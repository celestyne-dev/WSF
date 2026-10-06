import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchCirclePlans, fetchMyCircleMembership, requestCircleMembership, startCircleCheckout } from '../api/circle'
import { getMembershipAction, getCheckoutErrorPresentation } from '../utils/circlePayment'
import { formatProductPrice } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import PageLoader from '../components/ui/PageLoader'
import ArticleContent from '../components/article/ArticleContent'

const BENEFITS = [
  { title: 'WSF Learning', description: 'Full access to WSF Circle learning programs and courses as the catalog grows.' },
  { title: 'WSF Circle resources', description: 'Guides, workbooks, and tools reserved for WSF Circle members — separate from one-off premium purchases.' },
  { title: 'Opportunities & jobs', description: 'Selected roles and opportunities reserved for WSF Circle members.' },
  { title: 'WSF Circle events', description: 'Community gatherings and sessions held exclusively for members.' },
]

function billingLabel(plan) {
  return plan.billingInterval === 'yearly' ? '/ year' : '/ month'
}

// Module 4's secondary/fallback path (Phase 1 staff-assisted enrollment is
// still exactly this — see api/circle.js's own comment). Collapsed by
// default wherever "Pay securely" is available, so it never competes with
// the primary CTA — only expanded on request, or rendered directly for the
// membership states where no automated payment is offered at all (see
// PlanCta below). `plan` is optional: omitted on the zero-plans fallback,
// where the request simply isn't tied to a specific plan yet.
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
      <div className="mt-3 border border-burgundy-400 bg-blush-50 p-4 text-sm text-charcoal">
        <p className="font-semibold">Your WSF Circle request has been received.</p>
        <p className="mt-1 text-charcoal-600">Our team will contact you with the next steps.</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 border border-taupe-200 bg-white p-4 text-sm">
      <p className="text-charcoal-600">
        Tell us what you need help with — a different plan, a payment issue, or a special enrollment request — and
        our team will follow up.
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
      <button type="submit" disabled={submitting} className="btn-primary mt-3 disabled:cursor-not-allowed disabled:opacity-60">
        {submitting ? 'Sending…' : 'Request assistance'}
      </button>
    </form>
  )
}

// A small, collapsed-by-default trigger for the panel above — this is
// what keeps assisted enrollment "secondary/fallback" rather than
// cluttering every plan card once native Paystack checkout is the primary
// path (see this module's own docstring in api/circle.js).
function RequestAssistanceToggle({ plan, label = 'Request assistance' }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="mt-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="text-xs font-semibold text-burgundy-600 hover:underline"
      >
        {label}
      </button>
      {open && <CircleMembershipRequestPanel plan={plan} />}
    </div>
  )
}

function PlanCta({ plan, accessToken, membership, hasAccess, loginFrom, checkingOutSlug, checkoutError, onPaySecurely }) {
  if (!accessToken) {
    return (
      <Link to="/login" state={{ from: loginFrom }} className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
        Join WSF Circle &rarr;
      </Link>
    )
  }

  if (hasAccess) return null

  // Still loading GET /circle/me — deliberately shows nothing rather than
  // a CTA that might be wrong for a moment (e.g. briefly offering "Pay
  // securely" to someone who turns out to have a pending request).
  if (membership === undefined) return null

  const action = getMembershipAction(membership, plan)
  const errorForThisPlan = checkoutError?.slug === plan.slug ? checkoutError : null

  if (action === 'blocked_pending') {
    return (
      <p className="mt-4 text-sm text-charcoal-600">
        Your WSF Circle membership request is awaiting review. We&apos;ll be in touch soon.
      </p>
    )
  }

  if (action === 'blocked_non_expiring') {
    return (
      <p className="mt-4 text-sm text-charcoal-600">
        Your WSF Circle membership doesn&apos;t have an automatic expiry.{' '}
        <Link to="/contact" className="font-semibold text-burgundy-600 hover:underline">Contact WSF</Link> about your account.
      </p>
    )
  }

  if (action === 'blocked_different_plan') {
    return (
      <div className="mt-4 text-sm">
        <p className="text-charcoal-600">You&apos;re currently on another WSF Circle plan.</p>
        <RequestAssistanceToggle plan={plan} label="Request a plan change" />
      </div>
    )
  }

  // action is 'new' or 'renew' — both check out through the exact same
  // POST /circle/plans/<slug>/checkout flow; the backend (not this
  // component) decides whether that activates a fresh membership or
  // extends the current one.
  const isCheckingOut = checkingOutSlug === plan.slug
  const disableButton = !!checkingOutSlug

  return (
    <div className="mt-4">
      <button
        type="button"
        onClick={() => onPaySecurely(plan)}
        disabled={disableButton}
        aria-busy={isCheckingOut}
        className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isCheckingOut ? 'Preparing secure checkout…' : 'Pay securely'}
      </button>
      {errorForThisPlan && (
        <p className="mt-2 text-sm text-rose-600" role="alert">
          {errorForThisPlan.message}
        </p>
      )}
      {errorForThisPlan?.showAssistance && <RequestAssistanceToggle plan={plan} />}
      {plan.checkoutAvailable && plan.checkoutUrl && (
        <p className="mt-3 text-xs text-charcoal-600/70">
          Prefer a different payment method?{' '}
          <a
            href={plan.checkoutUrl}
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackEvent('circle_alternate_checkout_click', { planSlug: plan.slug })}
            className="font-semibold text-burgundy-600 hover:underline"
          >
            Use our alternate secure checkout
          </a>
          . Membership access becomes active only once your payment is confirmed — it isn&apos;t activated
          automatically when you follow this link.
        </p>
      )}
    </div>
  )
}

export default function CirclePage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const location = useLocation()

  const [plans, setPlans] = useState(undefined)
  const [membership, setMembership] = useState(undefined)
  const [checkingOutSlug, setCheckingOutSlug] = useState(null)
  const [checkoutError, setCheckoutError] = useState(null)

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

  // Backend dedupe (Module 2's _find_reusable_pending_payment) already
  // protects against a genuine double-submission server-side; this local
  // guard just keeps the UI from firing a second request — and from
  // letting a click on a DIFFERENT plan's button start a second checkout
  // — while one is already in flight.
  async function handlePaySecurely(plan) {
    if (checkingOutSlug) return
    setCheckoutError(null)
    setCheckingOutSlug(plan.slug)
    trackEvent('circle_checkout_initiated', { planSlug: plan.slug })
    try {
      const { authorizationUrl } = await startCircleCheckout(plan.slug)
      if (!authorizationUrl) throw new Error('Checkout response was missing an authorization URL.')
      // Full browser redirect to Paystack's hosted checkout — never an
      // iframe, never a WSF-collected card/M-PESA form. We never say
      // payment "started" until this URL is actually in hand.
      window.location.assign(authorizationUrl)
    } catch (err) {
      const code = err?.response?.data?.error?.code
      setCheckoutError({ slug: plan.slug, ...getCheckoutErrorPresentation(code) })
      setCheckingOutSlug(null)
    }
  }

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
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
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
                  <PlanCta
                    plan={plan}
                    accessToken={accessToken}
                    membership={membership}
                    hasAccess={hasAccess}
                    loginFrom={location.pathname}
                    checkingOutSlug={checkingOutSlug}
                    checkoutError={checkoutError}
                    onPaySecurely={handlePaySecurely}
                  />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
