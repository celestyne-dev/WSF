import { apiClient, USE_MOCK } from './client'
import { mapEvent } from './events'

// First-party WSF-managed event registration (see backend
// app/api/v1/event_registrations.py and the registration endpoints added
// to app/api/v1/events.py). Real-backend only in any meaningful sense —
// mock mode below is just enough of a no-op that a logged-out/demo
// session doesn't crash.
function mapRegistration(r) {
  if (!r) return null
  return {
    id: r.id,
    status: r.status,
    registeredAt: r.registered_at,
    cancelledAt: r.cancelled_at,
    attendedAt: r.attended_at,
    event: mapEvent(r.event),
  }
}

function mapAdminRegistration(r) {
  if (!r) return null
  return {
    id: r.id,
    status: r.status,
    registeredAt: r.registered_at,
    cancelledAt: r.cancelled_at,
    attendedAt: r.attended_at,
    attendeeName: r.attendee_name,
    attendeeEmail: r.attendee_email,
    attendeeCountry: r.attendee_country,
  }
}

export async function registerForEvent(eventId) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/event-registrations', { event_id: eventId })
    return { registered: !!data?.registered, registration: mapRegistration(data?.registration) }
  }
  return { registered: true, registration: null }
}

export async function checkEventRegistration(eventId) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/event-registrations/check', { params: { eventId } })
    return { registered: !!data?.registered, registration: mapRegistration(data?.registration) }
  }
  return { registered: false, registration: null }
}

// params: { status, when, page, perPage }
export async function fetchMyEventRegistrations(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/event-registrations/me', {
      params: { status: params.status, when: params.when, page: params.page, perPage: params.perPage },
    })
    return {
      items: (data.items || []).map(mapRegistration),
      pagination: data.pagination,
    }
  }
  return { items: [], pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 0 } }
}

export async function cancelEventRegistration(registrationId) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post(`/event-registrations/${registrationId}/cancel`)
    return mapRegistration(data?.registration)
  }
  return null
}

// --- Admin (events.manage) ---------------------------------------------

// params: { status, q, page, perPage }
// The backend nests pagination inside `data` (not the `meta=` kwarg) so the
// shared response interceptor's bare-array reshaping never fires and the
// counts/activeCount/capacity/available fields survive alongside items —
// see app/api/v1/events.py's EventRegistrationAdminListResource for why.
// Because that bypasses the interceptor, `data.pagination` still carries
// the backend's raw snake_case keys and needs the same manual camelCase
// mapping fetchSavedItems() applies in api/saved.js.
export async function fetchAdminEventRegistrations(eventId, params = {}) {
  const { data } = await apiClient.get(`/events/${eventId}/registrations`, {
    params: { status: params.status, q: params.q, page: params.page, perPage: params.perPage },
  })
  const pagination = data?.pagination || {}
  return {
    items: (data.items || []).map(mapAdminRegistration),
    counts: data.counts || {},
    activeCount: data.active_count,
    capacity: data.capacity,
    available: data.available,
    pagination: {
      page: pagination.page || 1,
      pageSize: pagination.per_page,
      totalItems: pagination.total || 0,
      totalPages: pagination.total_pages || 0,
    },
  }
}

export async function updateAdminEventRegistration(eventId, registrationId, updates) {
  const { data } = await apiClient.patch(`/events/${eventId}/registrations/${registrationId}`, updates)
  return mapAdminRegistration(data)
}

export async function exportEventRegistrations(eventId, eventSlug) {
  const response = await apiClient.get(`/events/${eventId}/registrations/export`, { responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `wsf-event-${eventSlug || eventId}-registrations-${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}
