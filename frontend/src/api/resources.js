import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { resources, getResourceBySlug as findBySlug } from '../mock/resources'

export async function fetchResources(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/resources', { params })
    return data
  }
  let results = [...resources]
  if (params.topic) results = results.filter((r) => r.topicSlug === params.topic)
  if (params.type) results = results.filter((r) => r.type === params.type)
  if (params.premium === 'free') results = results.filter((r) => !r.isPremium)
  if (params.premium === 'premium') results = results.filter((r) => r.isPremium)
  return delay(paginate(results, params))
}

export async function fetchResourceBySlug(slug) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/resources/${slug}`)
    return data
  }
  return delay(findBySlug(slug) || null)
}
