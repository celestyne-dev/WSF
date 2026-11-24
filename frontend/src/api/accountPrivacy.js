import { apiClient } from './client'

// Self-service export/deletion and privacy requests (backend
// app/api/v1/account_privacy.py). Calls resolve to { success, ... } and
// never throw, so pages can show inline, accessible messages.

function failure(err, fallback) {
  return { success: false, message: err?.apiError?.message || fallback, code: err?.apiError?.code }
}

// Downloads the member's JSON export (a file, not page data).
export async function downloadAccountExport() {
  try {
    const response = await apiClient.get('/account/export', { responseType: 'blob' })
    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/json' }))
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `wsf-account-data-${new Date().toISOString().slice(0, 10)}.json`)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
    return { success: true }
  } catch (err) {
    if (err?.response?.status === 429) return { success: false, message: 'You’ve downloaded your data several times recently. Please try again later.' }
    return failure(err, 'Your data could not be prepared. Please try again.')
  }
}

export async function requestAccountDeletion({ password, removeComments }) {
  try {
    const { data } = await apiClient.post('/account/deletion', { password, removeComments }, { withCredentials: true })
    return { success: true, scheduledFor: data.deletion_scheduled_for }
  } catch (err) {
    return failure(err, 'Deletion could not be scheduled.')
  }
}

export async function cancelDeletionWithLoginToken(token) {
  try {
    await apiClient.post('/account/deletion/cancel', { token })
    return { success: true }
  } catch (err) {
    return failure(err, 'The deletion could not be cancelled. Please sign in again.')
  }
}

export async function cancelDeletionWithLink(token) {
  try {
    await apiClient.post('/account/deletion/cancel-link', { token })
    return { success: true }
  } catch (err) {
    return failure(err, 'This link isn’t valid any more.')
  }
}

export async function submitPrivacyRequest({ requestType, details }) {
  try {
    const { data } = await apiClient.post('/account/privacy-requests', { requestType, details })
    return { success: true, dueAt: data.dueAt }
  } catch (err) {
    return failure(err, 'Your request could not be sent.')
  }
}

// --- Studio ---------------------------------------------------------------

export async function fetchPrivacyRequests(params = {}) {
  try {
    const { data } = await apiClient.get('/admin/privacy-requests', { params })
    return { success: true, items: data.items }
  } catch (err) {
    return failure(err, 'Privacy requests could not be loaded.')
  }
}

export async function createPrivacyRequest(payload) {
  try {
    const { data } = await apiClient.post('/admin/privacy-requests', payload)
    return { success: true, item: data }
  } catch (err) {
    return failure(err, 'The request could not be saved.')
  }
}

export async function updatePrivacyRequest(id, payload) {
  try {
    const { data } = await apiClient.patch(`/admin/privacy-requests/${id}`, payload)
    return { success: true, item: data }
  } catch (err) {
    return failure(err, 'The request could not be updated.')
  }
}
