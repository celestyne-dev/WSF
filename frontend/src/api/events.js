import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'
import { attachMockCountry, countryOptionsFromItems } from './geography'
import { mapMediaRef } from '../utils/media'

// The mock events dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockEvents
async function loadMockEvents() {
  if (!_mockEvents) _mockEvents = await import('../mock/events')
  return _mockEvents
}

function mapSpeaker(s) {
  if (!s) return null
  return {
    id: s.id,
    personSlug: s.person?.slug || null,
    name: s.person?.name || s.name || '',
    title: s.person?.title || s.title || '',
    organizationName: s.organization_name || '',
    bio: s.person?.short_bio || s.bio || '',
    headshot: mapMediaRef(s.person?.photo || s.headshot),
    profileSlug: s.person?.slug || null,
  }
}

function mapSponsor(s) {
  if (!s) return null
  return {
    id: s.id,
    organizationId: s.organization?.id || null,
    organizationSlug: s.organization?.slug || null,
    name: s.organization?.name || s.name || '',
    url: s.organization ? null : s.url || null,
    logo: mapMediaRef(s.organization?.logo || s.logo),
    tier: s.tier || '',
  }
}

function mapAgendaItem(item) {
  return {
    startTime: item.startTime,
    endTime: item.endTime || '',
    title: item.title,
    description: item.description || '',
    sessionType: item.sessionType || '',
    speakerNames: item.speakerNames || [],
  }
}

function mapEvent(e) {
  if (!e) return null
  return {
    id: e.id,
    slug: e.slug,
    title: e.title,
    shortDescription: e.short_description,
    description: Array.isArray(e.description) ? e.description : e.description ? [{ type: 'paragraph', text: e.description }] : [],
    type: e.type,
    format: e.format,
    date: e.date,
    endDate: e.end_date,
    startTime: e.start_time,
    endTime: e.end_time,
    timezone: e.timezone,
    location: e.location,
    address: e.address,
    city: e.city || '',
    countryCode: e.country?.code || e.country_code || null,
    country: e.country ? { code: e.country.code, name: e.country.name, region: e.country.region } : null,
    venue: e.venue,
    virtualLink: e.virtual_link,
    virtualLinkPublic: e.virtual_link_public ?? false,
    organizer: e.organizer?.name || e.organizer_name || null,
    organizerSlug: e.organizer?.slug || null,
    organizerId: e.organizer_id || e.organizer?.id || null,
    organizerLogo: e.organizer?.logo?.public_url || null,
    organizerLogoMedia: mapMediaRef(e.organizer?.logo),
    registrationUrl: e.registration_url,
    registrationRequired: e.registration_required ?? true,
    registrationDeadline: e.registration_deadline,
    registrationInstructions: e.registration_instructions,
    soldOut: e.sold_out ?? false,
    ticketPrice: e.ticket_price,
    currency: e.currency,
    isFree: e.is_free ?? !e.ticket_price,
    capacity: e.capacity,
    speakers: (e.speakers || []).map(mapSpeaker),
    sponsors: (e.sponsors || []).map(mapSponsor),
    agenda: (e.agenda || []).map(mapAgendaItem),
    status: e.status,
    isPast: e.is_past ?? false,
    isUpcoming: e.is_upcoming ?? true,
    isOngoing: e.is_ongoing ?? false,
    isCompleted: e.is_completed ?? false,
    isCancelled: e.is_cancelled ?? false,
    isPostponed: e.is_postponed ?? false,
    publishedDate: e.published_date,
    seo: e.seo || null,
    coverImage: e.cover_media?.public_url || null,
    coverMedia: mapMediaRef(e.cover_media),
    featured: e.featured,
    sponsored: e.sponsored,
  }
}

export async function fetchEvents(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/events', { params })
    return { ...data, items: data.items.map(mapEvent) }
  }
  const { events } = await loadMockEvents()
  let results = [...events]
  if (params.format) results = results.filter((e) => e.format === params.format)
  if (params.type) results = results.filter((e) => e.type === params.type)
  if (params.country) results = results.filter((e) => matchesCountry(e.countryCode, params.country))
  if (params.region) results = results.filter((e) => matchesRegion(e.countryCode, params.region))
  if (params.city) results = results.filter((e) => (e.city || '').toLowerCase().includes(params.city.toLowerCase()))
  if (params.organizer) results = results.filter((e) => e.organizerSlug === params.organizer)
  if (params.featured === 'true' || params.featured === true) results = results.filter((e) => e.featured)
  if (params.dateFrom) results = results.filter((e) => e.date >= params.dateFrom)
  if (params.dateTo) results = results.filter((e) => e.date <= params.dateTo)
  if (params.price === 'free') results = results.filter((e) => !e.ticketPrice)
  else if (params.price === 'paid') results = results.filter((e) => e.ticketPrice)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((e) => e.title.toLowerCase().includes(q))
  }
  const today = new Date().toISOString().slice(0, 10)
  if (params.when === 'past') results = results.filter((e) => (e.endDate || e.date) < today)
  else if (params.when === 'upcoming' || params.when === undefined) results = results.filter((e) => (e.endDate || e.date) >= today)
  results.sort((a, b) => new Date(a.date) - new Date(b.date))
  const page = paginate(results, params)
  return delay({ ...page, items: page.items.map(attachMockCountry) })
}

