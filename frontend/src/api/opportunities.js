import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { regionFilterOptions, matchesRegion, matchesCountry, getCountry } from '../mock/geography'
import { mapMediaRef } from '../utils/media'

// The mock opportunities dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockOpportunities
async function loadMockOpportunities() {
  if (!_mockOpportunities) _mockOpportunities = await import('../mock/opportunities')
  return _mockOpportunities
}

// Opportunities carry an array of eligible countries rather than one, so
// filter options are built from flattened { code, name } pairs instead of
// the single-country countryOptionsFromItems helper used elsewhere.
function dedupeCountryOptions(pairs) {
  const seen = new Map()
  for (const { code, name } of pairs) {
    if (code && !seen.has(code)) seen.set(code, { value: code, label: name })
  }
  return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label))
}

// Mock opportunities only carry country codes; pair each with its display
// name via the mock geography table — confined to this mock-only branch.
function attachMockCountriesEligible(o) {
  if (!o) return null
  return { ...o, countriesEligibleNames: o.countriesEligible.map((code) => getCountry(code)?.name || code) }
}

function mapOpportunity(o) {
  if (!o) return null
  return {
    id: o.id,
    slug: o.slug,
    title: o.title,
    organization: o.organization?.name || o.organization_name || null,
    organizationSlug: o.organization?.slug || null,
    logo: o.logo?.public_url || null,
    logoMedia: mapMediaRef(o.logo),
    type: o.type,
    description: o.description,
    eligibility: o.eligibility,
    countriesEligible: (o.countries_eligible || []).map((c) => c.code),
    countriesEligibleNames: (o.countries_eligible || []).map((c) => c.name),
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
  const { opportunities } = await loadMockOpportunities()
  let results = [...opportunities]
  if (params.type) results = results.filter((o) => o.type === params.type)
  if (params.country) results = results.filter((o) => matchesCountry(o.countriesEligible, params.country))
  if (params.region) results = results.filter((o) => matchesRegion(o.countriesEligible, params.region))
  if (params.topic) results = results.filter((o) => o.topicSlugs.includes(params.topic))
  if (params.organization) results = results.filter((o) => o.organizationSlug === params.organization)
  if (params.featured) results = results.filter((o) => o.featured)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((o) => o.title.toLowerCase().includes(q) || o.organization.toLowerCase().includes(q))
  }
  results.sort((a, b) => new Date(a.deadline) - new Date(b.deadline))
  const page = paginate(results, params)
  return delay({ ...page, items: page.items.map(attachMockCountriesEligible) })
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
  const { getOpportunityBySlug } = await loadMockOpportunities()
  return delay(attachMockCountriesEligible(getOpportunityBySlug(slug)))
}

export async function fetchOpportunityFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/opportunities', { params: { pageSize: 100 } })
    const all = data.items.map(mapOpportunity)
    return {
      types: [...new Set(all.map((o) => o.type))].filter(Boolean),
      countries: dedupeCountryOptions(
        all.flatMap((o) => o.countriesEligible.map((code, i) => ({ code, name: o.countriesEligibleNames[i] }))),
      ),
      regions: regionFilterOptions(),
    }
  }
  const { opportunities } = await loadMockOpportunities()
  const enriched = opportunities.map(attachMockCountriesEligible)
  return delay({
    types: [...new Set(opportunities.map((o) => o.type))],
    countries: dedupeCountryOptions(
      enriched.flatMap((o) => o.countriesEligible.map((code, i) => ({ code, name: o.countriesEligibleNames[i] }))),
    ),
    regions: regionFilterOptions(),
  })
}
