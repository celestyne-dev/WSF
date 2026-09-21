import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { resources, getResourceBySlug as findBySlug } from '../mock/resources'

function mapResource(r) {
  if (!r) return null
  return {
    id: r.id,
    slug: r.slug,
    name: r.name,
    description: r.description,
    coverImage: r.cover_media?.public_url || null,
    type: r.type,
    topicSlug: r.topic?.slug || null,
    authorSlug: r.author?.slug || null,
    price: r.price,
    currency: r.currency,
    isPremium: r.is_premium,
    isDownloadable: r.is_downloadable,
    isExternal: r.is_external,
    featured: r.featured,
  }
}

export async function fetchResources(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/resources', { params })
    return { ...data, items: data.items.map(mapResource) }
  }
  let results = [...resources]
  if (params.topic) results = results.filter((r) => r.topicSlug === params.topic)
  if (params.type) results = results.filter((r) => r.type === params.type)
  if (params.premium === 'free') results = results.filter((r) => !r.isPremium)
  if (params.premium === 'premium') results = results.filter((r) => r.isPremium)
  if (params.featured) results = results.filter((r) => r.featured)
  return delay(paginate(results, params))
}

export async function fetchResourceBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/resources/${slug}`)
      return mapResource(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  return delay(findBySlug(slug) || null)
}

export async function fetchResourcesFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/resources', { params: { pageSize: 100 } })
    const all = data.items.map(mapResource)
    return { types: [...new Set(all.map((r) => r.type))].filter(Boolean) }
  }
  return delay({ types: [...new Set(resources.map((r) => r.type))] })
}
