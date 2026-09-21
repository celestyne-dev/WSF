import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { Calendar, Globe2, Award } from 'lucide-react'
import { fetchOpportunityBySlug, fetchOpportunities } from '../api/opportunities'
import { getCountryNames } from '../mock/geography'
import { formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import Tag from '../components/ui/Tag'
import OpportunityCard from '../components/cards/OpportunityCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

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

  useSeo(
    opportunity
      ? {
          title: `${opportunity.title} | Women Shaping Futures Opportunities`,
          description: opportunity.description,
          canonical: `https://womenshapingfutures.org/opportunities/${opportunity.slug}`,
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this opportunity" description={error} /></div>
  if (opportunity === undefined) return <PageLoader />
  if (opportunity === null) return <NotFoundPage />

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Opportunities', to: '/opportunities' }, { label: opportunity.title }]} />
          <div className="mt-6 flex flex-col gap-6 sm:flex-row sm:items-center">
            {opportunity.logo && (
              <MediaImage mediaPath={opportunity.logo} alt={opportunity.organization} width={160} height={160} aspect={1} className="h-20 w-20 border border-taupe-200 object-cover" />
            )}
            <div>
              <Tag tone="plum">{opportunity.type}</Tag>
              <h1 className="mt-3 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{opportunity.title}</h1>
              <p className="mt-1 text-lg font-medium text-charcoal-600">{opportunity.organization}</p>
            </div>
          </div>
          <div className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-charcoal-600">
            <span className="inline-flex items-center gap-1.5">
              <Calendar size={15} /> Deadline: {formatDate(opportunity.deadline)}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Globe2 size={15} /> {getCountryNames(opportunity.countriesEligible).join(', ')}
            </span>
            <span className="inline-flex items-center gap-1.5">
              <Award size={15} /> {opportunity.fundingValue}
            </span>
          </div>
          <a
            href={opportunity.applicationUrl}
            onClick={() => trackEvent('opportunity_apply_click', { opportunitySlug: opportunity.slug })}
            className="btn-primary mt-6 inline-flex"
          >
            Apply now
          </a>
        </div>
      </div>

      <div className="container-editorial max-w-reading py-14">
        <p className="text-lg leading-relaxed text-charcoal-600">{opportunity.description}</p>

        <h2 className="mt-8 font-serif text-xl font-semibold text-charcoal">Eligibility</h2>
        <p className="mt-3 text-base text-charcoal-600">{opportunity.eligibility}</p>

        <h2 className="mt-8 font-serif text-xl font-semibold text-charcoal">Location</h2>
        <p className="mt-3 text-base text-charcoal-600">{opportunity.location}</p>
      </div>

      {more.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">More {opportunity.type.toLowerCase()}s</p>
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
