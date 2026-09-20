import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { events, getEventBySlug as findBySlug } from '../mock/events'

export async function fetchEvents(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/events', { params })
    return data
  }
  let results = [...events]
  if (params.format) results = results.filter((e) => e.format === params.format)
  if (params.type) results = results.filter((e) => e.type === params.type)
  results.sort((a, b) => new Date(a.date) - new Date(b.date))
  return delay(paginate(results, params))
}

export async function fetchEventBySlug(slug) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/events/${slug}`)
    return data
  }
  return delay(findBySlug(slug) || null)
}
