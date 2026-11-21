import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchOpportunities, fetchOpportunityFilterOptions } from '../api/opportunities'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import ListingFilters from '../components/ui/ListingFilters'
import OpportunityCard from '../components/cards/OpportunityCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import ListingNewsletterCta from '../components/newsletter/ListingNewsletterCta'

const CANONICAL = 'https://womenshapingfutures.org/opportunities'
const FUNDING_LABELS = { fully_funded: 'Fully funded', partially_funded: 'Partially funded', stipend: 'Stipend', unpaid: 'Unpaid', not_applicable: 'Not applicable' }

// The server decides what is listed (backend listing_lifecycle.py): "Open"
// returns only currently open opportunities; "Upcoming" only published ones
// whose opening date is still ahead. Closed opportunities are never returned
// here, so there is no client-side "hide closed" filter.
export default function OpportunitiesListingPage() {
  const [tab, setTab] = useState('open')
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const [careerStage, setCareerStage] = useState('')
  const [fundingType, setFundingType] = useState('')
  const [closingSoon, setClosingSoon] = useState(false)
  const [opportunities, setOpportunities] = useState(null)
  const [options, setOptions] = useState({ types: [], countries: [], regions: [], careerStages: [], fundingTypes: [] })
  const [error, setError] = useState(null)

  useSeo({
    title: 'Opportunities | Women Shaping Futures',
    description: 'Scholarships, fellowships, grants, and accelerators for women worldwide.',
    canonical: CANONICAL,
  })
  useBreadcrumbStructuredData([{ label: 'Opportunities' }], CANONICAL)

  useEffect(() => {
    let active = true
    fetchOpportunityFilterOptions()
      .then((data) => active && setOptions((o) => ({ ...o, ...data })))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    const params = {
      scope: 'public', query, type, country, region, careerStage: careerStage || undefined, fundingType: fundingType || undefined,
      state: tab === 'upcoming' ? 'upcoming' : undefined, closingSoon: tab === 'open' && closingSoon ? 'true' : undefined, pageSize: 100,
    }
    fetchOpportunities(params)
      .then((res) => {
        if (!active) return
        setError(null)
        setOpportunities(res.items)
      })
      .catch(() => active && setError('Something went wrong loading opportunities. Please try again.'))
    return () => {
      active = false
    }
  }, [tab, query, type, country, region, careerStage, fundingType, closingSoon])

  const activeCount = [type, country, region, careerStage, fundingType, closingSoon].filter(Boolean).length
  const tabClass = (key) =>
    `rounded-control px-4 py-2 text-sm font-semibold transition-colors ${tab === key ? 'bg-charcoal text-ivory' : 'text-charcoal-600 hover:text-charcoal'}`

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Opportunities" description="Fellowships, scholarships, grants, accelerators and more, reviewed by our editorial team. Only opportunities that are open now are listed." />
      <div className="container-editorial py-10">
        <div role="tablist" aria-label="Opportunity status" className="mb-6 inline-flex gap-1 rounded-control border border-taupe-200 bg-white p-1">
          <button type="button" role="tab" aria-selected={tab === 'open'} onClick={() => setTab('open')} className={tabClass('open')}>Open now</button>
          <button type="button" role="tab" aria-selected={tab === 'upcoming'} onClick={() => setTab('upcoming')} className={tabClass('upcoming')}>Opening soon</button>
        </div>
        <ListingFilters
          activeCount={activeCount}
          search={
            <div className="rounded-control flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
              <Search size={15} className="text-charcoal-600" aria-hidden="true" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search opportunities…" aria-label="Search opportunities" className="w-44 text-sm focus:outline-none sm:w-52" />
            </div>
          }
        >
          <FilterSelect label="Type" value={type} onChange={setType} options={options.types} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Eligible country" value={country} onChange={setCountry} options={options.countries} />
          {options.careerStages.length > 0 && <FilterSelect label="Career stage" value={careerStage} onChange={setCareerStage} options={options.careerStages} />}
          {options.fundingTypes.length > 0 && (
            <FilterSelect label="Funding" value={fundingType} onChange={setFundingType} options={options.fundingTypes.map((v) => ({ value: v, label: FUNDING_LABELS[v] || v }))} />
          )}
          {tab === 'open' && (
            <label className="flex items-center gap-2 pb-2 text-sm text-charcoal-700">
              <input type="checkbox" checked={closingSoon} onChange={(e) => setClosingSoon(e.target.checked)} /> Closing within 7 days
            </label>
          )}
        </ListingFilters>

        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load opportunities" description={error} />
          </div>
        )}
        {!error && opportunities === null && <PageLoader />}
        {!error && opportunities !== null && (
          opportunities.length ? (
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {opportunities.map((o) => (
                <OpportunityCard key={o.id} opportunity={o} />
              ))}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState title={tab === 'upcoming' ? 'No upcoming opportunities right now' : 'No open opportunities match those filters'} />
            </div>
          )
        )}
        <ListingNewsletterCta placement="opportunities-listing" />
      </div>
    </div>
  )
}
