import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { opportunities, getOpportunityBySlug as findBySlug } from '../mock/opportunities'

export async function fetchOpportunities(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/opportunities', { params })
    return data
  }
  let results = [...opportunities]
  if (params.type) results = results.filter((o) => o.type === params.type)
  if (params.country) results = results.filter((o) => o.countriesEligible.includes(params.country))
  if (params.topic) results = results.filter((o) => o.topicSlugs.includes(params.topic))
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((o) => o.title.toLowerCase().includes(q) || o.organization.toLowerCase().includes(q))
  }
  results.sort((a, b) => new Date(a.deadline) - new Date(b.deadline))
  return delay(paginate(results, params))
}

export async function fetchOpportunityBySlug(slug) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/opportunities/${slug}`)
    return data
  }
  return delay(findBySlug(slug) || null)
}

export function getOpportunityFilterOptions() {
  return {
    types: [...new Set(opportunities.map((o) => o.type))],
    countries: [...new Set(opportunities.flatMap((o) => o.countriesEligible))].sort(),
  }
}
