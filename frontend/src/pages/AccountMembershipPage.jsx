import { useEffect, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchMyCircleMembership } from '../api/circle'
import { formatProductPrice } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import { formatDate } from '../utils/format'

function billingLabel(plan) {
  return plan?.billingInterval === 'yearly' ? 'Yearly' : 'Monthly'
}

export default function AccountMembershipPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)

  const [membership, setMembership] = useState(undefined)
  const [error, setError] = useState(null)
  const [retryCount, setRetryCount] = useState(0)

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

  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  const subscription = membership?.subscription || null
  const status = subscription?.status

  return (
    <div className="container-editorial max-w-3xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">WSF Circle</h1>

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
                    {subscription.cancelAtPeriodEnd ? 'Access ends' : 'Current period ends'}
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
              Explore membership options
            </Link>
          </div>
        )}
      </div>
    </div>
  )
}
