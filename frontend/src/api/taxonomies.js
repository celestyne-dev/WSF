import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { attachMockCountry } from './geography'
import { mapMediaRef } from '../utils/media'

// Each mock dataset here is only needed when VITE_USE_MOCK=true —
// dynamic-imported per module so a real-mode production build never
// fetches any of them.
let _mockTopics
async function loadMockTopics() {
  if (!_mockTopics) _mockTopics = await import('../mock/topics')
  return _mockTopics
}
let _mockSeries
async function loadMockSeries() {
  if (!_mockSeries) _mockSeries = await import('../mock/series')
  return _mockSeries
}
let _mockAuthors
async function loadMockAuthors() {
  if (!_mockAuthors) _mockAuthors = await import('../mock/authors')
  return _mockAuthors
}
let _mockOrganizations
async function loadMockOrganizations() {
  if (!_mockOrganizations) _mockOrganizations = await import('../mock/organizations')
  return _mockOrganizations
}

function mapTopic(t) {
  if (!t) return null
  return {
    id: t.id,
    slug: t.slug,
    name: t.name,
    description: t.description,
    heroImage: t.hero_media?.public_url || null,
    heroMedia: mapMediaRef(t.hero_media),
    heroMediaId: t.hero_media_id || null,
    seo: t.seo || null,
    status: t.status || 'published',
    sortOrder: t.sort_order || 0,
    articleCount: t.article_count,
    usageCount: t.usageCount,
  }
}

function mapCategory(c) {
  if (!c) return null
  return {
    id: c.id,
    slug: c.slug,
    name: c.name,
    description: c.description,
    status: c.status || 'published',
    sortOrder: c.sort_order || 0,
    usageCount: c.usageCount,
  }
}

function mapSeries(s) {
  if (!s) return null
  return {
    id: s.id,
    slug: s.slug,
    name: s.name,
    subtitle: s.subtitle,
    description: s.description,
    coverImage: s.cover_media?.public_url || null,
    coverMedia: mapMediaRef(s.cover_media),
    sponsor: s.sponsor_organization
      ? {
          name: s.sponsor_organization.name,
          logo: s.sponsor_organization.logo?.public_url || null,
          logoMedia: mapMediaRef(s.sponsor_organization.logo),
        }
      : null,
    seo: s.seo || null,
    featured: s.featured,
    status: s.status || 'published',
    sortOrder: s.sort_order || 0,
    articleCount: s.article_count,
    usageCount: s.usageCount,
  }
}

function mapTag(t) {
  if (!t) return null
  return {
    id: t.id,
    slug: t.slug,
    name: t.name,
    status: t.status || 'published',
    usageCount: t.usageCount,
  }
}

function mapAuthor(a) {
  if (!a) return null
  return {
    id: a.id,
    slug: a.slug,
    name: a.name,
    role: a.role,
    photo: a.photo?.public_url || null,
    photoMedia: mapMediaRef(a.photo),
    photoMediaId: a.photo?.id || null,
    // Ordered content-block list — same shape as Article.content, rendered
    // with the shared ArticleContent component and edited with the shared
    // ArticleBlockEditor. Mock-mode demo data still carries a plain
    // string, wrapped into a single paragraph block so both modes share
    // one shape.
    bio: Array.isArray(a.bio) ? a.bio : a.bio ? [{ type: 'paragraph', text: a.bio }] : [],
    shortBio: a.short_bio,
    expertise: a.expertise || [],
    topics: (a.topics || []).map(mapTopic),
    topicSlugs: (a.topics || []).map((t) => t.slug),
    location: a.location,
    countryCode: a.country?.code || a.country_code || null,
    country: a.country ? { code: a.country.code, name: a.country.name, region: a.country.region } : null,
    social: a.social || {},
    website: a.website,
    personId: a.person_id || null,
    person: a.person ? { slug: a.person.slug, name: a.person.name, title: a.person.title, photoMedia: mapMediaRef(a.person.photo) } : null,
    status: a.status || 'active',
    seo: a.seo || null,
    articleCount: a.article_count,
  }
}

function mapOrganization(o) {
  if (!o) return null
  return {
    id: o.id,
    slug: o.slug,
    name: o.name,
    logo: o.logo?.public_url || null,
    logoMedia: mapMediaRef(o.logo),
    logoMediaId: o.logo?.id || null,
    industry: o.industry,
    countryCode: o.country?.code || o.country_code || null,
    country: o.country ? { code: o.country.code, name: o.country.name, region: o.country.region } : null,
    location: o.location,
    foundedYear: o.founded_year,
    type: o.org_type,
    shortDescription: o.short_description,
    // Ordered content-block list — same shape as Article.content, rendered
    // with the shared ArticleContent component and edited with the shared
    // ArticleBlockEditor. Mock-mode demo data still carries a plain
    // string, wrapped into a single paragraph block so both modes share
    // one shape.
    description: Array.isArray(o.description) ? o.description : o.description ? [{ type: 'paragraph', text: o.description }] : [],
    website: o.website,
    social: o.social || {},
    status: o.status || 'published',
    seo: o.seo || null,
    peopleCount: o.people_count,
    featured: o.featured,
  }
}

