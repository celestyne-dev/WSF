import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { Bell } from 'lucide-react'
import { fetchNotifications, fetchUnreadCount, markNotificationRead, notificationLink } from '../../api/notifications'
import { formatRelativeTime } from '../../utils/format'

// Admin-only work-queue bell — not a public notification system (see
// backend/app/models/notification.py's module docstring). Deliberately
// modest polling (60s, unread count only) rather than a WebSocket/SSE
// connection — see task spec's "no aggressive polling, no WebSockets".
const POLL_MS = 60000

export default function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [unreadCount, setUnreadCount] = useState(0)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const containerRef = useRef(null)
  const navigate = useNavigate()

  const refreshUnreadCount = useCallback(async () => {
    try {
      const count = await fetchUnreadCount()
      setUnreadCount(count)
    } catch {
      // A failed background refresh should never surface an error UI for
      // something this ambient — the next poll (or opening the dropdown)
      // will simply try again.
    }
  }, [])

  useEffect(() => {
    refreshUnreadCount()
    const interval = setInterval(refreshUnreadCount, POLL_MS)
    return () => clearInterval(interval)
  }, [refreshUnreadCount])

  useEffect(() => {
    if (!open) return undefined
    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) setOpen(false)
    }
    function handleEscape(event) {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEscape)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEscape)
    }
  }, [open])

  async function toggleOpen() {
    const next = !open
    setOpen(next)
    if (next) {
      setLoading(true)
      try {
        const { items: latest } = await fetchNotifications({ filter: 'all', page: 1, pageSize: 5 })
        setItems(latest)
      } finally {
        setLoading(false)
      }
    }
  }

  async function handleSelect(notification) {
    setOpen(false)
    if (!notification.isRead) {
      setUnreadCount((n) => Math.max(0, n - 1))
      markNotificationRead(notification.id).catch(() => {})
    }
    const link = notificationLink(notification)
    navigate(link || '/admin/notifications')
  }

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggleOpen}
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : 'Notifications'}
        aria-expanded={open}
        className="relative flex h-9 w-9 items-center justify-center border border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600"
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span
            aria-hidden="true"
            className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-burgundy-600 px-1 text-[10px] font-semibold text-white"
          >
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Notifications"
          className="absolute right-0 z-30 mt-2 w-80 border border-taupe-300 bg-white shadow-lg"
        >
          <div className="flex items-center justify-between border-b border-taupe-200 px-4 py-2.5">
            <p className="text-sm font-semibold text-charcoal">Notifications</p>
          </div>
          <div className="max-h-96 overflow-y-auto">
            {loading && <p className="px-4 py-6 text-center text-sm text-charcoal-600">Loading…</p>}
            {!loading && items.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-charcoal-600">You're all caught up.</p>
            )}
            {!loading &&
              items.map((notification) => (
                <button
                  key={notification.id}
                  type="button"
                  role="menuitem"
                  onClick={() => handleSelect(notification)}
                  className={`flex w-full flex-col gap-0.5 border-b border-taupe-100 px-4 py-2.5 text-left text-sm hover:bg-taupe-50 ${
                    notification.isRead ? '' : 'bg-blush-50'
                  }`}
                >
                  <span className="flex items-center gap-1.5 font-medium text-charcoal">
                    {!notification.isRead && (
                      <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-burgundy-600" />
                    )}
                    {notification.title}
                  </span>
                  <span className="text-xs text-charcoal-600">{notification.message}</span>
                  <span className="text-[11px] text-charcoal-400">{formatRelativeTime(notification.createdAt)}</span>
                </button>
              ))}
          </div>
          <Link
            to="/admin/notifications"
            onClick={() => setOpen(false)}
            className="block border-t border-taupe-200 px-4 py-2.5 text-center text-sm font-semibold text-burgundy-600 hover:bg-taupe-50"
          >
            View all notifications
          </Link>
        </div>
      )}
    </div>
  )
}
