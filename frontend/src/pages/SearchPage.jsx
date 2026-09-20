import { useEffect, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Search as SearchIcon } from 'lucide-react'
import { globalSearch } from '../api/search'
import { resolveImage } from '../utils/media'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

const TYPES = [
  { key: 'all', label: 'All' },
  { key: 'articles', label: 'Stories' },
  { key: 'people', label: 'People' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'opportunities', label: 'Opportunities' },
  { key: 'events', label: 'Events' },
  { key: 'resources', label: 'Resources' },
  { key: 'organizations', label: 'Organizations' },
]

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const query = params.get('q') || ''
  const type = params.get('type') || 'all'
  const [inputValue, setInputValue] = useState(query)
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setInputValue(query)
    if (!query) {
      setResults({ query: '', results: [] })
      return
    }
    setLoading(true)
    globalSearch(query, type).then((data) => {
      setResults(data)
      setLoading(false)
    })
  }, [query, type])

  useSeo({
    title: query ? `Search: ${query} | Women Shaping Futures` : 'Search | Women Shaping Futures',
    description: 'Search articles, people, jobs, opportunities, events, and resources on Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/search',
    robots: 'noindex, follow',
  })

  function handleSubmit(e) {
    e.preventDefault()
    setParams({ q: inputValue, type })
  }

  return (
    <div>
      <PageHeader eyebrow="Search" title="Search Women Shaping Futures">
        <form onSubmit={handleSubmit} className="mt-6 flex max-w-xl items-center gap-3 border-b-2 border-charcoal pb-3">
          <SearchIcon size={20} className="shrink-0 text-charcoal-600" />
          <input
            type="search"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search stories, people, jobs, opportunities…"
            className="w-full bg-transparent font-serif text-lg text-charcoal placeholder:text-charcoal-600/50 focus:outline-none"
          />
        </form>
        <div className="mt-5 flex flex-wrap gap-2">
          {TYPES.map((t) => (
            <button
              key={t.key}
              type="button"
              onClick={() => setParams({ q: query, type: t.key })}
              className={`px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                type === t.key ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600 hover:bg-taupe-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
      </PageHeader>

      <div className="container-editorial py-14">
        {!query && <EmptyState title="Search across the entire platform" description="Try 'leadership', 'fintech', or a name like 'Naliaka Wafula'." />}
        {query && loading && <PageLoader />}
        {query && !loading && results && (
          <>
            <p className="mb-6 text-sm text-charcoal-600">
              {results.results.length} result{results.results.length === 1 ? '' : 's'} for &ldquo;{query}&rdquo;
            </p>
            {results.results.length ? (
              <div className="divide-y divide-taupe-200">
                {results.results.map((r, i) => (
                  <Link key={i} to={r.url} className="group flex items-center gap-4 py-4">
                    {r.image && <img src={resolveImage(r.image, { width: 160, height: 160 })} alt="" width={64} height={64} className="h-16 w-16 shrink-0 object-cover" loading="lazy" />}
                    <div>
                      <span className="eyebrow">{r.resultType}</span>
                      <h3 className="mt-0.5 font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{r.title}</h3>
                      <p className="line-clamp-1 text-sm text-charcoal-600">{r.excerpt}</p>
                    </div>
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState title="No results found" description="Try a different search term or browse our sections from the navigation." />
            )}
          </>
        )}
      </div>
    </div>
  )
}
