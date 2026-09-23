import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchResources, fetchResourcesFilterOptions } from '../api/resources'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import ResourceCard from '../components/cards/ResourceCard'
import NewsletterForm from '../components/ui/NewsletterForm'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

export default function ResourcesPage() {
  const [query, setQuery] = useState('')
  const [type, setType] = useState('')
  const [free, setFree] = useState('')
  const [types, setTypes] = useState([])
  const [featured, setFeatured] = useState(null)
  const [latest, setLatest] = useState(null)
  const [popular, setPopular] = useState(null)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const isFiltering = !!(query || type || free)

  useSeo({
    title: 'Resource Library | Women Shaping Futures',
    description: 'Guides, workbooks, templates, and toolkits to help you plan your career, negotiate pay, and grow a business — free and premium.',
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
    Promise.all([
      fetchResources({ featured: 'true', pageSize: 4 }),
      fetchResources({ pageSize: 8 }),
    ])
      .then(([featuredRes, latestRes]) => {
        if (!active) return
        setFeatured(featuredRes.items)
        setLatest(latestRes.items)
        setPopular([...latestRes.items].sort((a, b) => (b.downloadCount || 0) - (a.downloadCount || 0)).slice(0, 4))
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!isFiltering) {
      setResults(null)
      return
    }
    let active = true
    setError(null)
    fetchResources({ type, free, q: query, pageSize: 100 })
      .then((res) => active && setResults(res.items))
      .catch(() => active && setError('Something went wrong loading resources. Please try again.'))
    return () => {
      active = false
    }
  }, [type, free, query, isFiltering])

  return (
    <div>
      <PageHeader
        eyebrow="Resource Library"
        title="Guides, Workbooks & Toolkits Built for Your Next Move"
        description="Practical tools from our editors and career coaches — career planning, negotiation, leadership, and business, free and premium."
      />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-center gap-3 border-b border-taupe-200 pb-8">
          <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2.5">
            <Search size={16} className="text-charcoal-600" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search resources…"
              className="w-full min-w-0 text-sm focus:outline-none sm:w-56"
            />
          </div>
          <FilterSelect label="Type" value={type} onChange={setType} options={types} />
          <FilterSelect label="Access" value={free} onChange={setFree} options={[{ value: 'true', label: 'Free' }, { value: 'false', label: 'Premium' }]} />
        </div>

        {isFiltering ? (
          <div className="mt-8">
            {error && <EmptyState title="Couldn't load resources" description={error} />}
            {!error && results === null && <PageLoader />}
            {!error && results !== null && (
              results.length ? (
                <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
                  {results.map((r) => (
                    <ResourceCard key={r.id} resource={r} />
                  ))}
                </div>
              ) : (
                <EmptyState title="No resources match those filters" description="Try a different search term or clear your filters." />
              )
            )}
          </div>
        ) : (
          <>
            {featured === null ? (
              <div className="mt-8">
                <PageLoader />
              </div>
            ) : (
              <>
                {featured.length > 0 && (
                  <section className="mt-12">
                    <h2 className="font-serif text-2xl font-semibold text-charcoal">Featured</h2>
                    <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
                      {featured.map((r) => (
                        <ResourceCard key={r.id} resource={r} />
                      ))}
                    </div>
                  </section>
                )}

                {popular?.length > 0 && (
                  <section className="mt-14 border-t border-taupe-200 pt-12">
                    <h2 className="font-serif text-2xl font-semibold text-charcoal">Most downloaded</h2>
                    <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
                      {popular.map((r) => (
                        <ResourceCard key={r.id} resource={r} />
                      ))}
                    </div>
                  </section>
                )}

                {latest?.length > 0 && (
                  <section className="mt-14 border-t border-taupe-200 pt-12">
                    <h2 className="font-serif text-2xl font-semibold text-charcoal">Latest resources</h2>
                    <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
                      {latest.map((r) => (
                        <ResourceCard key={r.id} resource={r} />
                      ))}
                    </div>
                  </section>
                )}

                {featured.length === 0 && !latest?.length && (
                  <div className="mt-8">
                    <EmptyState title="No resources published yet" description="Check back soon." />
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      <section className="border-t border-taupe-200 bg-charcoal py-16 text-ivory sm:py-20">
        <div className="container-editorial flex flex-col items-center text-center">
          <p className="eyebrow !text-blush-200">Never miss a new resource</p>
          <h2 className="mt-3 max-w-xl font-serif text-3xl font-semibold sm:text-4xl">Get new guides and toolkits in your inbox</h2>
          <div className="mt-7">
            <NewsletterForm variant="dark" source="resources_page" />
          </div>
        </div>
      </section>
    </div>
  )
}
