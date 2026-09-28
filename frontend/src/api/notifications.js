import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'

// Admin Notifications & Work Queue — the internal CMS inbox (see backend
// app/models/notification.py / app/services/notifications.py). This is
// NOT a public/member notification system: every function here reads or
// mutates only the CURRENT user's own notification rows, mirroring the
// backend's implicit `recipient_user_id = current_user.id` scoping —
// there is deliberately no `recipientUserId` parameter anywhere.
//
// entity_type + entity_id is the ONLY addressing scheme a notification
// carries (never a persisted URL — see the backend model's own docstring
// on "no open redirects"). ENTITY_ROUTES below is this module's half of
// that contract: a small, hand-maintained map from entity_type to a real
// existing admin detail route. Keep this in sync with
// backend/app/models/notification.py's ENTITY_TYPES by hand — there is
// deliberately no shared codegen for a vocabulary this small.
const ENTITY_ROUTES = {
  article: (id) => `/admin/articles/${id}`,
  story_submission: (id) => `/admin/submissions/${id}`,
  nomination: (id) => `/admin/nominations/${id}`,
  contact_inquiry: (id) => `/admin/contact/${id}`,
  directory_submission: (id) => `/admin/directory/submissions/${id}`,
  mentorship_application: (id) => `/admin/mentorship/applications/${id}`,
  partnership: (id) => `/admin/partnerships/${id}`,
}

// Same hand-maintained relationship to backend NOTIFICATION_TYPES — used
// by AdminNotifications.jsx's type filter dropdown.
export const NOTIFICATION_TYPE_LABELS = {
  article_review_requested: 'Article review requested',
  article_approved: 'Article approved',
  story_submission_received: 'Story submission',
  nomination_received: 'Nomination',
  contact_inquiry_received: 'Contact inquiry',
  directory_submission_received: 'Directory submission',
  mentorship_application_received: 'Mentorship application',
  partnership_inquiry_received: 'Partnership inquiry',
}

// Resolves a notification to the real admin route it's about, or null when
// it carries no entity reference (or an entity_type this frontend doesn't
// recognize — never falls back to constructing a URL from raw input).
export function notificationLink(notification) {
  if (!notification?.entityType || notification.entityId == null) return null
  const build = ENTITY_ROUTES[notification.entityType]
  return build ? build(notification.entityId) : null
}

function mapNotification(n) {
  if (!n) return null
  return {
    id: n.id,
    notificationType: n.notification_type,
    title: n.title,
    message: n.message,
    entityType: n.entity_type ?? null,
    entityId: n.entity_id ?? null,
    priority: n.priority || 'normal',
    isRead: !!n.is_read,
    readAt: n.read_at ?? null,
    isArchived: !!n.is_archived,
    archivedAt: n.archived_at ?? null,
    createdAt: n.created_at,
  }
}

let _mockNotifications
async function loadMockNotifications() {
  if (!_mockNotifications) _mockNotifications = await import('../mock/notifications')
  return _mockNotifications
}

// filter: 'all' | 'unread' | 'needs_attention' | 'archived'
export async function fetchNotifications(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/notifications', {
      params: {
        filter: params.filter || undefined,
        type: params.type || undefined,
        priority: params.priority || undefined,
        page: params.page,
        pageSize: params.pageSize,
      },
    })
    return { items: (data.items || []).map(mapNotification), pagination: data.pagination }
  }
  const { notifications: rows } = await loadMockNotifications()
  let filtered = rows.filter((n) => (params.filter === 'archived' ? n.is_archived : !n.is_archived))
  if (params.filter === 'unread' || params.filter === 'needs_attention') {
    filtered = filtered.filter((n) => !n.is_read)
  }
  if (params.type) filtered = filtered.filter((n) => n.notification_type === params.type)
  if (params.priority) filtered = filtered.filter((n) => n.priority === params.priority)
  filtered = [...filtered].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
  const { items, pagination } = paginate(filtered, params)
  return { items: items.map(mapNotification), pagination }
}

export async function fetchUnreadCount() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/admin/notifications/unread-count')
    return data.count
  }
  const { notifications: rows } = await loadMockNotifications()
  return await delay(rows.filter((n) => !n.is_archived && !n.is_read).length, 60)
}

export async function markNotificationRead(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.patch(`/admin/notifications/${id}/read`)
    return mapNotification(data)
  }
  const { notifications: rows } = await loadMockNotifications()
  const row = rows.find((n) => n.id === id)
  if (row) {
    row.is_read = true
    row.read_at = new Date().toISOString()
  }
  return delay(mapNotification(row))
}

export async function markNotificationUnread(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.patch(`/admin/notifications/${id}/unread`)
    return mapNotification(data)
  }
  const { notifications: rows } = await loadMockNotifications()
  const row = rows.find((n) => n.id === id)
  if (row) {
    row.is_read = false
    row.read_at = null
  }
  return delay(mapNotification(row))
}

export async function archiveNotification(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.patch(`/admin/notifications/${id}/archive`)
    return mapNotification(data)
  }
  const { notifications: rows } = await loadMockNotifications()
  const row = rows.find((n) => n.id === id)
  if (row) {
    row.is_archived = true
    row.archived_at = new Date().toISOString()
  }
  return delay(mapNotification(row))
}

export async function markAllNotificationsRead() {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/admin/notifications/mark-all-read')
    return data.updated
  }
  const { notifications: rows } = await loadMockNotifications()
  let updated = 0
  const now = new Date().toISOString()
  for (const row of rows) {
    if (!row.is_archived && !row.is_read) {
      row.is_read = true
      row.read_at = now
      updated += 1
    }
  }
  return delay(updated, 60)
}
