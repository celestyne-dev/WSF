import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'

// The mock partnerships dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockAdmin
async function loadMockAdmin() {
  if (!_mockAdmin) _mockAdmin = await import('../mock/admin')
  return _mockAdmin
}

function mapNote(n) {
  if (!n) return null
  return {
    id: n.id,
    body: n.body,
    user: n.user ? { id: n.user.id, name: n.user.full_name, email: n.user.email } : null,
    createdAt: n.created_at,
  }
}

export function mapPartnership(p) {
  if (!p) return null
  return {
    id: p.id,
    contactName: p.contact_name,
    email: p.email,
    phone: p.phone || '',
    jobTitle: p.job_title || '',
    company: p.company,
    website: p.website || '',
    country: p.country ? { code: p.country.code, name: p.country.name } : null,
    countryCode: p.country?.code || null,
    organization: p.organization ? { id: p.organization.id, slug: p.organization.slug, name: p.organization.name } : null,
    organizationSlug: p.organization?.slug || null,
    partnershipType: p.partnership_type || '',
    subject: p.subject || '',
    message: p.message || '',
    goals: p.goals || '',
    proposedTiming: p.proposed_timing || '',
    budgetRange: p.budget_range || '',
    status: p.status || 'new',
    assignedTo: p.assigned_to ? { id: p.assigned_to.id, name: p.assigned_to.full_name, email: p.assigned_to.email } : null,
    assignedToId: p.assigned_to?.id || null,
    estimatedValue: p.estimated_value ?? null,
    currency: p.currency || '',
    commercialNotes: p.commercial_notes || '',
    proposedStartDate: p.proposed_start_date || null,
    proposedEndDate: p.proposed_end_date || null,
    actualStartDate: p.actual_start_date || null,
    actualEndDate: p.actual_end_date || null,
    notes: Array.isArray(p.notes) ? p.notes.map(mapNote) : [],
    submittedAt: p.submitted_at || null,
    updatedAt: p.updated_at || null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function submitPartnershipInquiry(payload) {
  const body = {
    contactName: payload.contactName,
    email: payload.email,
    phone: payload.phone || undefined,
    jobTitle: payload.jobTitle || undefined,
    company: payload.company,
    website: payload.website || undefined,
    countryCode: payload.countryCode || undefined,
    partnershipType: payload.partnershipType || undefined,
    subject: payload.subject || undefined,
    message: payload.message || undefined,
    goals: payload.goals || undefined,
    proposedTiming: payload.proposedTiming || undefined,
    budgetRange: payload.budgetRange || undefined,
    consentGiven: !!payload.consentGiven,
    acquisition: payload.acquisition || undefined,
  }
  if (!USE_MOCK) {
    try {
      await apiClient.post('/partnerships/inquiries', body)
      return { success: true, message: 'Thank you for your partnership inquiry. Our team has received it.' }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: 'Thank you for your partnership inquiry. Our team has received it.' }, 500)
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export async function fetchPartnerships(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/partnerships/inquiries', { params })
    return { ...data, items: data.items.map(mapPartnership) }
  }
  const { partnershipInquiries } = await loadMockAdmin()
  let results = partnershipInquiries.map((p) => ({
    id: p.id,
    contact_name: p.contactName,
    email: p.email,
    company: p.company,
    subject: p.interest,
    message: p.message,
    status: p.status,
    submitted_at: p.submittedAt,
    notes: [],
  }))
  if (params.status) results = results.filter((p) => p.status === params.status)
  if (params.q) {
    const q = params.q.toLowerCase()
    results = results.filter((p) => p.company.toLowerCase().includes(q) || p.contact_name.toLowerCase().includes(q) || p.email.toLowerCase().includes(q))
  }
  const page = paginate(results.map(mapPartnership), params)
  return delay(page)
}

export async function fetchPartnership(id) {
  const { data } = await apiClient.get(`/partnerships/inquiries/${id}`)
  return mapPartnership(data)
}

export async function updatePartnership(id, payload) {
  const { data } = await apiClient.patch(`/partnerships/inquiries/${id}`, {
    contactName: payload.contactName,
    email: payload.email,
    phone: payload.phone || undefined,
    jobTitle: payload.jobTitle || undefined,
    company: payload.company,
    website: payload.website || undefined,
    countryCode: payload.countryCode || undefined,
    partnershipType: payload.partnershipType || undefined,
    subject: payload.subject || undefined,
    message: payload.message || undefined,
    goals: payload.goals || undefined,
    proposedTiming: payload.proposedTiming || undefined,
    budgetRange: payload.budgetRange || undefined,
    estimatedValue: payload.estimatedValue === '' || payload.estimatedValue == null ? undefined : Number(payload.estimatedValue),
    currency: payload.currency || undefined,
    commercialNotes: payload.commercialNotes || undefined,
    proposedStartDate: payload.proposedStartDate || undefined,
    proposedEndDate: payload.proposedEndDate || undefined,
    actualStartDate: payload.actualStartDate || undefined,
    actualEndDate: payload.actualEndDate || undefined,
  })
  return mapPartnership(data)
}

export async function updatePartnershipStatus(id, status) {
  const { data } = await apiClient.patch(`/partnerships/inquiries/${id}/status`, { status })
  return mapPartnership(data)
}

export async function assignPartnership(id, assignedToId) {
  const { data } = await apiClient.post(`/partnerships/inquiries/${id}/assign`, { assignedToId: assignedToId || undefined })
  return mapPartnership(data)
}

export async function linkPartnershipOrganization(id, organizationSlug) {
  const { data } = await apiClient.post(`/partnerships/inquiries/${id}/organization`, { organizationSlug: organizationSlug || undefined })
  return mapPartnership(data)
}

export async function addPartnershipNote(id, body) {
  const { data } = await apiClient.post(`/partnerships/inquiries/${id}/notes`, { body })
  return mapPartnership(data)
}

export async function archivePartnership(id) {
  const { data } = await apiClient.post(`/partnerships/inquiries/${id}/archive`)
  return mapPartnership(data)
}

export async function fetchPartnershipHistory(id) {
  const { data } = await apiClient.get(`/partnerships/inquiries/${id}/history`)
  return data
}

export async function fetchPartnershipOverview() {
  const { data } = await apiClient.get('/partnerships/overview')
  return {
    newInquiries: data.newInquiries,
    underReview: data.underReview,
    active: data.active,
    completed: data.completed,
  }
}

// Triggers a browser download of the CSV export.
export async function exportPartnerships(params = {}) {
  const response = await apiClient.get('/partnerships/inquiries/export', { params, responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `partnership-inquiries-${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
