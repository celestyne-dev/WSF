import { useEffect, useState } from 'react'
import { fetchOpportunities, fetchOpportunityFilterOptions } from '../api/opportunities'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import OpportunityCard from '../components/cards/OpportunityCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

export default function OpportunitiesListingPage() {
  const [type, setType] = useState('')
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
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
    fetchOpportunities({ type, country, region, pageSize: 100 })
      .then((res) => active && setOpportunities(res.items))
      .catch(() => active && setError('Something went wrong loading opportunities. Please try again.'))
    return () => {
      active = false
    }
  }, [type, country, region])

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Opportunities" description="Fellowships, scholarships, grants, and accelerators — reviewed by our editorial team and sorted by deadline." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Type" value={type} onChange={setType} options={options.types} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Eligible Country" value={country} onChange={setCountry} options={options.countries} />
        </div>

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
              <EmptyState title="No opportunities match those filters" />
            </div>
          )
        )}
      </div>
    </div>
  )
}