// No mock category dataset exists — Categories were never modeled in
// mock/*.js (only Topics were). Real mode is fully functional; mock mode
// returns an empty list rather than fabricating data, same as
// AdminGenericList's "advertising" section handles a real feature with no
// mock equivalent.
export async function fetchCategories() {
  if (!USE_MOCK) return (await apiClient.get('/categories')).data.map(mapCategory)
  return delay([])
}

export async function fetchTopics() {
  if (!USE_MOCK) return (await apiClient.get('/topics')).data.map(mapTopic)
  const { topics } = await loadMockTopics()
  return delay(topics)
}
export async function fetchTopicBySlug(slug) {
  if (!USE_MOCK) {
    try {
      return mapTopic((await apiClient.get(`/topics/${slug}`)).data.topic)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getTopicBySlug } = await loadMockTopics()
  return delay(getTopicBySlug(slug) || null)
}

export async function fetchSeries() {
  if (!USE_MOCK) return (await apiClient.get('/series')).data.map(mapSeries)
  const { series } = await loadMockSeries()
  return delay(series)
}
export async function fetchSeriesBySlug(slug) {
  if (!USE_MOCK) {
    try {
      return mapSeries((await apiClient.get(`/series/${slug}`)).data.series)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getSeriesBySlug } = await loadMockSeries()
  return delay(getSeriesBySlug(slug) || null)
}

// ---------------------------------------------------------------------------
// Taxonomy admin (Topics/Categories/Series/Tags) — CMS CRUD + status/merge.
// Every call hits /api/v1/admin/taxonomy/* under taxonomy.manage; unlike
// the public fetch* functions above, these have no mock-mode fallback (the
// admin TAXONOMY area is real-data-only, same as every other CMS section).
// Field names mirror the *InputSchema/*UpdateSchema camelCase data_keys.
// ---------------------------------------------------------------------------

export async function fetchTopicsAdmin(params = {}) {
  const { data } = await apiClient.get('/admin/taxonomy/topics', { params })
  return { ...data, items: data.items.map(mapTopic) }
}
export async function fetchTopicAdmin(id) {
  return mapTopic((await apiClient.get(`/admin/taxonomy/topics/${id}`)).data)
}
export async function createTopic(payload) {
  return mapTopic((await apiClient.post('/admin/taxonomy/topics', payload)).data)
}
export async function updateTopic(id, payload) {
  return mapTopic((await apiClient.put(`/admin/taxonomy/topics/${id}`, payload)).data)
}
export async function setTopicStatus(id, status) {
  return mapTopic((await apiClient.put(`/admin/taxonomy/topics/${id}/status`, { status })).data)
}
// Hard delete — the backend rejects this with a 409 if any content still
// references the topic. Archive (via setTopicStatus) is the safe default.
export async function deleteTopic(id) {
  await apiClient.delete(`/admin/taxonomy/topics/${id}`)
}

export async function fetchCategoriesAdmin(params = {}) {
  const { data } = await apiClient.get('/admin/taxonomy/categories', { params })
  return { ...data, items: data.items.map(mapCategory) }
}
export async function fetchCategoryAdmin(id) {
  return mapCategory((await apiClient.get(`/admin/taxonomy/categories/${id}`)).data)
}
export async function createCategory(payload) {
  return mapCategory((await apiClient.post('/admin/taxonomy/categories', payload)).data)
}
export async function updateCategory(id, payload) {
  return mapCategory((await apiClient.put(`/admin/taxonomy/categories/${id}`, payload)).data)
}
export async function setCategoryStatus(id, status) {
  return mapCategory((await apiClient.put(`/admin/taxonomy/categories/${id}/status`, { status })).data)
}
export async function deleteCategory(id) {
  await apiClient.delete(`/admin/taxonomy/categories/${id}`)
}

export async function fetchSeriesAdmin(params = {}) {
  const { data } = await apiClient.get('/admin/taxonomy/series', { params })
  return { ...data, items: data.items.map(mapSeries) }
}
export async function fetchSeriesAdminById(id) {
  return mapSeries((await apiClient.get(`/admin/taxonomy/series/${id}`)).data)
}
export async function createSeries(payload) {
  return mapSeries((await apiClient.post('/admin/taxonomy/series', payload)).data)
}
export async function updateSeries(id, payload) {
  return mapSeries((await apiClient.put(`/admin/taxonomy/series/${id}`, payload)).data)
}
export async function setSeriesStatus(id, status) {
  return mapSeries((await apiClient.put(`/admin/taxonomy/series/${id}/status`, { status })).data)
}
export async function deleteSeries(id) {
  await apiClient.delete(`/admin/taxonomy/series/${id}`)
}

export async function fetchTags(params = {}) {
  const { data } = await apiClient.get('/admin/taxonomy/tags', { params })
  return { ...data, items: data.items.map(mapTag) }
}
export async function createTag(payload) {
  return mapTag((await apiClient.post('/admin/taxonomy/tags', payload)).data)
}
export async function updateTag(id, payload) {
  return mapTag((await apiClient.put(`/admin/taxonomy/tags/${id}`, payload)).data)
}
export async function deleteTag(id) {
  await apiClient.delete(`/admin/taxonomy/tags/${id}`)
}
// Moves every Article/Resource relationship off fromTagId onto toTagId,
// then deletes the source tag — the only bulk-editing operation offered
// for taxonomy. Returns the (now-merged-into) destination tag.
export async function mergeTags(fromTagId, toTagId) {
  return mapTag((await apiClient.post('/admin/taxonomy/tags/merge', { fromTagId, toTagId })).data)
}

// Mock demo authors still carry a plain-string `bio` (pre-dating the
// block-content shape the real API now returns) — wrapped into a single
// paragraph block here so both modes hand components the same shape,
// without needing to rewrite mock/authors.js's other already-correct,
// pre-normalized fields through the real-mode mapAuthor() mapper.
function normalizeMockAuthorBio(item) {
  if (!item) return item
  return { ...item, bio: Array.isArray(item.bio) ? item.bio : item.bio ? [{ type: 'paragraph', text: item.bio }] : [] }
}

export async function fetchAuthors(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/authors', { params })
    return { ...data, items: data.items.map(mapAuthor) }
  }
  const { authors } = await loadMockAuthors()
  let results = authors.map(attachMockCountry).map(normalizeMockAuthorBio)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((a) => a.name.toLowerCase().includes(q) || a.role?.toLowerCase().includes(q))
  }
  return delay({ items: results, pagination: { page: 1, pageSize: results.length, totalItems: results.length, totalPages: 1 } })
}
export async function fetchAuthorBySlug(slug) {
  if (!USE_MOCK) {
    try {
      return mapAuthor((await apiClient.get(`/authors/${slug}`)).data.author)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getAuthorBySlug } = await loadMockAuthors()
  return delay(normalizeMockAuthorBio(attachMockCountry(getAuthorBySlug(slug))))
}

// POST/PUT /api/v1/authors — CMS create/update. Field names mirror
// AuthorInputSchema's camelCase data_keys exactly.
export async function createAuthor(payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/authors', payload)
    return mapAuthor(data)
  }
  return delay({ ...payload, id: `mock-${Date.now()}`, slug: payload.slug })
}

