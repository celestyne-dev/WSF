import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Link, useSearchParams } from 'react-router-dom'
import { toast } from 'react-toastify'
import { getResourcePaymentStatus, requestResourceAccess } from '../api/resources'
import { getResourcePaymentPhase, getResourcePendingStatusMessage, RESOURCE_PAYMENT_PHASE } from '../utils/resourcePayment'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import EmptyState from '../components/ui/EmptyState'

// Paystack redirects here after the hosted checkout (see backend
// app/services/resource_payments.py's _build_callback_url, which must
// stay pointed at this exact path). The `reference` query param is ONLY
// a locator for which ResourcePayment to look up — it is never treated
// as proof of anything. This page never activates purchase entitlement
// itself; every render below is a direct reflection of what GET
// /resources/payments/<reference> (owner-scoped, backend-authoritative)
// just reported. Refreshing this page is always safe: it only ever
// re-asks the backend for the current state, never re-initializes
// checkout. Modeled on CircleCheckoutCallbackPage.jsx — see that file for
// the shared polling-pattern rationale; the two differ only in copy and
// in the lack of Circle's "conflict" phase (a one-time purchase has no
// renewal/plan-switch concept to conflict with).

const POLL_INTERVAL_MS = 4000
const MAX_AUTO_ATTEMPTS = 15 // ~60s at the interval above

export default function ResourceCheckoutCallbackPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [searchParams] = useSearchParams()
  const reference = (searchParams.get('reference') || '').trim()

  const [result, setResult] = useState(undefined) // undefined = first fetch in flight
  const [timedOut, setTimedOut] = useState(false)
  const [fetchFailed, setFetchFailed] = useState(false)
  const [authRequired, setAuthRequired] = useState(false)
  const [manualCheckToken, setManualCheckToken] = useState(0)
  const [downloading, setDownloading] = useState(false)

  useSeo({ title: 'Confirming your purchase | Women Shaping Futures Resources', robots: 'noindex, nofollow' })

  useEffect(() => {
    // No accessToken at all means GET /resources/payments/<reference>
    // would just 401 — and the app's global 401 interceptor (see
    // api/client.js's handleUnauthorized) would hard-redirect the whole
    // page to bare /login the instant that happens, with no return path.
    // Checking here first, before ever making the request, is what lets
    // this page show its own "sign in" state below with the callback URL
    // (reference included) preserved instead.
    if (!reference || !accessToken) return undefined

    // `cancelled` and `timeoutId` are local to THIS effect invocation, not
    // refs — see CircleCheckoutCallbackPage.jsx's identical comment for
    // why that matters for "Check again" correctness.
    let cancelled = false
    let timeoutId = null

    async function checkOnce() {
      try {
        const data = await getResourcePaymentStatus(reference)
        if (cancelled) return { data: null }
        setFetchFailed(false)
        setResult(data)
        return { data }
      } catch (err) {
        if (cancelled) return { data: null }
        // Defense in depth: a token that was present but expired/invalid
        // between render and this request still surfaces the same
        // "sign in" state as having no token at all, rather than the
        // generic fetch-failed message.
        if (err?.response?.status === 401) {
          setAuthRequired(true)
          return { data: null, authRequired: true }
        }
        setFetchFailed(true)
        return { data: null }
      }
    }

    let attempts = 0
    async function pollLoop() {
      const { data, authRequired: needsAuth } = await checkOnce()
      if (cancelled || needsAuth) return
      const phase = data ? getResourcePaymentPhase(data) : RESOURCE_PAYMENT_PHASE.PENDING
      attempts += 1
      if (phase === RESOURCE_PAYMENT_PHASE.PENDING && attempts < MAX_AUTO_ATTEMPTS) {
        // setTimeout after each completed request, not a bare
        // setInterval — the next poll is only ever scheduled once this
        // one has fully resolved, so overlapping requests can't pile up.
        timeoutId = setTimeout(pollLoop, POLL_INTERVAL_MS)
      } else if (phase === RESOURCE_PAYMENT_PHASE.PENDING) {
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
  }, [reference, accessToken, manualCheckToken])

  function handleCheckAgain() {
    setTimedOut(false)
    setFetchFailed(false)
    setAuthRequired(false)
    setResult(undefined)
    setManualCheckToken((n) => n + 1)
  }

  // The one download action this page ever takes — identical in shape to
  // ResourceDetailPage.jsx's handleAccessClick: every download, including
  // the very first one right after a successful purchase, goes through
  // POST /resources/<slug>/access again rather than reusing any URL this
  // page might have seen before (there is none to reuse — Paystack's
  // reference is never itself a download credential).
  async function handleDownload(resourceSlug) {
    if (downloading || !resourceSlug) return
    setDownloading(true)
    try {
      const { url } = await requestResourceAccess(resourceSlug)
      trackEvent('resource_download_success', { resourceSlug, accessType: 'premium' })
      window.open(url, '_blank', 'noopener,noreferrer')
    } catch {
      toast.error("We couldn't start your download. Please try again from the resource page.")
    } finally {
      setDownloading(false)
    }
  }

  if (!reference) {
    return (
      <div className="container-editorial max-w-xl py-20">
        <EmptyState
          title="We couldn't identify this payment."
          description="The link you followed is missing the information we need to look up your payment."
          action={
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <Link to="/resources" className="btn-primary">Browse Resources</Link>
              <Link to="/contact" className="btn-secondary">Contact WSF</Link>
            </div>
          }
        />
      </div>
    )
  }

  if (!accessToken || authRequired) {
    const returnTo = `/resources/checkout/callback?reference=${encodeURIComponent(reference)}`
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        <h1 className="font-serif text-2xl font-semibold text-charcoal">Sign in to confirm your purchase</h1>
        <p className="mt-3 text-charcoal-600">
          We need you to sign back in so we can look up this payment on your account. Your Paystack reference is
          safely preserved — you won&apos;t need to pay again.
        </p>
        <Link to="/login" state={{ from: returnTo }} className="btn-primary mt-8 inline-block">
          Sign in
        </Link>
      </div>
    )
  }

  if (fetchFailed) {
    return (
      <div className="container-editorial max-w-xl py-20">
        <EmptyState
          title="We couldn't check this payment right now."
          description="This doesn't mean anything went wrong with your purchase — we just couldn't reach our server. Please try again."
          action={
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              <button type="button" onClick={handleCheckAgain} className="btn-primary">Check again</button>
              <Link to="/resources" className="btn-secondary">Browse Resources</Link>
              <Link to="/contact" className="text-sm font-semibold text-burgundy-600 hover:underline">Contact WSF</Link>
            </div>
          }
        />
      </div>
    )
  }

  const phase = result ? getResourcePaymentPhase(result) : RESOURCE_PAYMENT_PHASE.PENDING
  const resourceSlug = result?.resourceSlug || null

  if (result === undefined || phase === RESOURCE_PAYMENT_PHASE.PENDING) {
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        {!timedOut && (
          <div className="mx-auto mb-6 h-8 w-8 animate-spin border-2 border-taupe-300 border-t-burgundy-500" aria-hidden="true" />
        )}
        <p role="status" aria-live="polite" className="font-serif text-xl font-semibold text-charcoal">
          {getResourcePendingStatusMessage(result, timedOut)}
        </p>
        {timedOut && (
          <div className="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" onClick={handleCheckAgain} className="btn-primary">Check again</button>
            {resourceSlug && <Link to={`/resources/${resourceSlug}`} className="btn-secondary">View resource</Link>}
            <Link to="/resources" className="text-sm font-semibold text-burgundy-600 hover:underline">Browse Resources</Link>
          </div>
        )}
      </div>
    )
  }

  if (phase === RESOURCE_PAYMENT_PHASE.CONSUMED) {
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        <p className="eyebrow">Payment confirmed</p>
        <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Your resource is ready</h1>
        <p className="mt-3 text-charcoal-600">Your purchase is now linked to your WSF account.</p>
        <button
          type="button"
          onClick={() => handleDownload(resourceSlug)}
          disabled={downloading || !resourceSlug}
          className="btn-primary mt-8 inline-flex disabled:opacity-60"
        >
          {downloading ? 'Preparing…' : 'Download resource'}
        </button>
        {resourceSlug && (
          <p className="mt-4">
            <Link to={`/resources/${resourceSlug}`} className="text-sm font-semibold text-burgundy-600 hover:underline">
              View resource
            </Link>
          </p>
        )}
      </div>
    )
  }

  if (phase === RESOURCE_PAYMENT_PHASE.RECONCILIATION) {
    return (
      <div className="container-editorial max-w-xl py-20 text-center">
        <h1 className="font-serif text-2xl font-semibold text-charcoal">We&apos;re reviewing your payment</h1>
        <p className="mt-3 text-charcoal-600">
          Your payment was received, but we need to confirm a detail before unlocking the resource. This does not
          mean your payment failed.
        </p>
        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {resourceSlug && <Link to={`/resources/${resourceSlug}`} className="btn-primary">View resource</Link>}
          <Link to="/contact" className="btn-secondary">Contact WSF</Link>
        </div>
      </div>
    )
  }

  // phase === FAILED (covers both the backend's "failed" and "abandoned"
  // provider outcomes — see getResourcePaymentPhase's own comment).
  return (
    <div className="container-editorial max-w-xl py-20 text-center">
      <h1 className="font-serif text-2xl font-semibold text-charcoal">Your payment was not completed</h1>
      <p className="mt-3 text-charcoal-600">No purchase access was activated for this attempt.</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <Link to={resourceSlug ? `/resources/${resourceSlug}` : '/resources'} className="btn-primary">Try again</Link>
        <Link to="/contact" className="btn-secondary">Contact WSF</Link>
      </div>
    </div>
  )
}
