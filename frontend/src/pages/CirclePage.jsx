import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchCirclePlans, fetchMyCircleMembership } from '../api/circle'
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

function PlanCta({ plan, accessToken, hasAccess }) {
  if (!accessToken) {
    return (
      <Link to="/login" className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
        Join WSF Circle &rarr;
      </Link>
    )
  }

  if (hasAccess) {
    return null
  }

  if (plan.checkoutAvailable && plan.checkoutUrl) {
    return (
      <a
        href={plan.checkoutUrl}
        target="_blank"
        rel="noopener noreferrer"
        onClick={() => trackEvent('circle_checkout_click', { planSlug: plan.slug })}
        className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline"
      >
        Continue to secure checkout &rarr;
      </a>
    )
  }

  return (
    <div className="mt-4 text-sm text-charcoal-600/70">
      <p>Membership enrollment coming soon.</p>
      <Link to="/contact" className="font-semibold text-burgundy-600 hover:underline">
        Contact WSF
      </Link>
    </div>
  )
}

export default function CirclePage() {
  const accessToken = useSelector((s) => s.auth.accessToken)

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
            <p className="mt-4 text-sm text-charcoal-600">
              WSF Circle membership plans are being finalized. Please check back soon, or{' '}
              <Link to="/contact" className="font-semibold text-burgundy-600 hover:underline">
                contact WSF
              </Link>{' '}
              with questions.
            </p>
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
                  <PlanCta plan={plan} accessToken={accessToken} hasAccess={hasAccess} />
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
