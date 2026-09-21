import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { RESERVED_SLUGS } from '../constants/routes'
import { mapMediaRef } from '../utils/media'

// Mock article/author/topic datasets are only ever needed when
// VITE_USE_MOCK=true — dynamic-importing them here (instead of a static
// top-of-file import) keeps them out of the real-mode production bundle
// entirely; a real-mode build never executes this function, so the
// mock/* chunks it would pull in are never requested by the browser.
let _mockDeps
async function loadMockDeps() {
  if (!_mockDeps) {
    const [articlesMod, authorsMod, topicsMod] = await Promise.all([
      import('../mock/articles'),
      import('../mock/authors'),
      import('../mock/topics'),
    ])
    _mockDeps = {
      articles: articlesMod.articles,
      findBySlug: articlesMod.getArticleBySlug,
      getAuthorBySlug: authorsMod.getAuthorBySlug,
      getTopicBySlug: topicsMod.getTopicBySlug,
    }
  }
  return _mockDeps
}

// Mock articles only carry flat slug strings; attach the same nested
// author/topic shape the real API returns (see mapArticle) so shared
// components never need to know which mode is active.
async function enrichMockArticle(a) {
  if (!a) return null
  const { getAuthorBySlug, getTopicBySlug } = await loadMockDeps()
  return {
    ...a,
    author: getAuthorBySlug(a.authorSlug) || null,
    coAuthors: (a.coAuthorSlugs || []).map((s) => getAuthorBySlug(s)).filter(Boolean),
    topic: getTopicBySlug(a.topicSlugs?.[0]) || null,
  }
}

// The backend nests full objects (author, topics, hero_media, ...) instead
// of the mock's flat slug strings / bare path strings — this maps a
// backend Article into the exact shape components already expect, so
// nothing downstream needs to change.
function mapArticle(a) {
  if (!a) return null
  return {
    id: a.id,
    slug: a.slug,
    title: a.title,
    subtitle: a.subtitle,
    excerpt: a.excerpt,
    heroImage: a.hero_media?.public_url || null,
    heroMedia: mapMediaRef(a.hero_media),
    heroMediaId: a.hero_media?.id || null,
    heroImageAlt: a.hero_media?.alt_text || '',
    heroImageCaption: a.hero_image_caption,
    heroImageCredit: a.hero_image_credit,
    authorSlug: a.author?.slug,
    // Nested, already-resolved objects — cards prefer these over looking an
    // author/topic up by slug themselves (only the mock branch needs the
    // slug-lookup fallback, since raw mock articles don't carry them).
    author: a.author
      ? { slug: a.author.slug, name: a.author.name, photo: a.author.photo?.public_url || null, photoMedia: mapMediaRef(a.author.photo) }
      : null,
    coAuthors: (a.co_authors || []).map((x) => ({ slug: x.slug, name: x.name, photo: x.photo?.public_url || null, photoMedia: mapMediaRef(x.photo) })),
    coAuthorSlugs: (a.co_authors || []).map((x) => x.slug),
    publishDate: a.publish_date,
    updatedDate: a.updated_at,
    readingTime: a.reading_time,
    categorySlug: a.category?.slug || null,
    topic: a.topics?.[0] ? { slug: a.topics[0].slug, name: a.topics[0].name } : null,
    topicSlugs: (a.topics || []).map((t) => t.slug),
    tagSlugs: (a.tags || []).map((t) => t.slug),
    seriesSlug: a.series?.slug || null,
    relatedPersonSlugs: (a.related_people || []).map((p) => p.slug),
    relatedOrganizationSlugs: (a.related_organizations || []).map((o) => o.slug),
    relatedArticleSlugs: (a.related_articles || []).map((x) => x.slug),
    featured: a.featured,
    promoted: a.promoted,
    isSponsored: a.is_sponsored,
    sponsor: a.sponsor,
    status: a.status,
    seo: a.seo,
    content: a.content,
  }
}

// GET /api/v1/articles?topic=&series=&author=&page=
export async function fetchArticles(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/articles', { params })
    return { ...data, items: data.items.map(mapArticle) }
  }
  const { articles } = await loadMockDeps()
  let results = articles.filter((a) => a.status === 'published')
  if (params.topic) results = results.filter((a) => a.topicSlugs.includes(params.topic))
  if (params.series) results = results.filter((a) => a.seriesSlug === params.series)
  if (params.author) results = results.filter((a) => a.authorSlug === params.author)
  if (params.category) results = results.filter((a) => a.categorySlug === params.category)
  if (params.person) results = results.filter((a) => a.relatedPersonSlugs.includes(params.person))
  if (params.organization) results = results.filter((a) => a.relatedOrganizationSlugs.includes(params.organization))
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter(
      (a) => a.title.toLowerCase().includes(q) || a.excerpt.toLowerCase().includes(q),
    )
  }
  results = [...results].sort((a, b) => new Date(b.publishDate) - new Date(a.publishDate))
  const page = paginate(results, params)
  const items = await Promise.all(page.items.map(enrichMockArticle))
  return delay({ ...page, items })
}

// GET /api/v1/articles/{slug} — flat public URL is /{slug}; reserved-slug
// protection lives here so the CMS and the SPA share one source of truth.
export async function fetchArticleBySlug(slug) {
  if (RESERVED_SLUGS.includes(slug)) return delay(null)
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/articles/${slug}`)
      return mapArticle(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { findBySlug } = await loadMockDeps()
  return delay(await enrichMockArticle(findBySlug(slug)))
}

export async function fetchRelatedArticles(slugs = []) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/articles/related', { slugs })
    return data.map(mapArticle)
  }
  const { findBySlug } = await loadMockDeps()
  const found = slugs.map((s) => findBySlug(s)).filter(Boolean)
  return delay(await Promise.all(found.map(enrichMockArticle)))
}

export function isReservedSlug(slug) {
  return RESERVED_SLUGS.includes(slug)
}

// POST/PUT /api/v1/articles — admin create/update. Field names mirror
// ArticleInputSchema's camelCase data_keys exactly, so the editor form can
// send its state straight through.
export async function createArticle(payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/articles', payload)
    return mapArticle(data)
  }
  return delay({ ...payload, id: `mock-${Date.now()}`, slug: payload.slug })
}

export async function updateArticle(slug, payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.put(`/articles/${slug}`, payload)
    return mapArticle(data)
  }
  return delay({ ...payload, slug: payload.slug || slug })
}
