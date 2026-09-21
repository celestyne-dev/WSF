import { useState, useMemo } from 'react'
import { opportunities } from '../mock/opportunities'
import { getOpportunityFilterOptions } from '../api/opportunities'
import { matchesCountry, matchesRegion } from '../mock/geography'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import OpportunityCard from '../components/cards/OpportunityCard'
import EmptyState from '../components/ui/EmptyState'

export default function OpportunitiesListingPage() {
  const [type, setType] = useState('')
  const [country, setCountry] = useState('')
  const [region, setRegion] = useState('')
  const options = useMemo(() => getOpportunityFilterOptions(), [])

  useSeo({
    title: 'Opportunities | Women Shaping Futures',
    description: 'Scholarships, fellowships, grants, and accelerators for women worldwide.',
    canonical: 'https://womenshapingfutures.org/opportunities',
  })

  const filtered = opportunities.filter(
    (o) =>
      (!type || o.type === type) &&
      (!country || matchesCountry(o.countriesEligible, country)) &&
      (!region || matchesRegion(o.countriesEligible, region)),
  )

  return (
    <div>
      <PageHeader eyebrow="Opportunity" title="Opportunities" description="Fellowships, scholarships, grants, and accelerators — reviewed by our editorial team and sorted by deadline." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Type" value={type} onChange={setType} options={options.types} />
          <FilterSelect label="Region" value={region} onChange={setRegion} options={options.regions} />
          <FilterSelect label="Eligible Country" value={country} onChange={setCountry} options={options.countries} />
        </div>

        {filtered.length ? (
          <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((o) => (
              <OpportunityCard key={o.id} opportunity={o} />
            ))}
          </div>
        ) : (
          <div className="mt-8">
            <EmptyState title="No opportunities match those filters" />
          </div>
        )}
      </div>
    </div>
  )
}
