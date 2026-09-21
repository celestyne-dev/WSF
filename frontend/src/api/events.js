import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { events, getEventBySlug as findBySlug } from '../mock/events'
import { countryFilterOptions, regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'

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
    featured: e.featured,
  }
}

export async function fetchEvents(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/events', { params })
    return { ...data, items: data.items.map(mapEvent) }
  }
  let results = [...events]
  if (params.format) results = results.filter((e) => e.format === params.format)
  if (params.type) results = results.filter((e) => e.type === params.type)
  if (params.country) results = results.filter((e) => matchesCountry(e.countryCode, params.country))
  if (params.region) results = results.filter((e) => matchesRegion(e.countryCode, params.region))
  results.sort((a, b) => new Date(a.date) - new Date(b.date))
  return delay(paginate(results, params))
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
  return delay(findBySlug(slug) || null)
}

export async function fetchEventsFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/events', { params: { pageSize: 100 } })
    const all = data.items.map(mapEvent)
    return {
      types: [...new Set(all.map((e) => e.type))].filter(Boolean),
      formats: [...new Set(all.map((e) => e.format))].filter(Boolean),
      countries: countryFilterOptions(all.map((e) => e.countryCode)),
      regions: regionFilterOptions(),
    }
  }
  return delay({
    types: [...new Set(events.map((e) => e.type))],
    formats: [...new Set(events.map((e) => e.format))],
    countries: countryFilterOptions(events.map((e) => e.countryCode)),
    regions: regionFilterOptions(),
  })
}
