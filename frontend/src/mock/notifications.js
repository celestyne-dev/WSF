// Mock-mode fixture for the Admin Notifications & Work Queue inbox (GET
// /api/v1/admin/notifications and friends) — shaped identically to the real
// backend's NotificationSchema dump (see backend/app/models/notification.py)
// so AdminNotifications.jsx and the header bell work the same whether
// VITE_USE_MOCK is true or false. A handful of representative rows only —
// this is a CMS work-queue inbox, not a dataset to exhaustively fixture.
export const notifications = [
  {
    id: 501,
    notification_type: 'story_submission_received',
    title: 'New story submission',
    message: 'A new story submission was received and is awaiting review.',
    entity_type: 'story_submission',
    entity_id: 214,
    priority: 'normal',
    is_read: false,
    read_at: null,
    is_archived: false,
    archived_at: null,
    created_at: '2026-09-28T08:12:00Z',
  },
  {
    id: 500,
    notification_type: 'article_review_requested',
    title: 'Article ready for review',
    message: 'An article was submitted for review.',
    entity_type: 'article',
    entity_id: 58,
    priority: 'normal',
    is_read: false,
    read_at: null,
    is_archived: false,
    archived_at: null,
    created_at: '2026-09-28T07:40:00Z',
  },
  {
    id: 499,
    notification_type: 'partnership_inquiry_received',
    title: 'New partnership inquiry',
    message: 'A new partnership inquiry was received.',
    entity_type: 'partnership',
    entity_id: 37,
    priority: 'normal',
    is_read: true,
    read_at: '2026-09-27T16:05:00Z',
    is_archived: false,
    archived_at: null,
    created_at: '2026-09-27T15:50:00Z',
  },
  {
    id: 498,
    notification_type: 'mentorship_application_received',
    title: 'New mentorship application',
    message: 'A new mentorship application was received.',
    entity_type: 'mentorship_application',
    entity_id: 82,
    priority: 'normal',
    is_read: true,
    read_at: '2026-09-26T11:00:00Z',
    is_archived: true,
    archived_at: '2026-09-26T11:02:00Z',
    created_at: '2026-09-26T09:30:00Z',
  },
]
