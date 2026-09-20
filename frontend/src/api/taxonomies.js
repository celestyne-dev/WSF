import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { topics, getTopicBySlug as findTopic } from '../mock/topics'
import { series, getSeriesBySlug as findSeries } from '../mock/series'
import { authors, getAuthorBySlug as findAuthor } from '../mock/authors'
import { organizations, getOrganizationBySlug as findOrg } from '../mock/organizations'

export async function fetchTopics() {
  if (!USE_MOCK) return (await apiClient.get('/topics')).data
  return delay(topics)
}
export async function fetchTopicBySlug(slug) {
  if (!USE_MOCK) return (await apiClient.get(`/topics/${slug}`)).data
  return delay(findTopic(slug) || null)
}

export async function fetchSeries() {
  if (!USE_MOCK) return (await apiClient.get('/series')).data
  return delay(series)
}
export async function fetchSeriesBySlug(slug) {
  if (!USE_MOCK) return (await apiClient.get(`/series/${slug}`)).data
  return delay(findSeries(slug) || null)
}

export async function fetchAuthors() {
  if (!USE_MOCK) return (await apiClient.get('/authors')).data
  return delay(authors)
}
export async function fetchAuthorBySlug(slug) {
  if (!USE_MOCK) return (await apiClient.get(`/authors/${slug}`)).data
  return delay(findAuthor(slug) || null)
}

export async function fetchOrganizations() {
  if (!USE_MOCK) return (await apiClient.get('/organizations')).data
  return delay(organizations)
}
export async function fetchOrganizationBySlug(slug) {
  if (!USE_MOCK) return (await apiClient.get(`/organizations/${slug}`)).data
  return delay(findOrg(slug) || null)
}