export async function fetchEventBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/events/${slug}`)
      return mapEvent(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getEventBySlug } = await loadMockEvents()
  return delay(attachMockCountry(getEventBySlug(slug)))
}

export async function fetchEventsFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/events', { params: { pageSize: 100 } })
    const all = data.items.map(mapEvent)
    return {
      types: [...new Set(all.map((e) => e.type))].filter(Boolean),
      formats: [...new Set(all.map((e) => e.format))].filter(Boolean),
      countries: countryOptionsFromItems(all),
      regions: regionFilterOptions(),
      organizers: [...new Map(all.filter((e) => e.organizerSlug).map((e) => [e.organizerSlug, { value: e.organizerSlug, label: e.organizer }])).values()],
    }
  }
  const { events } = await loadMockEvents()
  const enriched = events.map(attachMockCountry)
  return delay({
    types: [...new Set(events.map((e) => e.type))],
    formats: [...new Set(events.map((e) => e.format))],
    countries: countryOptionsFromItems(enriched),
    regions: regionFilterOptions(),
    organizers: [],
  })
}

function toSpeakerPayload(s) {
  return {
    personSlug: s.personSlug || undefined,
    name: s.personSlug ? undefined : s.name || undefined,
    title: s.title || undefined,
    organizationName: s.organizationName || undefined,
    bio: s.bio || undefined,
    headshotMediaId: s.headshot?.id || undefined,
  }
}

function toSponsorPayload(s) {
  return {
    organizationId: s.organizationId || undefined,
    name: s.organizationId ? undefined : s.name || undefined,
    logoMediaId: s.organizationId ? undefined : s.logo?.id || undefined,
    url: s.organizationId ? undefined : s.url || undefined,
    tier: s.tier || undefined,
  }
}

function toAgendaPayload(item) {
  return {
    startTime: item.startTime,
    endTime: item.endTime || undefined,
    title: item.title,
    description: item.description || undefined,
    sessionType: item.sessionType || undefined,
    speakerNames: item.speakerNames || [],
  }
}

function toApiPayload(form) {
  return {
    title: form.title,
    slug: form.slug || undefined,
    shortDescription: form.shortDescription || undefined,
    description: form.description || [],
    type: form.type || undefined,
    format: form.format || undefined,
    date: form.date || undefined,
    endDate: form.endDate || undefined,
    startTime: form.startTime || undefined,
    endTime: form.endTime || undefined,
    timezone: form.timezone || undefined,
    location: form.location || undefined,
    address: form.address || undefined,
    city: form.city || undefined,
    countryCode: form.countryCode || undefined,
    venue: form.venue || undefined,
    virtualLink: form.virtualLink || undefined,
    virtualLinkPublic: !!form.virtualLinkPublic,
    organizerId: form.organizerId || undefined,
    organizerName: form.organizerName || undefined,
    registrationUrl: form.registrationUrl || undefined,
    registrationRequired: form.registrationRequired !== false,
    registrationDeadline: form.registrationDeadline || undefined,
    registrationInstructions: form.registrationInstructions || undefined,
    soldOut: !!form.soldOut,
    ticketPrice: form.ticketPrice === '' || form.ticketPrice == null ? undefined : Number(form.ticketPrice),
    currency: form.currency || undefined,
    capacity: form.capacity === '' || form.capacity == null ? undefined : Number(form.capacity),
    agenda: (form.agenda || []).map(toAgendaPayload),
    status: form.status || 'draft',
    seo: form.seo || undefined,
    coverMediaId: form.coverMedia?.id || undefined,
    featured: !!form.featured,
    sponsored: !!form.sponsored,
    speakers: (form.speakers || []).map(toSpeakerPayload),
    sponsors: (form.sponsors || []).map(toSponsorPayload),
  }
}

export async function createEvent(form) {
  const { data } = await apiClient.post('/events', toApiPayload(form))
  return mapEvent(data)
}

export async function updateEvent(slug, form) {
  const { data } = await apiClient.put(`/events/${slug}`, toApiPayload(form))
  return mapEvent(data)
}

export async function deleteEvent(slug) {
  await apiClient.delete(`/events/${slug}`)
}
