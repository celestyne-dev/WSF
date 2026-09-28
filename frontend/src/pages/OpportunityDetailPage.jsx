import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Calendar, Globe2, Award, AlertCircle } from 'lucide-react'
import { fetchOpportunityBySlug, fetchOpportunities } from '../api/opportunities'
import { formatDate, formatFunding } from '../utils/format'
import { resolveImage } from '../utils/media'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import Tag from '../components/ui/Tag'
import ArticleContent from '../components/article/ArticleContent'
import OpportunityCard from '../components/cards/OpportunityCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

// Opportunity types are too varied (Scholarship, Fellowship, Grant,
// Competition, Internship…) to map onto a single schema.org type without
// forcing an ill fit. Only the two cases with a genuinely valid, specific
// schema.org type get type-specific JSON-LD; everything else relies on the
// standard Open Graph / meta tags already set by useSeo() below rather
// than pretending every opportunity is the same kind of thing.
const EDUCATIONAL_PROGRAM_TYPES = new Set([
  'Scholarship',
  'Fellowship',
  'Accelerator',
  'Incubator',
  'Training Program',
  'Mentorship Program',
  'Internship',
])
const GRANT_TYPES = new Set(['Grant', 'Funding Opportunity'])

function useOpportunityStructuredData(opportunity) {
  useEffect(() => {
    if (!opportunity) return
    let data = null

    if (GRANT_TYPES.has(opportunity.type)) {
      data = {
        '@context': 'https://schema.org',
        '@type': 'MonetaryGrant',
        name: opportunity.title,
        description: opportunity.shortDescription || opportunity.title,
        url: opportunity.applicationUrl || undefined,
        funder: opportunity.organization ? { '@type': 'Organization', name: opportunity.organization } : undefined,
        ...(opportunity.fundingMin != null && opportunity.currency
          ? {
              amount: {
                '@type': 'MonetaryAmount',
                currency: opportunity.currency,
                value: opportunity.fundingMax ?? opportunity.fundingMin,
              },
            }
          : {}),
      }
    } else if (EDUCATIONAL_PROGRAM_TYPES.has(opportunity.type)) {
      data = {
        '@context': 'https://schema.org',
        '@type': 'EducationalOccupationalProgram',
        name: opportunity.title,
        description: opportunity.shortDescription || opportunity.title,
        url: opportunity.applicationUrl || undefined,
        provider: opportunity.organization ? { '@type': 'Organization', name: opportunity.organization } : undefined,
        ...(opportunity.deadline ? { applicationDeadline: opportunity.deadline } : {}),
        ...(opportunity.openingDate ? { applicationStartDate: opportunity.openingDate } : {}),
      }
    }

    let el = document.head.querySelector('script[data-opportunity-structured-data]')
    if (data) {
      if (!el) {
        el = document.createElement('script')
        el.type = 'application/ld+json'
        el.setAttribute('data-opportunity-structured-data', 'true')
        document.head.appendChild(el)
      }
      el.textContent = JSON.stringify(data)
    } else if (el) {
      el.remove()
    }
    return () => el?.remove()
  }, [opportunity])
}

