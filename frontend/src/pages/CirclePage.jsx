import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchCirclePlans, fetchMyCircleMembership, requestCircleMembership } from '../api/circle'
import { formatProductPrice } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import ArticleContent from '../components/article/ArticleContent'

const BENEFITS = [
  { title: 'Deeper learning', description: 'Priority access to WSF Learning programs as the catalog grows.' },
  { title: 'Career resources', description: 'Curated guidance and tools designed for ambitious career moves.' },
  { title: 'Community experiences', description: 'A closer connection to the women shaping their industries alongside you.' },
]

function billingLabel(plan) {
  return plan.billingInterval === 'yearly' ? '/ year' : '/ month'
}

// Phase 1: WSF Circle has no self-service checkout yet (see
// api/circle.js's module docstring) — this submits a staff-reviewable
// lead only (POST /circle/membership-requests) and never implies payment
// happened or membership is now active. `plan` is optional: omitted on
// the zero-plans fallback below, where the request simply isn't tied to a
// specific plan yet.
function CircleMembershipRequestPanel({ plan }) {
  const [note, setNote] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setSubmitting(true)
    setError(false)
    try {
      await requestCircleMembership({ planSlug: plan?.slug, note })
      trackEvent('circle_membership_request_submitted', { planSlug: plan?.slug || null })
      setSubmitted(true)
    } catch {
      // Kept as a local inline message rather than react-toastify — this
      // panel already renders its own error state below.
      setError(true)
    } finally {
      setSubmitting(false)
    }
  }

  if (submitted) {
    return (
      <div className="mt-4 border border-burgundy-400 bg-blush-50 p-4 text-sm text-charcoal">
        <p className="font-semibold">Your WSF Circle membership request has been received.</p>
        <p className="mt-1 text-charcoal-600">Our team will contact you with the next steps.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mt-4 border border-taupe-200 bg-white p-4 text-sm">
      <p className="font-serif text-base font-semibold text-charcoal">Ready to join WSF Circle?</p>
      <p className="mt-1 text-charcoal-600">
        WSF Circle enrollment is currently assisted by our team. Send your membership request and we&apos;ll help you
        complete your enrollment.
      </p>
      <label htmlFor={`circle-request-note-${plan?.slug || 'general'}`} className="mt-3 block text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        Anything we should know? <span className="normal-case text-charcoal-600/60">(optional)</span>
      </label>
      <textarea
        id={`circle-request-note-${plan?.slug || 'general'}`}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        rows={2}
        className="mt-1.5 w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
      />
      {error && <p className="mt-2 text-xs text-rose-600">Something went wrong. Please try again.</p>}
      <button type="submit" disabled={submitting} className="btn-primary mt-3 disabled:opacity-60">
        {submitting ? 'Sending…' : 'Request to Join WSF Circle'}
      </button>
    </form>
  )
}

function PlanCta({ plan, accessToken, hasAccess, loginFrom }) {
  if (!accessToken) {
    return (
      <Link to="/login" state={{ from: loginFrom }} className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
        Join WSF Circle &rarr;
      </Link>
    )
  }

  if (hasAccess) {
    return null
  }

  if (plan.checkoutAvailable && plan.checkoutUrl) {
    return (
      <div className="mt-4 text-sm">
        <a
          href={plan.checkoutUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackEvent('circle_checkout_click', { planSlug: plan.slug })}
          className="font-semibold text-burgundy-600 hover:underline"
        >
          Continue to secure checkout &rarr;
        </a>
        <p className="mt-2 text-xs text-charcoal-600/70">
          Membership access becomes active once your enrollment and payment have been confirmed by our team — it
          isn&apos;t activated automatically when you follow this link.
        </p>
      </div>
    )
  }

  return <CircleMembershipRequestPanel plan={plan} />
}