export async function updateAuthor(slug, payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.put(`/authors/${slug}`, payload)
    return mapAuthor(data)
  }
  return delay({ ...payload, slug: payload.slug || slug })
}

// Hard delete — the backend rejects this with a 409 if the author is
// credited on any article (byline or co-author), so the CMS should offer
// archiving (status: "archived", via updateAuthor) as the safe
// alternative for established authors rather than calling this blindly.
export async function deleteAuthor(slug) {
  if (!USE_MOCK) {
    await apiClient.delete(`/authors/${slug}`)
    return
  }
  return delay(undefined)
}

// Mock demo organizations still carry a plain-string `description`
// (pre-dating the block-content shape the real API now returns) —
// wrapped into a single paragraph block so both modes share one shape.
function normalizeMockOrgDescription(item) {
  if (!item) return item
  return { ...item, description: Array.isArray(item.description) ? item.description : item.description ? [{ type: 'paragraph', text: item.description }] : [] }
}

export async function fetchOrganizations(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/organizations', { params })
    return { ...data, items: data.items.map(mapOrganization) }
  }
  const { organizations } = await loadMockOrganizations()
  let results = organizations.map(attachMockCountry).map(normalizeMockOrgDescription)
  if (params.type) results = results.filter((o) => o.type === params.type)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((o) => o.name.toLowerCase().includes(q) || o.industry?.toLowerCase().includes(q))
  }
  return delay({ items: results, pagination: { page: 1, pageSize: results.length, totalItems: results.length, totalPages: 1 } })
}
export async function fetchOrganizationBySlug(slug) {
  if (!USE_MOCK) {
    try {
      return mapOrganization((await apiClient.get(`/organizations/${slug}`)).data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getOrganizationBySlug } = await loadMockOrganizations()
  return delay(normalizeMockOrgDescription(attachMockCountry(getOrganizationBySlug(slug))))
}

// POST/PUT /api/v1/organizations — CMS create/update. Field names mirror
// OrganizationInputSchema's camelCase data_keys exactly.
export async function createOrganization(payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/organizations', payload)
    return mapOrganization(data)
  }
  return delay({ ...payload, id: `mock-${Date.now()}`, slug: payload.slug })
}

export async function updateOrganization(slug, payload) {
  if (!USE_MOCK) {
    const { data } = await apiClient.put(`/organizations/${slug}`, payload)
    return mapOrganization(data)
  }
  return delay({ ...payload, slug: payload.slug || slug })
}

// Hard delete — the backend rejects this with a 409 if the organization is
// referenced by any Person, Job, Opportunity, Article, or Series, so the
// CMS should offer archiving (status: "archived", via updateOrganization)
// as the safe alternative for established organizations rather than
// calling this blindly.
export async function deleteOrganization(slug) {
  if (!USE_MOCK) {
    await apiClient.delete(`/organizations/${slug}`)
    return
  }
  return delay(undefined)
}
