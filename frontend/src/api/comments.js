import { apiClient } from './client'

// Article comments (backend app/api/v1/comments.py). Every call resolves to
// { success, data?, message?, code? } and never throws, so components can
// render inline, accessible error messages without try/catch.

function failure(err, fallback) {
  return { success: false, message: err?.apiError?.message || fallback, code: err?.apiError?.code }
}

async function call(fn, fallback) {
  try {
    const res = await fn()
    return { success: true, data: res.data, message: res.message }
  } catch (err) {
    return failure(err, fallback)
  }
}

const enc = encodeURIComponent

export function fetchArticleComments(slug) {
  return call(() => apiClient.get(`/comments/article/${enc(slug)}`), 'Comments could not be loaded.')
}

export function fetchCommentForm(slug) {
  return call(() => apiClient.get(`/comments/article/${enc(slug)}/form`), 'Please reload the page and try again.')
}

// `website` is the honeypot: the form never fills it for a person.
export async function postComment(slug, { body, parentId, formToken, website }) {
  try {
    const res = await apiClient.post(`/comments/article/${enc(slug)}`, {
      body, parentId: parentId ?? undefined, formToken, website: website || '',
    })
    return { success: true, data: res.data }
  } catch (err) {
    return failure(err, 'Your comment could not be posted. Please try again.')
  }
}

export function editComment(id, body) {
  return call(() => apiClient.patch(`/comments/${id}`, { body }), 'Your edit could not be saved.')
}

export function deleteComment(id) {
  return call(() => apiClient.delete(`/comments/${id}`), 'Your comment could not be deleted.')
}

export function reportComment(id, { reason, details }) {
  return call(() => apiClient.post(`/comments/${id}/report`, { reason, details: details || undefined }),
    'Your report could not be sent.')
}

export function setReplyEmails(enabled) {
  return call(() => apiClient.put('/comments/notifications', { replyEmails: enabled }),
    'Your email preference could not be saved.')
}

export function unsubscribeReplyEmails(token) {
  return call(() => apiClient.post('/comments/notifications/unsubscribe', { token }),
    'This unsubscribe link is invalid.')
}

// --- Studio moderation -----------------------------------------------------

export function fetchModerationQueue({ queue = 'pending', page = 1 } = {}) {
  return call(() => apiClient.get('/admin/comments', { params: { queue, page } }), 'The queue could not be loaded.')
}

export function fetchModerationComment(id) {
  return call(() => apiClient.get(`/admin/comments/${id}`), 'This comment could not be loaded.')
}

export function moderateComment(id, action, reason) {
  return call(() => apiClient.post(`/admin/comments/${id}/${action}`, reason ? { reason } : {}),
    'That action could not be completed.')
}

export function restrictCommenter(userId, { kind, days, reason }) {
  return call(() => apiClient.post(`/admin/comments/users/${userId}/restrict`, { kind, days, reason }),
    'The restriction could not be saved.')
}

export function liftCommenterRestriction(userId) {
  return call(() => apiClient.post(`/admin/comments/users/${userId}/lift`), 'The restriction could not be lifted.')
}
