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
    capacity: e.capacity,
    speakers: (e.speakers || []).map((p) => p.slug),
    sponsors: (e.sponsors || []).map((o) => o.slug),
    agenda: e.agenda || [],
    status: e.status,
    isPast: e.is_past ?? false,
    isUpcoming: e.is_upcoming ?? true,
    isCancelled: e.is_cancelled ?? false,
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
    }
  }
  const { events } = await loadMockEvents()
  const enriched = events.map(attachMockCountry)
  return delay({
    types: [...new Set(events.map((e) => e.type))],
    formats: [...new Set(events.map((e) => e.format))],
    countries: countryOptionsFromItems(enriched),
    regions: regionFilterOptions(),
  })
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
    agenda: form.agenda || [],
    status: form.status || 'draft',
    seo: form.seo || undefined,
    coverMediaId: form.coverMedia?.id || undefined,
    featured: !!form.featured,
    sponsored: !!form.sponsored,
    speakerSlugs: form.speakerSlugs || [],
    sponsorSlugs: form.sponsorSlugs || [],
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
