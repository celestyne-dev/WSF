import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Archive, CheckCheck } from 'lucide-react'
import {
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  archiveNotification,
  notificationLink,
  NOTIFICATION_TYPE_LABELS,
} from '../../api/notifications'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate, formatRelativeTime } from '../../utils/format'

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'unread', label: 'Unread' },
  { key: 'needs_attention', label: 'Needs Attention' },
  { key: 'archived', label: 'Archived' },
]

const EMPTY_COPY = {
  all: { title: "You're all caught up", description: 'Nothing has come through yet — new activity across the CMS will show up here.' },
  unread: { title: 'No unread notifications', description: "You've read everything in your inbox." },
  needs_attention: { title: 'Nothing needs your attention', description: 'Items you have not yet reviewed will show up here.' },
  archived: { title: 'No archived notifications', description: "Notifications you archive will be kept here — they're never deleted." },
}

function exactTimestamp(iso) {
  return formatDate(iso, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

export default function AdminNotifications() {
  const [statusFilter, setStatusFilter] = useState('all')
  const [typeFilter, setTypeFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [page, setPage] = useState(1)
  const [items, setItems] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const navigate = useNavigate()

  const load = useCallback(() => {
    let active = true
    setError(null)
    fetchNotifications({ filter: statusFilter, type: typeFilter || undefined, priority: priorityFilter || undefined, page, pageSize: 20 })
      .then((res) => {
        if (!active) return
        setItems(res.items)
        setPagination(res.pagination)
      })
      .catch(() => {
        if (!active) return
        setError('Something went wrong loading notifications. Please try again.')
      })
    return () => {
      active = false
    }
  }, [statusFilter, typeFilter, priorityFilter, page])

  useEffect(() => load(), [load])

  function changeFilter(key) {
    setStatusFilter(key)
    setPage(1)
  }

  async function handleOpen(notification) {
    if (!notification.isRead) {
      await markNotificationRead(notification.id).catch(() => {})
      setItems((rows) => rows.map((n) => (n.id === notification.id ? { ...n, isRead: true } : n)))
    }
    const link = notificationLink(notification)
    if (link) navigate(link)
  }

  async function handleArchive(event, notification) {
    event.stopPropagation()
    await archiveNotification(notification.id).catch(() => {})
    setItems((rows) => rows.filter((n) => n.id !== notification.id))
  }

  async function handleMarkAllRead() {
    await markAllNotificationsRead().catch(() => {})
    load()
  }

  return (
    <div>
      <AdminPageHeader
        title="Notifications"
        description="Your personal work queue — new activity across Articles, Story Submissions, Nominations, Contact, Directory, Mentorship, and Partnerships that needs your attention."
        actions={
          <button
            type="button"
            onClick={handleMarkAllRead}
            className="flex items-center gap-1.5 border border-taupe-300 px-3 py-2 text-sm font-semibold text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600"
          >
            <CheckCheck size={15} /> Mark all read
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5" role="group" aria-label="Filter notifications">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => changeFilter(f.key)}
              aria-pressed={statusFilter === f.key}
              className={`px-3 py-2 text-xs font-semibold ${
                statusFilter === f.key ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600 hover:bg-taupe-200'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>

        <label htmlFor="notif-type" className="sr-only">
          Notification type
        </label>
        <select
          id="notif-type"
          value={typeFilter}
          onChange={(e) => {
            setPage(1)
            setTypeFilter(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All types</option>
          {Object.entries(NOTIFICATION_TYPE_LABELS).map(([key, label]) => (
            <option key={key} value={key}>
              {label}
            </option>
          ))}
        </select>

        <label htmlFor="notif-priority" className="sr-only">
          Priority
        </label>
        <select
          id="notif-priority"
          value={priorityFilter}
          onChange={(e) => {
            setPage(1)
            setPriorityFilter(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All priorities</option>
          <option value="normal">Normal priority</option>
          <option value="high">High priority</option>
        </select>
      </div>

      {error && <EmptyState title="Couldn't load notifications" description={error} />}
      {!error && items === undefined && <PageLoader />}
      {!error && items !== undefined && (
        items.length ? (
          <ul className="divide-y divide-taupe-200 border border-taupe-200 bg-white">
            {items.map((notification) => (
              <li key={notification.id}>
                <div
                  role="button"
                  tabIndex={0}
                  onClick={() => handleOpen(notification)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      handleOpen(notification)
                    }
                  }}
                  className={`flex cursor-pointer items-start justify-between gap-4 px-4 py-3.5 hover:bg-taupe-50 ${
                    notification.isRead ? '' : 'bg-blush-50'
                  }`}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      {!notification.isRead && (
                        <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-burgundy-600" />
                      )}
                      <p className="font-semibold text-charcoal">{notification.title}</p>
                      {notification.priority === 'high' && (
                        <span className="flex items-center gap-1 bg-amber-100 px-1.5 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-amber-700">
                          <AlertTriangle size={11} aria-hidden="true" /> High priority
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-sm text-charcoal-600">{notification.message}</p>
                    <time
                      dateTime={notification.createdAt}
                      title={exactTimestamp(notification.createdAt)}
                      className="mt-1 block text-xs text-charcoal-400"
                    >
                      {formatRelativeTime(notification.createdAt)}
                    </time>
                  </div>
                  {!notification.isArchived && (
                    <button
                      type="button"
                      onClick={(e) => handleArchive(e, notification)}
                      aria-label="Archive notification"
                      className="flex h-8 w-8 shrink-0 items-center justify-center text-charcoal-400 hover:text-burgundy-600"
                    >
                      <Archive size={15} />
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState {...(EMPTY_COPY[statusFilter] || EMPTY_COPY.all)} />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
