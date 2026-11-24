// Pure helpers for article comments (UI rules mirror backend
// app/services/comments.py; the server always has the final say).

export const REPORT_REASONS = [
  { value: 'spam', label: 'Spam' },
  { value: 'harassment', label: 'Harassment' },
  { value: 'misinformation', label: 'Misinformation' },
  { value: 'other', label: 'Other' },
]

export const COMMENT_MAX_LENGTH = 5000

// Reply always targets a top-level comment: one level of replies only.
export function replyTargetId(comment) {
  return comment.parentId ?? comment.id
}

export function canEditNow(comment, now = Date.now()) {
  if (!comment?.editableUntil) return false
  return new Date(comment.editableUntil).getTime() > now
}

export function editMinutesLeft(comment, now = Date.now()) {
  if (!canEditNow(comment, now)) return 0
  return Math.max(1, Math.ceil((new Date(comment.editableUntil).getTime() - now) / 60000))
}

export function closedMessage(state) {
  if (state === 'off') return 'Comments are turned off for this article.'
  if (state === 'closed') return 'Comments are closed for this article.'
  if (state === 'disabled') return 'Comments are currently unavailable.'
  return null
}

export function restrictionMessage(restriction) {
  if (!restriction) return null
  if (restriction.kind === 'ban') return 'Your account can no longer take part in comments.'
  const until = restriction.endsAt ? new Date(restriction.endsAt) : null
  const when = until
    ? until.toLocaleString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', timeZone: 'UTC' }) + ' UTC'
    : 'further notice'
  return `Your commenting is suspended until ${when}.`
}

export function postResultMessage(status) {
  return status === 'published'
    ? 'Thanks! Your comment is published.'
    : 'Thanks! Your comment will appear once a moderator approves it.'
}

export function commentCountLabel(count) {
  if (!count) return 'Comments'
  return count === 1 ? '1 comment' : `${count} comments`
}

export const HELD_REASON_LABELS = {
  first_comment: 'First comments from this member',
  links: 'More than two links',
  blocked_words: 'Blocked word or phrase',
  reports: 'Hidden after reports',
  moderator: 'Hidden by a moderator',
}

export const HISTORY_LABELS = {
  created: 'Posted',
  edited: 'Edited by author',
  deleted_by_author: 'Deleted by author',
  reported: 'Reported',
  approved: 'Approved',
  restored: 'Restored',
  hidden: 'Hidden',
  auto_hidden: 'Hidden automatically (report threshold reached)',
  removed: 'Removed',
  user_suspended: 'Member suspended from comments',
  user_banned: 'Member banned from comments',
  user_restriction_lifted: 'Comment restriction lifted',
  body_erased: 'Text erased (retention period ended)',
}

export const MODERATION_QUEUES = [
  { value: 'pending', label: 'Pending' },
  { value: 'reported', label: 'Reported' },
  { value: 'hidden', label: 'Hidden' },
  { value: 'removed', label: 'Removed' },
  { value: 'published', label: 'Published' },
  { value: 'all', label: 'All' },
]

export const STATUS_LABELS = {
  pending: 'Awaiting approval',
  published: 'Published',
  hidden: 'Hidden',
  removed: 'Removed',
  deleted: 'Deleted by author',
}
