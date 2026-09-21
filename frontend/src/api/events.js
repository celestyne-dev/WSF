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
    description: e.description,
    type: e.type,
    format: e.format,
    date: e.date,
    startTime: e.start_time,
    endTime: e.end_time,
    timezone: e.timezone,
    location: e.location,
    countryCode: e.country?.code || e.country_code || null,
    country: e.country ? { code: e.country.code, name: e.country.name, region: e.country.region } : null,
    venue: e.venue,
    virtualLink: e.virtual_link,
    registrationUrl: e.registration_url,
    ticketPrice: e.ticket_price,
    currency: e.currency,
    capacity: e.capacity,
    speakers: (e.speakers || []).map((p) => p.slug),
    sponsors: (e.sponsors || []).map((o) => o.slug),
    agenda: e.agenda || [],
    status: e.status,
    coverImage: e.cover_media?.public_url || null,
    coverMedia: mapMediaRef(e.cover_media),
    featured: e.featured,
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
