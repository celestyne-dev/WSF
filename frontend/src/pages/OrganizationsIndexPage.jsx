import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchOrganizations } from '../api/taxonomies'
import { regionOptions } from '../api/geography'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import OrganizationCard from '../components/cards/OrganizationCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

const TYPE_OPTIONS = [
  { value: 'company', label: 'Company' },
  { value: 'nonprofit', label: 'Nonprofit' },
  { value: 'foundation', label: 'Foundation' },
  { value: 'government', label: 'Government' },
  { value: 'educational_institution', label: 'Educational institution' },
  { value: 'media_organization', label: 'Media organization' },
  { value: 'professional_association', label: 'Professional association' },
  { value: 'social_enterprise', label: 'Social enterprise' },
  { value: 'community_organization', label: 'Community organization' },
  { value: 'other', label: 'Other' },
]

export default function OrganizationsIndexPage() {
  const [query, setQuery] = useState('')
  const [region, setRegion] = useState('')
  const [type, setType] = useState('')
  const [organizations, setOrganizations] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Organizations | Women Shaping Futures',
    description: 'Companies, foundations, universities, and institutions in the Women Shaping Futures network.',
    canonical: 'https://womenshapingfutures.org/organizations',
  })

  useEffect(() => {
    let active = true
    setOrganizations(null)
    setError(null)
    fetchOrganizations({ query, region, type, pageSize: 100 })
      .then((res) => active && setOrganizations(res.items))
      .catch(() => active && setError('Something went wrong loading organizations. Please try again.'))
    return () => {
      active = false
    }
  }, [query, region, type])

  return (
    <div>
      <PageHeader eyebrow="Network" title="Organizations" description="Companies, foundations, and institutions hiring, funding, and partnering with women across our network." />
      <div className="container-editorial py-14">
        <div className="mb-8 flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Search
            <span className="flex min-w-[14rem] items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
              <Search size={15} className="shrink-0 text-charcoal-600" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search by name…"
                className="w-full text-sm font-normal normal-case text-charcoal focus:outline-none"
              />
            </span>
          </label>
          <FilterSelect label="Region" value={region} onChange={setRegion} options={regionOptions()} />
          <FilterSelect label="Type" value={type} onChange={setType} options={TYPE_OPTIONS} />
        </div>

        {error && <EmptyState title="Couldn't load organizations" description={error} />}
        {!error && organizations === null && <PageLoader />}
        {!error && organizations !== null && (
          organizations.length ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {organizations.map((org) => (
                <OrganizationCard key={org.id} organization={org} />
              ))}
            </div>
          ) : (
            <EmptyState title="No organizations match those filters yet" description="Try broadening your search." />
          )
        )}
      </div>
    </div>
  )
}
