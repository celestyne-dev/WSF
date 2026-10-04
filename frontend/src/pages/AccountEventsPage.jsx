import { useEffect, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { fetchMyEventRegistrations, cancelEventRegistration, registerForEvent } from '../api/eventRegistrations'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import EventCard from '../components/cards/EventCard'
import { formatDate } from '../utils/format'

const TABS = [
  { key: 'upcoming', label: 'Upcoming' },
  { key: 'past', label: 'Past' },
  { key: 'cancelled', label: 'Cancelled' },
]

const EMPTY_COPY = {
  upcoming: "You don't have any upcoming events.",
  past: "You haven't attended any events yet.",
  cancelled: 'No cancelled registrations.',
}

function statusLabel(status) {
  if (status === 'cancelled') return 'Cancelled'
  if (status === 'attended') return 'Attended'
  return 'Registered'
}

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

// A registration's own card is rendered as a sibling of this status/
// action footer, never a descendant — EventCard's root is a <Link>, so
// Cancel/Join-online/Register-again controls live outside it entirely
// (see SaveButton's own docstring for the same reasoning on other
// content types' cards).
function RegistrationRow({ item, onCancel, onReregister, busy }) {
  const event = item.event
  if (!event) return null

  const canCancelSelf = item.status !== 'cancelled' && !event.isPast
  const canReregister =
    item.status === 'cancelled' &&
    event.registrationRequired &&
    event.registrationMode === 'wsf' &&
    !event.isPast &&
    !event.isCancelled &&
    !event.isPostponed &&
    !event.registrationFull &&
    (!event.registrationDeadline || event.registrationDeadline >= todayIso())
  // Circle entitlement lapsed (spec section S) — the registration row and
  // its history stay exactly as-is; only "Join online" is withheld, and
  // only while the registration is otherwise active. Cancel remains the
  // learner's own action regardless of current Circle access.
  const circleAccessLapsed =
    event.accessType === 'circle_only' &&
    item.status !== 'cancelled' &&
    item.canAccessEvent === false &&
    item.accessReason === 'circle_required'
  const canJoinOnline = !circleAccessLapsed && (item.status === 'registered' || item.status === 'attended') && event.virtualLink

  return (
    <div>
      <EventCard event={event} />
      <div className="flex flex-wrap items-center justify-between gap-3 border border-t-0 border-taupe-200 bg-cream px-4 py-3 text-xs text-charcoal-600">
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={`font-semibold ${
              item.status === 'cancelled' ? 'text-charcoal-600/70' : item.status === 'attended' ? 'text-emerald-700' : 'text-burgundy-600'
            }`}
          >
            {statusLabel(item.status)}
          </span>
          {item.status !== 'cancelled' && item.registeredAt && <span>Registered {formatDate(item.registeredAt)}</span>}
          {item.status === 'cancelled' && item.cancelledAt && <span>Cancelled {formatDate(item.cancelledAt)}</span>}
          {event.isCancelled && <span className="font-semibold text-rose-600">Event cancelled</span>}
          {event.isPostponed && <span className="font-semibold text-amber-700">Event postponed</span>}
          {circleAccessLapsed && <span className="font-semibold text-rose-600">Your WSF Circle access is currently inactive.</span>}
        </div>
        <div className="flex items-center gap-3">
          {circleAccessLapsed && (
            <Link to="/circle" className="font-semibold text-burgundy-600 hover:underline">
              Explore WSF Circle
            </Link>
          )}
          {canJoinOnline && (
            <a href={event.virtualLink} target="_blank" rel="noreferrer" className="font-semibold text-burgundy-600 hover:underline">
              Join online
            </a>
          )}
          {canCancelSelf && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onCancel(item.id)}
              className="font-semibold text-charcoal-600 hover:text-burgundy-600 disabled:opacity-60"
            >
              Cancel registration
            </button>
          )}
          {canReregister && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onReregister(event.id)}
              className="font-semibold text-burgundy-600 hover:underline disabled:opacity-60"
            >
              Register again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function AccountEventsPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)

  const [activeTab, setActiveTab] = useState('upcoming')
  const [page, setPage] = useState(1)
  const [retryCount, setRetryCount] = useState(0)
  const [items, setItems] = useState(null)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const [busyKey, setBusyKey] = useState(null)

  useSeo({ title: 'My Events | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!accessToken) return undefined
    let cancelled = false
    const params =
      activeTab === 'cancelled' ? { status: 'cancelled', page, perPage: 10 } : { when: activeTab, page, perPage: 10 }
    fetchMyEventRegistrations(params)
      .then((result) => {
        if (cancelled) return
        setItems(result.items)
        setPagination(result.pagination)
        setError(null)
      })
      .catch(() => {
        if (!cancelled) setError('We couldn’t load your events. Please try again.')
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

  async function handleCancel(registrationId) {
    setBusyKey(registrationId)
    try {
      await cancelEventRegistration(registrationId)
      toast.success('Registration cancelled.')
      setRetryCount((n) => n + 1)
    } catch {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setBusyKey(null)
    }
  }

  async function handleReregister(eventId) {
    setBusyKey(eventId)
    try {
      await registerForEvent(eventId)
      toast.success("You're registered again!")
      setRetryCount((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setBusyKey(null)
    }
  }

  return (
    <div className="container-editorial max-w-4xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">My Events</h1>
      <p className="mt-2 max-w-xl text-sm text-charcoal-600">Events you've registered for with Women Shaping Futures.</p>

      <div className="mt-8 flex flex-wrap gap-2 border-b border-taupe-200 pb-4">
        {TABS.map((tab) => {
          const active = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => handleTabChange(tab.key)}
              aria-pressed={active}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                active ? 'bg-burgundy-600 text-ivory' : 'border border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600'
              }`}
            >
              {tab.label}
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
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-28 animate-pulse bg-taupe-100" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title={EMPTY_COPY[activeTab]}
            description="Explore WSF events and register for one that speaks to you."
            action={
              <Link to="/events" className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
                Browse events
              </Link>
            }
          />
        ) : (
          <>
            <div className="space-y-6">
              {items.map((item) => (
                <RegistrationRow
                  key={item.id}
                  item={item}
                  onCancel={handleCancel}
                  onReregister={handleReregister}
                  busy={busyKey === item.id || busyKey === item.event?.id}
                />
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
