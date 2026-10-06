import { useEffect, useState } from 'react'
import { Navigate, Link, useSearchParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchMyCircleMembership, startCircleCheckout } from '../api/circle'
import { formatProductPrice } from '../utils/format'
import { getCheckoutErrorPresentation } from '../utils/circlePayment'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import { formatDate } from '../utils/format'

function billingLabel(plan) {
  return plan?.billingInterval === 'yearly' ? 'Yearly' : 'Monthly'
}

export default function AccountMembershipPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)
  const [searchParams, setSearchParams] = useSearchParams()
  // `?payment=success` is never trusted by itself — the effect below only
  // ever flips `showSuccessBanner` on once `membership.hasAccess` (real
  // backend data) confirms it, and only then strips the param from the URL
  // (replace navigation, no new history entry). The param's mere presence
  // never shows or hides anything by itself.
  const paymentSuccessParam = searchParams.get('payment') === 'success'

  const [membership, setMembership] = useState(undefined)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)
  const [renewing, setRenewing] = useState(false)
  const [renewError, setRenewError] = useState(null)
  const [showSuccessBanner, setShowSuccessBanner] = useState(false)

  useSeo({ title: 'WSF Circle | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!accessToken) return undefined
    let cancelled = false
    fetchMyCircleMembership()
      .then((result) => {
        if (!cancelled) {
          setMembership(result)
          setError(null)
        }
      })
      .catch(() => {
        if (!cancelled) setError("We couldn't load your WSF Circle membership. Please try again.")
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, retryCount])

  // Genuinely one-time: we wait for the real membership fetch to resolve,
  // and only turn the banner on — then clean `payment=success` out of the
  // URL with a replace navigation (no new history entry) — once backend
  // data (`hasAccess`) actually confirms it. `showSuccessBanner` is plain
  // component state from here on, so it survives the URL edit for the rest
  // of this mount; a later refresh of the now-clean `/account/membership`
  // URL has no `payment` param left to re-trigger it.
  useEffect(() => {
    if (membership === undefined) return
    if (paymentSuccessParam && membership?.hasAccess) {
      setShowSuccessBanner(true)
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev)
          next.delete('payment')
          return next
        },
        { replace: true },
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [membership, paymentSuccessParam])

  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  const subscription = membership?.subscription || null
  const status = subscription?.status

  // Renewal is only ever offered for the exact situation Module 2's backend
  // actually supports as "renew" (see _classify_membership_action): the
  // SAME plan, with a real (non-null) current_period_end. A non-expiring
  // or terminal membership never gets this button — see sections below.
  const canRenew = status === 'active' && !!subscription?.currentPeriodEnd && !!subscription?.plan?.slug

  async function handleRenew() {
    if (renewing || !subscription?.plan?.slug) return
    setRenewError(null)
    setRenewing(true)
    trackEvent('circle_renew_initiated', { planSlug: subscription.plan.slug })
    try {
      const { authorizationUrl } = await startCircleCheckout(subscription.plan.slug)
      if (!authorizationUrl) throw new Error('Checkout response was missing an authorization URL.')
      window.location.assign(authorizationUrl)
    } catch (err) {
      const code = err?.response?.data?.error?.code
      setRenewError(getCheckoutErrorPresentation(code).message)
      setRenewing(false)
    }
  }

  return (
    <div className="container-editorial max-w-3xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">WSF Circle</h1>

      {showSuccessBanner && (
        <div className="mt-6 border border-burgundy-400 bg-blush-50 p-5 text-center">
          <p className="font-serif text-lg font-semibold text-charcoal">Your WSF Circle membership is active.</p>
          <p className="mt-1 text-sm text-charcoal-600">Welcome to the community.</p>
        </div>
      )}

      <div className="mt-8">
        {error ? (
          <div className="border border-taupe-200 p-6">
            <p className="text-sm text-charcoal-600">{error}</p>
            <button type="button" onClick={() => setRetryCount((n) => n + 1)} className="btn-secondary mt-4">
              Try again
            </button>
          </div>
        ) : membership === undefined ? (
          <div className="h-40 animate-pulse bg-taupe-100" />
        ) : !subscription ? (
          <div className="border border-taupe-200 p-6">
            <p className="text-sm text-charcoal-600">You are not currently a WSF Circle member.</p>
            <Link to="/circle" className="btn-primary mt-4 inline-block">
              Explore WSF Circle
            </Link>
          </div>
        ) : status === "pending" ? (
          <div className="border border-taupe-200 p-6">
            <p className="font-serif text-lg font-semibold text-charcoal">Membership pending</p>
            <p className="mt-2 text-sm text-charcoal-600">
              Your WSF Circle membership is being set up. We'll let you know as soon as it's confirmed.
            </p>
          </div>
        ) : status === "active" ? (
          <div className="border border-taupe-200 p-6">
            <p className="text-xs font-semibold uppercase tracking-wide text-burgundy-600">Active</p>
            <p className="mt-1 font-serif text-xl font-semibold text-charcoal">{subscription.plan?.name}</p>
            <p className="mt-1 text-sm text-charcoal-600">
              {billingLabel(subscription.plan)}
              {subscription.plan?.price != null && (
                <> &middot; {formatProductPrice(subscription.plan.price, subscription.plan.currency)}</>
              )}
            </p>
            <dl className="mt-4 grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              {subscription.startsAt && (
                <div>
                  <dt className="text-charcoal-600/70">Member since</dt>
                  <dd className="text-charcoal">{formatDate(subscription.startsAt)}</dd>
                </div>
              )}
              {subscription.currentPeriodEnd && (
                <div>
                  <dt className="text-charcoal-600/70">
                    {subscription.cancelAtPeriodEnd ? 'Access ends' : 'Your access runs through'}
                  </dt>
                  <dd className="text-charcoal">{formatDate(subscription.currentPeriodEnd)}</dd>
                </div>
              )}
            </dl>
            {subscription.cancelAtPeriodEnd && (
              <p className="mt-4 text-sm text-charcoal-600">
                Your membership is set to end{subscription.currentPeriodEnd ? ` on ${formatDate(subscription.currentPeriodEnd)}` : ''}.
                You'll keep full access until then.
              </p>
            )}
            {canRenew && (
              <div className="mt-6 border-t border-taupe-200 pt-5">
                <button
                  type="button"
                  onClick={handleRenew}
                  disabled={renewing}
                  aria-busy={renewing}
                  className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {renewing ? 'Preparing secure checkout…' : 'Renew membership'}
                </button>
                <p className="mt-2 text-xs text-charcoal-600/70">
                  Renewing extends your current access period for the same plan — this is a single payment, not
                  automatic billing.
                </p>
                {renewError && (
                  <p className="mt-2 text-sm text-rose-600" role="alert">{renewError}</p>
                )}
              </div>
            )}
          </div>
        ) : status === "past_due" ? (
          <div className="border border-taupe-200 p-6">
            <p className="font-serif text-lg font-semibold text-charcoal">Membership needs attention</p>
            <p className="mt-2 text-sm text-charcoal-600">
              There's an issue with your WSF Circle membership. Please contact Women Shaping Futures so we can help.
            </p>
            <Link to="/contact" className="mt-3 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
              Contact WSF
            </Link>
          </div>
        ) : (
          <div className="border border-taupe-200 p-6">
            <p className="font-serif text-lg font-semibold text-charcoal">
              {status === 'cancelled' ? 'Membership cancelled' : status === 'expired' ? 'Membership expired' : 'Not currently active'}
            </p>
            <p className="mt-2 text-sm text-charcoal-600">You don't currently have an active WSF Circle membership.</p>
            <Link to="/circle" className="btn-primary mt-4 inline-block">
              Renew WSF Circle
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
