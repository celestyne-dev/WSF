import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { Check, Infinity as InfinityIcon, Minus } from 'lucide-react'
import { fetchCirclePlans, fetchMyCircleMembership } from '../api/circle'
import { COMPARISON_ROWS, LIFETIME_EXCLUDED_NOTE, LIFETIME_INCLUDED, LIFETIME_LEAD, LIFETIME_TITLE } from '../constants/lifetime'
import { planOfferState } from '../utils/circlePlans'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import PageLoader from '../components/ui/PageLoader'

function defaultPrice(plan) {
  const option = (plan.prices || []).find((p) => p.currency === plan.defaultCurrency) || (plan.prices || [])[0]
  return option?.formatted || null
}

function Cell({ value }) {
  if (value === true) return <span className="inline-flex items-center gap-1 text-emerald-700"><Check size={16} aria-hidden="true" /><span className="sr-only">Included</span></span>
  if (value === false) return <span className="inline-flex items-center gap-1 text-charcoal-600/60"><Minus size={16} aria-hidden="true" /><span className="sr-only">Not included</span></span>
  return <span className="text-sm text-charcoal">{value}</span>
}

// WSF Lifetime sales page. Plans, prices, founding status and seat
// availability all come from the real CirclePlan data configured in
// Studio — nothing is hardcoded here. Joining hands off to the existing
// secure Circle checkout (/circle?plan=<slug>).
export default function LifetimePage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [plans, setPlans] = useState(null)
  const [membership, setMembership] = useState(null)

  useSeo({
    title: 'WSF Lifetime | Women Shaping Futures',
    description: 'One payment. Lifetime access to eligible WSF courses, learning paths, premium career resources and member benefits.',
    canonical: 'https://womenshapingfutures.org/lifetime',
  })
  useBreadcrumbStructuredData([{ label: 'WSF Lifetime' }], 'https://womenshapingfutures.org/lifetime')

  useEffect(() => {
    let active = true
    fetchCirclePlans()
      .then((list) => active && setPlans(list))
      .catch(() => active && setPlans([]))
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!accessToken) return undefined
    let active = true
    fetchMyCircleMembership()
      .then((m) => active && setMembership(m))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [accessToken])

  if (plans === null) return <PageLoader />
  const lifetimePlans = plans.filter((p) => p.isLifetime)
  const intervals = new Set(plans.map((p) => p.billingInterval))
  const columns = [
    { key: 'free', label: 'Free account' },
    intervals.has('monthly') && { key: 'monthly', label: 'Monthly' },
    intervals.has('yearly') && { key: 'yearly', label: 'Yearly' },
    intervals.has('lifetime') && { key: 'lifetime', label: 'Lifetime' },
  ].filter(Boolean)
  const subscription = membership?.subscription
  const isLifetimeMember = !!(membership?.lifetimeAccess || (membership?.hasAccess && subscription?.isLifetime))

  return (
    <div>
      <section className="bg-plum-700 text-ivory">
        <div className="container-editorial py-16 sm:py-20">
          <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-ivory/80">
            <InfinityIcon size={16} aria-hidden="true" /> WSF Lifetime
          </p>
          <h1 className="mt-4 max-w-3xl font-serif text-4xl font-semibold leading-[1.08] sm:text-5xl">{LIFETIME_TITLE}</h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-ivory/90">{LIFETIME_LEAD}</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            {isLifetimeMember ? (
              <p className="rounded-control bg-ivory/10 px-4 py-3 font-semibold">
                {subscription?.memberBadge || 'Lifetime Member'} — your Lifetime access is active.
              </p>
            ) : lifetimePlans.length > 0 ? (
              <a href="#join" className="btn-light">Join WSF Lifetime</a>
            ) : (
              <p className="text-ivory/90">WSF Lifetime isn&apos;t open for new members right now.</p>
            )}
          </div>
        </div>
      </section>

      <div className="container-editorial py-14">
        <section aria-labelledby="included-title" className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <div>
            <h2 id="included-title" className="font-serif text-3xl font-semibold text-charcoal">What&apos;s included</h2>
            <ul className="mt-6 space-y-3">
              {LIFETIME_INCLUDED.map((line) => (
                <li key={line} className="flex items-start gap-3 text-[1.0625rem] text-charcoal">
                  <Check size={20} aria-hidden="true" className="mt-0.5 shrink-0 text-plum-600" /> {line}
                </li>
              ))}
            </ul>
            <p className="mt-6 text-sm leading-relaxed text-charcoal-600">{LIFETIME_EXCLUDED_NOTE}</p>
            <p className="mt-3 text-sm text-charcoal-600">
              Lifetime gives you access, not shortcuts: certificates are still earned by completing each course.
            </p>
          </div>

          <div id="join" className="scroll-mt-24 space-y-5">
            {lifetimePlans.map((plan) => {
              const offer = planOfferState(plan)
              const price = defaultPrice(plan)
              return (
                <article key={plan.slug} className="rounded-card border border-plum-600 bg-white p-6 sm:p-7">
                  {offer.heading && <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">{offer.heading}</p>}
                  <h3 className="mt-1 font-serif text-2xl font-semibold text-charcoal">{plan.name}</h3>
                  {price && (
                    <p className="mt-3 font-serif text-4xl font-semibold text-charcoal">
                      {price} <span className="font-sans text-base font-medium text-charcoal-600">one payment</span>
                    </p>
                  )}
                  <p className="mt-1 text-sm text-charcoal-600">No membership renewal.</p>
                  {offer.status && (
                    <p className="mt-3 text-sm font-semibold text-burgundy-600">
                      {offer.status}{offer.remainingText ? ` · ${offer.remainingText}` : ''}
                    </p>
                  )}
                  {plan.shortDescription && <p className="mt-3 text-[15px] text-charcoal-600">{plan.shortDescription}</p>}
                  {!isLifetimeMember && !offer.full && (
                    <Link to={`/circle?plan=${encodeURIComponent(plan.slug)}`} className="btn-primary mt-5">
                      Join WSF Lifetime
                    </Link>
                  )}
                </article>
              )
            })}
            {!lifetimePlans.length && (
              <div className="rounded-card border border-taupe-200 bg-cream p-6">
                <p className="font-serif text-xl font-semibold text-charcoal">Not open right now</p>
                <p className="mt-2 text-sm text-charcoal-600">
                  Join the WSF Weekly newsletter to hear when WSF Lifetime opens, or explore <Link to="/circle" className="font-semibold text-burgundy-600 hover:underline">WSF Circle</Link>.
                </p>
              </div>
            )}
          </div>
        </section>

        {columns.length > 1 && (
          <section aria-labelledby="compare-title" className="mt-16 border-t border-taupe-200 pt-12">
            <h2 id="compare-title" className="font-serif text-3xl font-semibold text-charcoal">Compare memberships</h2>
            <p className="mt-2 text-sm text-charcoal-600">Only memberships currently on offer are shown. Prices are on the WSF Circle page.</p>
            <div className="relative mt-6 overflow-x-auto rounded-card border border-taupe-200 bg-white">
              <table className="w-full min-w-[640px] border-collapse text-left">
                <caption className="sr-only">What each WSF membership includes</caption>
                <thead>
                  <tr className="border-b border-taupe-200 bg-cream">
                    <th scope="col" className="px-4 py-3 text-sm font-semibold text-charcoal">Benefit</th>
                    {columns.map((c) => (
                      <th key={c.key} scope="col" className={`px-4 py-3 text-sm font-semibold ${c.key === 'lifetime' ? 'text-plum-600' : 'text-charcoal'}`}>{c.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {COMPARISON_ROWS.map((row) => (
                    <tr key={row.label} className="border-b border-taupe-100 last:border-0">
                      <th scope="row" className="px-4 py-3 text-sm font-medium text-charcoal">{row.label}</th>
                      {columns.map((c) => (
                        <td key={c.key} className={`px-4 py-3 ${c.key === 'lifetime' ? 'bg-blush-50' : ''}`}><Cell value={row[c.key]} /></td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}
      </div>
    </div>
  )
}
