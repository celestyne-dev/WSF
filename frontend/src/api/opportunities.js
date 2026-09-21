import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { opportunities, getOpportunityBySlug as findBySlug } from '../mock/opportunities'
import { countryFilterOptions, regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'

function mapOpportunity(o) {
  if (!o) return null
  return {
    id: o.id,
    slug: o.slug,
    title: o.title,
    organization: o.organization?.name || o.organization_name || null,
    organizationSlug: o.organization?.slug || null,
    logo: o.logo?.public_url || null,
    type: o.type,
    description: o.description,
    eligibility: o.eligibility,
    countriesEligible: (o.countries_eligible || []).map((c) => c.code),
    location: o.location,
    deadline: o.deadline,
    fundingValue: o.funding_value,
    applicationUrl: o.application_url,
    featured: o.featured,
    sponsored: o.sponsored,
    topicSlugs: (o.topics || []).map((t) => t.slug),
  }
}

export async function fetchOpportunities(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/opportunities', { params })
    return { ...data, items: data.items.map(mapOpportunity) }
  }
  let results = [...opportunities]
  if (params.type) results = results.filter((o) => o.type === params.type)
  if (params.country) results = results.filter((o) => matchesCountry(o.countriesEligible, params.country))
  if (params.region) results = results.filter((o) => matchesRegion(o.countriesEligible, params.region))
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
    try {
      const { data } = await apiClient.get(`/opportunities/${slug}`)
      return mapOpportunity(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  return delay(findBySlug(slug) || null)
}

export function getOpportunityFilterOptions() {
  return {
    types: [...new Set(opportunities.map((o) => o.type))],
    countries: countryFilterOptions(opportunities.flatMap((o) => o.countriesEligible)),
    regions: regionFilterOptions(),
  }
}
