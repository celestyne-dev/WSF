import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { articles, getArticleBySlug as findBySlug } from '../mock/articles'
import { RESERVED_SLUGS } from '../mock'

// GET /api/v1/articles?topic=&series=&author=&page=
export async function fetchArticles(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/articles', { params })
    return data
  }
  let results = articles.filter((a) => a.status === 'published')
  if (params.topic) results = results.filter((a) => a.topicSlugs.includes(params.topic))
  if (params.series) results = results.filter((a) => a.seriesSlug === params.series)
  if (params.author) results = results.filter((a) => a.authorSlug === params.author)
  if (params.category) results = results.filter((a) => a.categorySlug === params.category)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter(
      (a) => a.title.toLowerCase().includes(q) || a.excerpt.toLowerCase().includes(q),
    )
  }
  results = [...results].sort((a, b) => new Date(b.publishDate) - new Date(a.publishDate))
  return delay(paginate(results, params))
}

// GET /api/v1/articles/{slug} — flat public URL is /{slug}; reserved-slug
// protection lives here so the CMS and the SPA share one source of truth.
export async function fetchArticleBySlug(slug) {
  if (RESERVED_SLUGS.includes(slug)) return delay(null)
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/articles/${slug}`)
    return data
  }
  return delay(findBySlug(slug) || null)
}

export async function fetchRelatedArticles(slugs = []) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/articles/related', { slugs })
    return data
  }
  return delay(slugs.map((s) => findBySlug(s)).filter(Boolean))
}

export function isReservedSlug(slug) {
  return RESERVED_SLUGS.includes(slug)
}