export default function OpportunityDetailPage() {
  const { slug } = useParams()
  const [opportunity, setOpportunity] = useState(undefined)
  const [more, setMore] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setOpportunity(undefined)
    setMore([])
    setError(null)

    fetchOpportunityBySlug(slug)
      .then((data) => {
        if (!active) return
        setOpportunity(data)
        if (!data) return
        fetchOpportunities({ type: data.type, pageSize: 4 })
          .then((res) => active && setMore(res.items.filter((o) => o.slug !== slug).slice(0, 3)))
          .catch(() => {})
      })
      .catch(() => active && setError('Something went wrong loading this opportunity. Please try again.'))

    return () => {
      active = false
    }
  }, [slug])

  const canonicalUrl = `https://womenshapingfutures.org/opportunities/${slug}`

  useSeo(
    opportunity
      ? {
          title: opportunity.seo?.title || `${opportunity.title} | Women Shaping Futures Opportunities`,
          description: opportunity.seo?.description || opportunity.shortDescription || opportunity.eligibility,
          canonical: opportunity.seo?.canonical || canonicalUrl,
          image: opportunity.logo ? resolveImage(opportunity.logo, { width: 1200, height: 630 }) : undefined,
          robots: opportunity.seo?.robots,
        }
      : {},
  )

  useOpportunityStructuredData(opportunity)

  function handleApplyClick() {
    trackEvent('opportunity_apply_click', { opportunitySlug: opportunity.slug })
  }

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this opportunity" description={error} /></div>
  if (opportunity === undefined) return <PageLoader />
  if (opportunity === null) return <NotFoundPage />

  const funding = formatFunding(opportunity)
  const geography = opportunity.countriesEligibleNames?.length ? opportunity.countriesEligibleNames.join(', ') : null

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Opportunities', to: '/opportunities' }, { label: opportunity.title }]} />

          {opportunity.sponsored && (
            <div className="mt-4 inline-flex items-center gap-2 border border-dashed border-taupe-300 bg-blush-50 px-4 py-2 text-xs text-charcoal-600">
              <span className="font-semibold uppercase tracking-wide text-burgundy-600">Sponsored</span>
              <span>This listing is a paid placement{opportunity.organization ? ` from ${opportunity.organization}` : ''}.</span>
            </div>
          )}

          {opportunity.isClosed && (
            <div className="mt-4 flex items-center gap-2 border border-taupe-300 bg-taupe-100 px-4 py-3 text-sm text-charcoal-600">
              <AlertCircle size={16} className="shrink-0" />
              <span className="font-semibold">Applications closed</span> — this opportunity is no longer accepting applications.
            </div>
          )}

          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            {opportunity.logo && (
              <MediaImage media={opportunity.logoMedia} variant="thumbnail" mediaPath={opportunity.logo} alt={opportunity.organization} width={160} height={160} aspect={1} className="h-20 w-20 border border-taupe-200 object-contain p-2" />
            )}
            <div>
              {opportunity.type && <Tag tone="plum">{opportunity.type}</Tag>}
              <h1 className="mt-3 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{opportunity.title}</h1>
              {opportunity.organizationSlug ? (
                <Link to={`/organizations/${opportunity.organizationSlug}`} className="mt-1 inline-block text-lg font-medium text-charcoal-600 hover:text-burgundy-600">
                  {opportunity.organization}
                </Link>
              ) : (
                opportunity.organization && <p className="mt-1 text-lg font-medium text-charcoal-600">{opportunity.organization}</p>
              )}
            </div>
          </div>

          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-charcoal-600">
            {geography && (
              <span className="inline-flex items-center gap-1.5">
                <Globe2 size={15} /> {geography}
              </span>
            )}
            {opportunity.deadline && (
              <span className="inline-flex items-center gap-1.5">
                <Calendar size={15} /> Deadline: {formatDate(opportunity.deadline)}
              </span>
            )}
            {funding && (
              <span className="inline-flex items-center gap-1.5">
                <Award size={15} /> {funding}
              </span>
            )}
          </div>

          {opportunity.isClosed ? (
            <button type="button" disabled className="btn-secondary mt-6 inline-flex cursor-not-allowed opacity-60">
              Applications closed
            </button>
          ) : opportunity.applicationUrl ? (
            <a href={opportunity.applicationUrl} target="_blank" rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-6 inline-flex">
              Apply now
            </a>
          ) : null}
        </div>
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          {opportunity.shortDescription && <p className="text-lg leading-relaxed text-charcoal-600">{opportunity.shortDescription}</p>}

          <ArticleContent blocks={opportunity.description} />

          {(opportunity.eligibility || opportunity.eligibilityNotes || opportunity.careerStage) && (
            <div className="mt-8 border-t border-taupe-200 pt-8">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Eligibility</h2>
              {opportunity.eligibility && <p className="mt-3 text-base text-charcoal-600">{opportunity.eligibility}</p>}
              {opportunity.careerStage && <p className="mt-2 text-sm text-charcoal-600"><span className="font-semibold">Career stage:</span> {opportunity.careerStage}</p>}
              {opportunity.eligibilityNotes && <p className="mt-2 text-sm text-charcoal-600">{opportunity.eligibilityNotes}</p>}
            </div>
          )}

          {(opportunity.applicationInstructions || opportunity.applicationUrl) && !opportunity.isClosed && (
            <div className="mt-8 border border-taupe-200 bg-cream p-5">
              <p className="text-sm font-semibold text-charcoal">How to apply</p>
              {opportunity.applicationInstructions && <p className="mt-1 text-sm text-charcoal-600">{opportunity.applicationInstructions}</p>}
              {opportunity.applicationUrl && (
                <a href={opportunity.applicationUrl} target="_blank" rel="noreferrer" onClick={handleApplyClick} className="btn-primary mt-4 inline-flex">
                  Apply now
                </a>
              )}
            </div>
          )}
        </div>

        {opportunity.organizationSlug && (
          <aside>
            <div className="border border-taupe-200 p-5">
              <p className="eyebrow mb-3">About {opportunity.organization}</p>
              <Link to={`/organizations/${opportunity.organizationSlug}`} className="font-serif text-lg font-semibold text-charcoal hover:text-burgundy-600">
                View provider profile &rarr;
              </Link>
            </div>
          </aside>
        )}
      </div>

      {more.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">More {opportunity.type ? opportunity.type.toLowerCase() : 'opportunities'}</p>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
            {more.map((o) => (
              <OpportunityCard key={o.id} opportunity={o} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
