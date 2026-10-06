import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { getCirclePaymentStatus } from '../api/circle'
import { getCirclePaymentPhase, getPendingStatusMessage, CIRCLE_PAYMENT_PHASE } from '../utils/circlePayment'
import useSeo from '../hooks/useSeo'
import EmptyState from '../components/ui/EmptyState'

// Paystack redirects here after the hosted checkout (see backend
// app/services/circle_payments.py's _build_callback_url, which must stay
// pointed at this exact path). The `reference` query param is ONLY a
// locator for which CirclePayment to look up — it is never treated as
// proof of anything. This page never activates membership itself; every
// render below is a direct reflection of what GET /circle/payments/
// <reference> (owner-scoped, backend-authoritative) just reported.
// Refreshing this page is always safe: it only ever re-asks the backend
// for the current state, never re-initializes checkout.

const POLL_INTERVAL_MS = 4000
const MAX_AUTO_ATTEMPTS = 15 // ~60s at the interval above

export default function CircleCheckoutCallbackPage() {
  const [searchParams] = useSearchParams()
  const reference = (searchParams.get('reference') || '').trim()

  const [result, setResult] = useState(undefined) // undefined = first fetch in flight
  const [timedOut, setTimedOut] = useState(false)
  const [fetchFailed, setFetchFailed] = useState(false)
  const [manualCheckToken, setManualCheckToken] = useState(0)

  useSeo({ title: 'Confirming your payment | WSF Circle', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!reference) return undefined

    // `cancelled` and `timeoutId` are local to THIS effect invocation
    // (closure-captured, not refs). A ref shared across re-runs would get
    // reset by the next effect's startup, un-cancelling a still-in-flight
    // fetch/timeout from the PREVIOUS run (e.g. after "Check again" fires
    // while a request is pending) and risking two poll loops running at
    // once. Scoping these as plain variables means each run's cleanup can
    // only ever cancel that same run's chain.
    let cancelled = false
    let timeoutId = null

    async function checkOnce() {
      try {
        const data = await getCirclePaymentStatus(reference)
        if (cancelled) return null
        setFetchFailed(false)
        setResult(data)
        return data
      } catch {
        if (cancelled) return null
        setFetchFailed(true)
        return null
      }
    }

    let attempts = 0
    async function pollLoop() {
      const data = await checkOnce()
      if (cancelled) return
      const phase = data ? getCirclePaymentPhase(data) : CIRCLE_PAYMENT_PHASE.PENDING
      attempts += 1
      if (phase === CIRCLE_PAYMENT_PHASE.PENDING && attempts < MAX_AUTO_ATTEMPTS) {
        // setTimeout after each completed request, not a bare setInterval
        // — the next poll is only ever scheduled once this one has fully
        // resolved, so overlapping requests can't pile up.
        timeoutId = setTimeout(pollLoop, POLL_INTERVAL_MS)
      } else if (phase === CIRCLE_PAYMENT_PHASE.PENDING) {
        setTimedOut(true)
      }
    }

    pollLoop()

    return () => {
      cancelled = true
      if (timeoutId) clearTimeout(timeoutId)
    }
    // manualCheckToken intentionally restarts this whole effect (a fresh,
    // bounded poll) when the visitor clicks "Check again" below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reference, manualCheckToken])

  function handleCheckAgain() {
    setTimedOut(false)
    setFetchFailed(false)
    setResult(undefined)
    setManualCheckToken((n) => n + 1)
  }

  if (!reference) {
    return (
      <div className="container-editorial max-w-xl py-20">
        <EmptyState
          title="We couldn't identify this payment."
          description="The link you followed is missing the information we need to look up your payment."
          action={
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <Link to="/circle" className="btn-primary">Return to WSF Circle</Link>
              <Link to="/account/membership" className="btn-secondary">View Membership</Link>
            </div>
          }
        />
      </div>
    )
  }

  if (fetchFailed) {
    return (
      <div className="container-editorial max-w-xl py-20">
        <EmptyState
          title="We couldn't check this payment right now."
          description="This doesn't mean anything went wrong with your payment — we just couldn't reach our server. Please try again."
          action={
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <button type="button" onClick={handleCheckAgain} className="btn-primary">Check again</button>
              <Link to="/account/membership" className="btn-secondary">View Membership</Link>
              <Link to="/circle" className="text-sm font-semibold text-burgundy-600 hover:underline">Return to WSF Circle</Link>
            </div>
          }
        />
      </div>
    )
  }

  const phase = result ? getCirclePaymentPhase(result) : CIRCLE_PAYMENT_PHASE.PENDING

  if (result === undefined || phase === CIRCLE_PAYMENT_PHASE.PENDING) {
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        {!timedOut && (
          <div className="mx-auto mb-6 h-8 w-8 animate-spin border-2 border-taupe-300 border-t-burgundy-500" aria-hidden="true" />
        )}
        <p role="status" aria-live="polite" className="font-serif text-xl font-semibold text-charcoal">
          {getPendingStatusMessage(result, timedOut)}
        </p>
        {timedOut && (
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" onClick={handleCheckAgain} className="btn-primary">Check again</button>
            <Link to="/account/membership" className="btn-secondary">View Membership</Link>
            <Link to="/circle" className="text-sm font-semibold text-burgundy-600 hover:underline">Return to WSF Circle</Link>
          </div>
        )}
      </div>
    )
  }

  if (phase === CIRCLE_PAYMENT_PHASE.CONSUMED) {
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        <p className="eyebrow">Payment confirmed</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Welcome to WSF Circle</h1>
        <p className="mt-3 text-charcoal-600">Your membership is now active.</p>
        <Link to="/account/membership?payment=success" className="btn-primary mt-8 inline-block">
          View My Membership
        </Link>
      </div>
    )
  }

  if (phase === CIRCLE_PAYMENT_PHASE.RECONCILIATION || phase === CIRCLE_PAYMENT_PHASE.CONFLICT) {
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        <h1 className="font-serif text-2xl font-semibold text-charcoal">We&apos;re reviewing your payment</h1>
        <p className="mt-3 text-charcoal-600">
          Your payment was received, but we need to confirm a detail before activating your membership. This does
          not mean your payment failed — our team will follow up if we need anything from you.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          <Link to="/account/membership" className="btn-primary">View Membership</Link>
          <Link to="/contact" className="btn-secondary">Contact WSF</Link>
        </div>
      </div>
    )
  }

  // phase === FAILED (covers both the backend's "failed" and "abandoned"
  // provider outcomes — see getCirclePaymentPhase's own comment).
  return (
    <div className="container-editorial max-w-xl py-20 text-center">
      <h1 className="font-serif text-2xl font-semibold text-charcoal">Your payment was not completed</h1>
      <p className="mt-3 text-charcoal-600">No WSF Circle membership has been activated for this attempt.</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link to="/circle" className="btn-primary">Try Again</Link>
        <Link to="/contact" className="btn-secondary">Request Assistance</Link>
      </div>
    </div>
  )
}