export default function CirclePage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const location = useLocation()

  const [plans, setPlans] = useState(undefined)
  const [membership, setMembership] = useState(undefined)

  useSeo({
    title: 'WSF Circle | Women Shaping Futures',
    description: 'WSF Circle is the premium membership experience for women who want deeper access to learning, career resources, curated opportunities, events and community experiences.',
    canonical: 'https://womenshapingfutures.org/circle',
  })

  useEffect(() => {
    let active = true
    fetchCirclePlans()
      .then((list) => {
        if (active) setPlans(list)
        trackEvent('circle_page_view')
      })
      .catch(() => active && setPlans([]))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!accessToken) return undefined
    let active = true
    fetchMyCircleMembership()
      .then((result) => active && setMembership(result))
      .catch(() => active && setMembership(null))
    return () => {
      active = false
    }
  }, [accessToken])

  if (plans === undefined) return <PageLoader />

  const hasAccess = !!membership?.hasAccess

  return (
    <div>
      <PageHeader
        eyebrow="WSF Circle"
        title="A closer circle for women shaping their futures"
        description="WSF Circle is the premium membership experience for women who want deeper access to learning, career resources, curated opportunities, events and community experiences."
      />

      <div className="container-editorial py-14">
        {accessToken && hasAccess && (
          <div className="mb-14 border border-burgundy-400 bg-blush-50 p-6 text-center">
            <p className="font-serif text-xl font-semibold text-charcoal">You're a WSF Circle member</p>
            <Link to="/account/membership" className="btn-primary mt-4 inline-block">
              Manage membership
            </Link>
          </div>
        )}

        <div className="border-b border-taupe-200 pb-14">
          <h2 className="font-serif text-3xl font-semibold text-charcoal">Why WSF Circle</h2>
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {BENEFITS.map((b, i) => (
              <div key={i} className="border border-taupe-200 bg-white p-5">
                <h3 className="font-serif text-lg font-semibold text-charcoal">{b.title}</h3>
                <p className="mt-2 text-sm text-charcoal-600">{b.description}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="py-14">
          <h2 className="font-serif text-3xl font-semibold text-charcoal">Membership</h2>
          {plans.length === 0 ? (
            <div className="mt-4 text-sm text-charcoal-600">
              <p>
                WSF Circle membership plans are being finalized. Please check back soon, or{' '}
                <Link to="/contact" className="font-semibold text-burgundy-600 hover:underline">
                  contact WSF
                </Link>{' '}
                with questions.
              </p>
              {accessToken && !hasAccess && <CircleMembershipRequestPanel plan={null} />}
            </div>
          ) : (
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {plans.map((plan) => (
                <div
                  key={plan.slug}
                  className={`border p-6 ${plan.featured ? 'border-burgundy-400 bg-blush-50' : 'border-taupe-200 bg-white'}`}
                >
                  {plan.featured && (
                    <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</p>
                  )}
                  <h3 className="font-serif text-xl font-semibold text-charcoal">{plan.name}</h3>
                  {plan.shortDescription && <p className="mt-2 text-sm text-charcoal-600">{plan.shortDescription}</p>}
                  <p className="mt-4 text-2xl font-semibold text-charcoal">
                    {formatProductPrice(plan.price, plan.currency)}
                    <span className="ml-1 text-sm font-normal text-charcoal-600/70">{billingLabel(plan)}</span>
                  </p>
                  {plan.benefits?.length > 0 && (
                    <ul className="mt-4 space-y-1 text-sm text-charcoal-600">
                      {plan.benefits.map((b, i) => (
                        <li key={i}>&bull; {b}</li>
                      ))}
                    </ul>
                  )}
                  {plan.description?.length > 0 && (
                    <div className="mt-4 text-sm text-charcoal-600">
                      <ArticleContent blocks={plan.description} />
                    </div>
                  )}
                  <PlanCta plan={plan} accessToken={accessToken} hasAccess={hasAccess} loginFrom={location.pathname} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
