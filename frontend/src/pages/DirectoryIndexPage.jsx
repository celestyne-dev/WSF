import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchDirectoryListings, fetchDirectoryCategories } from '../api/directory'
import { regionOptions } from '../api/geography'
import { DIRECTORY_OWNERSHIP_CLASSIFICATIONS, DIRECTORY_OWNERSHIP_LABELS } from '../constants/directory'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import DirectoryCard from '../components/cards/DirectoryCard'
import Pagination from '../components/ui/Pagination'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

const CLASSIFICATION_OPTIONS = DIRECTORY_OWNERSHIP_CLASSIFICATIONS.filter((c) => c !== 'unspecified').map((c) => ({
  value: c,
  label: DIRECTORY_OWNERSHIP_LABELS[c],
}))

export default function DirectoryIndexPage() {
  const [query, setQuery] = useState('')
  const [region, setRegion] = useState('')
  const [classification, setClassification] = useState('')
  const [category, setCategory] = useState('')
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [page, setPage] = useState(1)

  const [categories, setCategories] = useState([])
  const [listings, setListings] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Business & Professional Directory | Women Shaping Futures',
    description: 'Discover women-owned, women-led, and women-founded businesses and professional organizations in the Women Shaping Futures network.',
    canonical: 'https://womenshapingfutures.org/directory',
  })

  useEffect(() => {
    fetchDirectoryCategories().then(setCategories).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchDirectoryListings({
      query: query || undefined,
      region: region || undefined,
      classification: classification || undefined,
      category: category || undefined,
      remote: remoteOnly ? 'true' : undefined,
      page,
      pageSize: 12,
    })
      .then((res) => {
        if (!active) return
        setListings(res.items)
        setPagination(res.pagination)
      })
      .catch(() => active && setError('Something went wrong loading the directory. Please try again.'))
    return () => {
      active = false
    }
  }, [query, region, classification, category, remoteOnly, page])

  const featured = page === 1 ? (listings || []).filter((l) => l.isCurrentlyFeatured) : []
  const rest = page === 1 ? (listings || []).filter((l) => !l.isCurrentlyFeatured) : listings || []

  return (
    <div>
      <PageHeader
        eyebrow="Directory"
        title="Business & Professional Directory"
        description="Discover women-owned, women-led, and women-founded businesses and aligned professional organizations from around the world."
      >
        <Link to="/directory/submit" className="btn-primary mt-6 inline-flex !px-5 !py-2.5 text-sm">
          Submit your business
        </Link>
      </PageHeader>

      <div className="container-editorial py-14">
        <div className="mb-8 flex flex-wrap items-end gap-4 border-b border-taupe-200 pb-8">
          <label className="flex flex-col gap-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            Search
            <span className="flex min-w-[14rem] items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
              <Search size={15} className="shrink-0 text-charcoal-600" />
              <input
                value={query}
                onChange={(e) => {
                  setPage(1)
                  setQuery(e.target.value)
                }}
                placeholder="Search by name…"
                className="w-full text-sm font-normal normal-case text-charcoal focus:outline-none"
              />
            </span>
          </label>
          <FilterSelect
            label="Category"
            value={category}
            onChange={(v) => {
              setPage(1)
              setCategory(v)
            }}
            options={categories.map((c) => ({ value: c.slug, label: c.name }))}
          />
          <FilterSelect
            label="Region"
            value={region}
            onChange={(v) => {
              setPage(1)
              setRegion(v)
            }}
            options={regionOptions()}
          />
          <FilterSelect
            label="Classification"
            value={classification}
            onChange={(v) => {
              setPage(1)
              setClassification(v)
            }}
            options={CLASSIFICATION_OPTIONS}
          />
          <label className="flex items-center gap-2 pb-2 text-sm text-charcoal-600">
            <input
              type="checkbox"
              checked={remoteOnly}
              onChange={(e) => {
                setPage(1)
                setRemoteOnly(e.target.checked)
              }}
            />
            Remote / global only
          </label>
        </div>

        {error && <EmptyState title="Couldn't load the directory" description={error} />}
        {!error && listings === undefined && <PageLoader />}
        {!error && listings !== undefined && (
          listings.length ? (
            <div className="space-y-10">
              {featured.length > 0 && (
                <div>
                  <p className="eyebrow mb-5">Featured</p>
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {featured.map((l) => (
                      <DirectoryCard key={l.id} listing={l} />
                    ))}
                  </div>
                </div>
              )}
              <div>
                {featured.length > 0 && <p className="eyebrow mb-5">All listings</p>}
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  {rest.map((l) => (
                    <DirectoryCard key={l.id} listing={l} />
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <EmptyState title="No listings match those filters yet" description="Try broadening your search, or be the first to submit a business in this category." />
          )
        )}
        {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
      </div>
    </div>
  )
}
