import { useEffect, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { fetchSavedItems } from '../api/saved'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import SaveButton from '../components/account/SaveButton'
import ArticleCard from '../components/cards/ArticleCard'
import JobCard from '../components/cards/JobCard'
import OpportunityCard from '../components/cards/OpportunityCard'
import ResourceCard from '../components/cards/ResourceCard'
import EventCard from '../components/cards/EventCard'
import LearningProgramCard from '../components/cards/LearningProgramCard'

const TABS = [
  { key: '', label: 'All' },
  { key: 'article', label: 'Stories' },
  { key: 'job', label: 'Jobs' },
  { key: 'opportunity', label: 'Opportunities' },
  { key: 'resource', label: 'Resources' },
  { key: 'event', label: 'Events' },
  { key: 'learning_program', label: 'Learning' },
]

const EMPTY_COPY = {
  '': 'You haven’t saved anything yet.',
  article: 'No saved stories yet.',
  job: 'No saved jobs yet.',
  opportunity: 'No saved opportunities yet.',
  resource: 'No saved resources yet.',
  event: 'No saved events yet.',
  learning_program: 'No saved learning programs yet.',
}

// Renders a saved item's underlying card as a plain sibling of SaveButton
// (never a descendant of the card's own <Link>) — see SaveButton's own
// docstring. Works identically whether the card's root is a <Link>
// (Job/Opportunity/Resource/Event/LearningProgram) or a plain <article>
// (ArticleCard), since the wrapper never looks inside the card.
function SavedItemCard({ item }) {
  const { contentType, contentId, content } = item
  if (!content) return null

  let card = null
  if (contentType === 'article') card = <ArticleCard article={content} />
  else if (contentType === 'job') card = <JobCard job={content} />
  else if (contentType === 'opportunity') card = <OpportunityCard opportunity={content} />
  else if (contentType === 'resource') card = <ResourceCard resource={content} />
  else if (contentType === 'event') card = <EventCard event={content} />
  else if (contentType === 'learning_program') card = <LearningProgramCard program={content} />
  if (!card) return null

  return (
    <div className="relative">
      {card}
      <div className="absolute right-2 top-2">
        <SaveButton
          contentType={contentType}
          contentId={contentId}
          className="inline-flex items-center gap-1.5 bg-ivory/95 px-2.5 py-1.5 text-xs font-medium text-charcoal-600 shadow-sm transition-colors hover:text-burgundy-600 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-500"
        />
      </div>
    </div>
  )
}

export default function AccountSavedPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)

  const [activeTab, setActiveTab] = useState('')
  const [page, setPage] = useState(1)
  const [retryCount, setRetryCount] = useState(0)
  const [items, setItems] = useState(null)
  const [counts, setCounts] = useState({})
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useSeo({ title: 'Saved for later | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!accessToken) return undefined
    let cancelled = false
    fetchSavedItems({ type: activeTab || undefined, page, perPage: 12 })
      .then((result) => {
        if (cancelled) return
        setItems(result.items)
        setCounts(result.counts)
        setPagination(result.pagination)
        setError(null)
      })
      .catch(() => {
        if (!cancelled) setError('We couldn’t load your saved items. Please try again.')
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, activeTab, page, retryCount])

  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  function handleTabChange(tabKey) {
    setActiveTab(tabKey)
    setPage(1)
    setItems(null)
  }

  function handleRetry() {
    setItems(null)
    setError(null)
    setRetryCount((n) => n + 1)
  }

  return (
    <div className="container-editorial max-w-5xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">Saved for later</h1>
      <p className="mt-2 max-w-xl text-sm text-charcoal-600">
        Your personal collection of stories, opportunities and resources to return to.
      </p>

      <div className="mt-8 flex flex-wrap gap-2 border-b border-taupe-200 pb-4">
        {TABS.map((tab) => {
          const count = tab.key ? counts[tab.key] : Object.values(counts).reduce((sum, n) => sum + n, 0)
          const active = activeTab === tab.key
          return (
            <button
              key={tab.key || 'all'}
              type="button"
              onClick={() => handleTabChange(tab.key)}
              aria-pressed={active}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                active ? 'bg-burgundy-600 text-ivory' : 'border border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600'
              }`}
            >
              {tab.label}
              {typeof count === 'number' && count > 0 ? ` (${count})` : ''}
            </button>
          )
        })}
      </div>

      <div className="mt-8">
        {error ? (
          <EmptyState
            title="Something went wrong"
            description={error}
            action={
              <button type="button" onClick={handleRetry} className="btn-secondary mt-4">
                Try again
              </button>
            }
          />
        ) : items === null ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-72 animate-pulse bg-taupe-100" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title={EMPTY_COPY[activeTab] || EMPTY_COPY['']}
            description="Explore WSF and save what speaks to you."
            action={
              <div className="mt-4 flex flex-wrap justify-center gap-4 text-sm font-semibold text-burgundy-600">
                <Link to="/" className="hover:underline">Browse stories</Link>
                <Link to="/opportunities" className="hover:underline">Explore opportunities</Link>
                <Link to="/jobs" className="hover:underline">Find jobs</Link>
              </div>
            }
          />
        ) : (
          <>
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {items.map((item) => (
                <SavedItemCard key={item.id} item={item} />
              ))}
            </div>

            {pagination && pagination.totalPages > 1 && (
              <div className="mt-10 flex items-center justify-center gap-4">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Previous
                </button>
                <span className="text-sm text-charcoal-600">
                  Page {pagination.page} of {pagination.totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= pagination.totalPages}
                  onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
