import { useEffect, useRef, useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { Search as SearchIcon } from 'lucide-react'
import { globalSearch, SEARCH_TYPES } from '../api/search'
import { fetchTopics } from '../api/taxonomies'
import { fetchCountries } from '../api/geography'
import { trackEvent } from '../utils/analytics'
import { resolveImage } from '../utils/media'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

// Any query this short can't return a useful count of results; the backend
// rejects it with a 422 too, but showing that as a validation hint (not a
// generic error) is friendlier than round-tripping to find out.
const MIN_QUERY_LENGTH = 2

export default function SearchPage() {
  const [params, setParams] = useSearchParams()
  const query = params.get('q') || ''
  const type = params.get('type') || 'all'
  const topic = params.get('topic') || ''
  const country = params.get('country') || ''
  const remote = params.get('remote') === 'true'
  const page = Math.max(1, parseInt(params.get('page') || '1', 10) || 1)

  const [inputValue, setInputValue] = useState(query)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [topicOptions, setTopicOptions] = useState([])
  const [countryOptions, setCountryOptions] = useState([])
  const requestId = useRef(0)

  useEffect(() => {
    setInputValue(query)
  }, [query])

  useEffect(() => {
    fetchTopics()
      .then((items) => setTopicOptions(items.map((t) => ({ value: t.slug, label: t.name }))))
      .catch(() => {})
    fetchCountries()
      .then((items) => setCountryOptions(items.map((c) => ({ value: c.code, label: c.name }))))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!query || query.trim().length < MIN_QUERY_LENGTH) {
      setData({ results: [], pagination: { page: 1, total: 0, totalPages: 0 } })
      setError(null)
      return
    }
    const id = ++requestId.current
    setLoading(true)
    setError(null)
    globalSearch(query, { type, page, topic: topic || undefined, country: country || undefined, remote: remote || undefined })
      .then((res) => {
        if (id !== requestId.current) return
        setData(res)
        setLoading(false)
        trackEvent('search_performed', { query, type, resultCount: res.pagination.total })
      })
      .catch(() => {
        if (id !== requestId.current) return
        setError('We couldn’t complete that search. Please try again.')
        setLoading(false)
      })
  }, [query, type, page, topic, country, remote])

  useSeo({
    title: query ? `Search: ${query} | Women Shaping Futures` : 'Search | Women Shaping Futures',
    description: 'Search stories, people, jobs, opportunities, events, resources, and more on Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/search',
    robots: 'noindex, follow',
  })

  function updateParams(next) {
    const merged = { q: query, type, ...next }
    const cleaned = {}
    Object.entries(merged).forEach(([k, v]) => {
      if (v) cleaned[k] = String(v)
    })
    setParams(cleaned)
  }

  function handleSubmit(e) {
    e.preventDefault()
    updateParams({ q: inputValue.trim(), page: undefined })
  }

  function handleTypeChange(nextType) {
    updateParams({ type: nextType, page: undefined })
  }

  function handleClearFilters() {
    setParams({ q: query, type: 'all' })
  }

  function handleResultClick(result) {
    trackEvent('search_result_click', { query, resultType: result.resultTypeKey, title: result.title }, { entityType: result.resultTypeKey })
  }

  const hasFilters = Boolean(topic || country || remote) || type !== 'all'
  const results = data?.results || []
  const pagination = data?.pagination || { page: 1, total: 0, totalPages: 0 }
  const tooShort = query && query.trim().length > 0 && query.trim().length < MIN_QUERY_LENGTH

  return (
    <div>
      <PageHeader eyebrow="Search" title="Search Women Shaping Futures">
        <form onSubmit={handleSubmit} className="mt-6 flex max-w-xl items-center gap-3 border-b-2 border-charcoal pb-3" role="search">
          <SearchIcon size={20} className="shrink-0 text-charcoal-600" aria-hidden="true" />
          <label htmlFor="search-input" className="sr-only">
            Search Women Shaping Futures
          </label>
          <input
            id="search-input"
            type="search"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Search stories, people, jobs, opportunities…"
            className="w-full bg-transparent font-serif text-lg text-charcoal placeholder:text-charcoal-600/50 focus:outline-none"
          />
          <button type="submit" className="btn-primary !px-4 !py-2 text-xs">
            Search
          </button>
        </form>
        <div className="mt-5 flex flex-wrap gap-2" role="tablist" aria-label="Filter results by type">
          {SEARCH_TYPES.map((t) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={type === t.key}
              onClick={() => handleTypeChange(t.key)}
              className={`px-3 py-1.5 text-xs font-semibold uppercase tracking-wide transition-colors ${
                type === t.key ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600 hover:bg-taupe-200'
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap items-end gap-3">
          <FilterSelect label="Topic" value={topic} onChange={(v) => updateParams({ topic: v, page: undefined })} options={topicOptions} />
          <FilterSelect label="Country" value={country} onChange={(v) => updateParams({ country: v, page: undefined })} options={countryOptions} />
          <label className="flex items-center gap-2 pb-2 text-sm text-charcoal-600">
            <input
              type="checkbox"
              checked={remote}
              onChange={(e) => updateParams({ remote: e.target.checked ? 'true' : undefined, page: undefined })}
            />
            Remote / Global only
          </label>
          {hasFilters && (
            <button type="button" onClick={handleClearFilters} className="pb-2 text-xs font-semibold uppercase tracking-wide text-burgundy-600 underline">
              Clear filters
            </button>
          )}
        </div>
      </PageHeader>

      <div className="container-editorial py-14">
        {!query && <EmptyState title="Search across the entire platform" description="Try 'leadership', 'fintech', or a name like 'Naliaka Wafula'." />}

        {tooShort && <EmptyState title="Keep typing…" description={`Enter at least ${MIN_QUERY_LENGTH} characters to search.`} />}

        {query && !tooShort && error && <EmptyState title="Something went wrong" description={error} />}

        {query && !tooShort && !error && loading && <PageLoader />}

        {query && !tooShort && !error && !loading && data && (
          <>
            <p className="mb-6 text-sm text-charcoal-600" role="status" aria-live="polite">
              {pagination.total} result{pagination.total === 1 ? '' : 's'} for &ldquo;{query}&rdquo;
            </p>
            {results.length ? (
              <>
                <div className="divide-y divide-taupe-200">
                  {results.map((r, i) => (
                    <Link key={`${r.resultTypeKey}-${i}`} to={r.url} onClick={() => handleResultClick(r)} className="group flex items-center gap-4 py-4">
                      {r.image ? (
                        <img
                          src={resolveImage(r.image, { width: 160, height: 160 })}
                          alt=""
                          width={64}
                          height={64}
                          className="h-16 w-16 shrink-0 object-cover"
                          loading="lazy"
                        />
                      ) : (
                        <div className="h-16 w-16 shrink-0 bg-taupe-100" aria-hidden="true" />
                      )}
                      <div>
                        <span className="eyebrow">{r.resultType}</span>
                        <h3 className="mt-0.5 font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{r.title}</h3>
                        <p className="line-clamp-1 text-sm text-charcoal-600">{r.excerpt}</p>
                      </div>
                    </Link>
                  ))}
                </div>
                {pagination.totalPages > 1 && (
                  <div className="mt-8 flex items-center justify-center gap-4">
                    <button
                      type="button"
                      disabled={pagination.page <= 1}
                      onClick={() => updateParams({ page: pagination.page - 1 })}
                      className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                    >
                      Previous
                    </button>
                    <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                      Page {pagination.page} of {pagination.totalPages}
                    </span>
                    <button
                      type="button"
                      disabled={pagination.page >= pagination.totalPages}
                      onClick={() => updateParams({ page: pagination.page + 1 })}
                      className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-40"
                    >
                      Next
                    </button>
                  </div>
                )}
              </>
            ) : (
              <EmptyState
                title="No results found"
                description={hasFilters ? 'Try clearing a filter, or search a broader term.' : 'Try a different search term or browse our sections from the navigation.'}
              />
            )}
          </>
        )}
      </div>
    </div>
  )
}
