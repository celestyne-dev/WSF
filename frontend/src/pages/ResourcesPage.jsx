import { useEffect, useState } from 'react'
import { fetchResources, fetchResourcesFilterOptions } from '../api/resources'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import ResourceCard from '../components/cards/ResourceCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

export default function ResourcesPage() {
  const [type, setType] = useState('')
  const [premium, setPremium] = useState('')
  const [resources, setResources] = useState(null)
  const [types, setTypes] = useState([])
  const [error, setError] = useState(null)

  useSeo({
    title: 'Resource Library | Women Shaping Futures',
    description: 'Guides, templates, and worksheets to help you plan your career, negotiate pay, and grow a business.',
    canonical: 'https://womenshapingfutures.org/resources',
  })

  useEffect(() => {
    let active = true
    fetchResourcesFilterOptions()
      .then((data) => active && setTypes(data.types))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchResources({ type, premium, pageSize: 100 })
      .then((res) => active && setResources(res.items))
      .catch(() => active && setError('Something went wrong loading resources. Please try again.'))
    return () => {
      active = false
    }
  }, [type, premium])

  return (
    <div>
      <PageHeader eyebrow="Resource Library" title="Guides, Templates & Worksheets" description="Practical tools built by our editors and career coaches — free and premium." />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <FilterSelect label="Type" value={type} onChange={setType} options={types} />
          <FilterSelect label="Access" value={premium} onChange={setPremium} options={['free', 'premium']} />
        </div>
        {error && (
          <div className="mt-8">
            <EmptyState title="Couldn't load resources" description={error} />
          </div>
        )}
        {!error && resources === null && <PageLoader />}
        {!error && resources !== null && (
          resources.length ? (
            <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {resources.map((r) => (
                <ResourceCard key={r.id} resource={r} />
              ))}
            </div>
          ) : (
            <div className="mt-8">
              <EmptyState title="No resources match those filters" />
            </div>
          )
        )}
      </div>
    </div>
  )
}
