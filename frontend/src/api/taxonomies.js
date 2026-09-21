import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { attachMockCountry } from './geography'

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
  return { id: t.id, slug: t.slug, name: t.name, description: t.description, articleCount: t.article_count }
}

function mapSeries(s) {
  if (!s) return null
  return {
    id: s.id,
    slug: s.slug,
    name: s.name,
    description: s.description,
    coverImage: s.cover_media?.public_url || null,
    sponsor: s.sponsor_organization
      ? { name: s.sponsor_organization.name, logo: s.sponsor_organization.logo?.public_url || null }
      : null,
    featured: s.featured,
    articleCount: s.article_count,
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
    bio: a.bio,
    shortBio: a.short_bio,
    expertise: a.expertise || [],
    location: a.location,
    countryCode: a.country?.code || a.country_code || null,
    country: a.country ? { code: a.country.code, name: a.country.name, region: a.country.region } : null,
    social: a.social || {},
    website: a.website,
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
    industry: o.industry,
    countryCode: o.country?.code || o.country_code || null,
    country: o.country ? { code: o.country.code, name: o.country.name, region: o.country.region } : null,
    type: o.org_type,
    description: o.description,
    website: o.website,
    social: o.social || {},
    featured: o.featured,
  }
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

export async function fetchAuthors() {
  if (!USE_MOCK) return (await apiClient.get('/authors')).data.map(mapAuthor)
  const { authors } = await loadMockAuthors()
  return delay(authors.map(attachMockCountry))
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
  return delay(attachMockCountry(getAuthorBySlug(slug)))
}

export async function fetchOrganizations() {
  if (!USE_MOCK) return (await apiClient.get('/organizations')).data.map(mapOrganization)
  const { organizations } = await loadMockOrganizations()
  return delay(organizations.map(attachMockCountry))
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
  return delay(attachMockCountry(getOrganizationBySlug(slug)))
}
