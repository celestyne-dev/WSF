import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { people, getPersonBySlug as findBySlug } from '../mock/people'
import { countryFilterOptions, regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'

export async function fetchPeople(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/people', { params })
    return data
  }
  let results = [...people]
  if (params.country) results = results.filter((p) => matchesCountry(p.countryCode, params.country))
  if (params.region) results = results.filter((p) => matchesRegion(p.countryCode, params.region))
  if (params.industry) results = results.filter((p) => p.industry === params.industry)
  if (params.expertise) results = results.filter((p) => p.expertise.includes(params.expertise))
  if (params.series) results = results.filter((p) => p.seriesSlugs.includes(params.series))
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((p) => p.name.toLowerCase().includes(q) || p.organization?.toLowerCase().includes(q))
  }
  results.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
  return delay(paginate(results, params))
}

export async function fetchPersonBySlug(slug) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/people/${slug}`)
    return data
  }
  return delay(findBySlug(slug) || null)
}

export function getPeopleFilterOptions() {
  return {
    countries: countryFilterOptions(people.map((p) => p.countryCode)),
    regions: regionFilterOptions(),
    industries: [...new Set(people.map((p) => p.industry))].sort(),
    expertise: [...new Set(people.flatMap((p) => p.expertise))].sort(),
  }
}
