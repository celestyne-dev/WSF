import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchOpportunities, fetchOpportunityFilterOptions } from '../api/opportunities'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import OpportunityCard from '../components/cards/OpportunityCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

export default function OpportunitiesListingPage() {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const [hideClosed, setHideClosed] = useState(true)
  const [opportunities, setOpportunities] = useState(null)
  const [options, setOptions] = useState({ types: [], countries: [], regions: [] })
  const [error, setError] = useState(null)

  useSeo({
    title: 'Opportunities | Women Shaping Futures',
    description: 'Scholarships, fellowships, grants, and accelerators for women worldwide.',
    canonical: 'https://womenshapingfutures.org/opportunities',
  })

  useEffect(() => {
    let active = true
    fetchOpportunityFilterOptions()
      .then((data) => active && setOptions(data))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchOpportunities({ query, type, country, region, pageSize: 100 })
      .then((res) => active && setOpportunities(res.items))
      .catch(() => active && setError('Something went wrong loading opportunities. Please try again.'))
    return () => {
      active = false
    }
  }, [query, type, country, region])

  const visible = opportunities ? (hideClosed ? opportunities.filter((o) => !o.isClosed) : opportunities) : null

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Opportunities" description="Fellowships, scholarships, grants, and accelerators — reviewed by our editorial team and sorted by deadline." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
            <Search size={15} className="text-charcoal-600" />
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search opportunities…" className="w-52 text-sm focus:outline-none" />
          </div>
          <FilterSelect label="Type" value={type} onChange={setType} options={options.types} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Eligible Country" value={country} onChange={setCountry} options={options.countries} />
          <label className="flex items-center gap-2 pb-1 text-sm text-charcoal-600">
            <input type="checkbox" checked={hideClosed} onChange={(e) => setHideClosed(e.target.checked)} />
            Hide closed
          </label>
        </div>

        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load opportunities" description={error} />
          </div>
        )}
        {!error && visible === null && <PageLoader />}
        {!error && visible !== null && (
          visible.length ? (
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {visible.map((o) => (
                <OpportunityCard key={o.id} opportunity={o} />
              ))}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState title="No opportunities match those filters" />
            </div>
          )
        )}
      </div>
    </div>
  )
}
