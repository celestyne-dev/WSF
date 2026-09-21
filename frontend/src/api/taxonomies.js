import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { topics, getTopicBySlug as findTopic } from '../mock/topics'
import { series, getSeriesBySlug as findSeries } from '../mock/series'
import { authors, getAuthorBySlug as findAuthor } from '../mock/authors'
import { organizations, getOrganizationBySlug as findOrg } from '../mock/organizations'

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
    type: o.org_type,
    description: o.description,
    website: o.website,
    social: o.social || {},
    featured: o.featured,
  }
}

export async function fetchTopics() {
  if (!USE_MOCK) return (await apiClient.get('/topics')).data.map(mapTopic)
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
  return delay(findTopic(slug) || null)
}

export async function fetchSeries() {
  if (!USE_MOCK) return (await apiClient.get('/series')).data.map(mapSeries)
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
  return delay(findSeries(slug) || null)
}

export async function fetchAuthors() {
  if (!USE_MOCK) return (await apiClient.get('/authors')).data.map(mapAuthor)
  return delay(authors)
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
  return delay(findAuthor(slug) || null)
}

export async function fetchOrganizations() {
  if (!USE_MOCK) return (await apiClient.get('/organizations')).data.map(mapOrganization)
  return delay(organizations)
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
  return delay(findOrg(slug) || null)
}
