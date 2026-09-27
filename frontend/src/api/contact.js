import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

// GET/POST /api/v1/contact — a focused general-inquiry inbox (see backend
// app/api/v1/contact.py). Never a duplicate of Partnerships/Advertise/
// StorySubmission/Nomination — the public form's own inquiry-type list
// excludes those categories and the Contact page routes visitors there
// instead.

function mapStaffRef(u) {
  if (!u) return null
  return { id: u.id, fullName: u.full_name, email: u.email }
}

export function mapContactInquiryListItem(i) {
  if (!i) return null
  return {
    id: i.id,
    reference: i.reference || '',
    fullName: i.full_name || `${i.first_name || ''} ${i.last_name || ''}`.trim(),
    email: i.email || '',
    inquiryType: i.inquiry_type || 'general',
    subject: i.subject || '',
    status: i.status || 'new',
    assignedTo: mapStaffRef(i.assigned_to),
    createdAt: i.created_at || null,
  }
}

export function mapContactInquiry(i) {
  if (!i) return null
  return {
    id: i.id,
    reference: i.reference || '',
    firstName: i.first_name || '',
    lastName: i.last_name || '',
    fullName: i.full_name || `${i.first_name || ''} ${i.last_name || ''}`.trim(),
    email: i.email || '',
    inquiryType: i.inquiry_type || 'general',
    subject: i.subject || '',
    message: i.message || '',
    status: i.status || 'new',
    assignedTo: mapStaffRef(i.assigned_to),
    resolvedAt: i.resolved_at || null,
    resolvedBy: mapStaffRef(i.resolved_by),
    notes: Array.isArray(i.notes)
      ? i.notes.map((n) => ({ id: n.id, body: n.body, user: mapStaffRef(n.user), createdAt: n.created_at }))
      : [],
    createdAt: i.created_at || null,
    updatedAt: i.updated_at || null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

// A rough per-viewer honeypot/timing signal — never a real anti-spam
// engine (see backend module docstring). `startedAt` is set once when the
// form first mounts and read back here at submit time.
export async function submitContactInquiry(payload, startedAt) {
  const body = {
    firstName: payload.firstName,
    lastName: payload.lastName,
    email: payload.email,
    inquiryType: payload.inquiryType || 'general',
    subject: payload.subject,
    message: payload.message,
    privacyAcknowledged: payload.privacyAcknowledged,
    hpWebsite: payload.hpWebsite || '',
    elapsedMs: startedAt ? Date.now() - startedAt : undefined,
  }
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/contact', body)
      return {
        success: true,
        reference: data.reference,
        message: `Your message has been received (reference ${data.reference}). Our team reviews every inquiry inside the CMS.`,
      }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay(
    {
      success: true,
      reference: 'WSF-CON-2026-000001',
      message: 'Your message has been received (reference WSF-CON-2026-000001). Our team reviews every inquiry inside the CMS.',
    },
    500,
  )
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

const MOCK_INQUIRIES = []

export async function fetchContactInquiries(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/contact', {
      params: {
        status: params.status || undefined,
        inquiryType: params.inquiryType || undefined,
        assignedToUserId: params.assignedToUserId || undefined,
        dateFrom: params.dateFrom || undefined,
        dateTo: params.dateTo || undefined,
        q: params.query || undefined,
        page: params.page,
        pageSize: params.pageSize || 20,
      },
    })
    return { items: data.items.map(mapContactInquiryListItem), pagination: data.pagination }
  }
  return delay({ items: MOCK_INQUIRIES, pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 0 } })
}

export async function fetchContactInquiry(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/contact/${id}`)
    return mapContactInquiry(data)
  }
  return delay(null)
}

export async function updateContactInquiryStatus(id, status) {
  const { data } = await apiClient.patch(`/contact/${id}/status`, { status })
  return mapContactInquiry(data)
}

export async function assignContactInquiry(id, userId) {
  const { data } = await apiClient.post(`/contact/${id}/assign`, { userId: userId || null })
  return mapContactInquiry(data)
}

export async function addContactInquiryNote(id, body) {
  const { data } = await apiClient.post(`/contact/${id}/notes`, { body })
  return mapContactInquiry(data)
}
