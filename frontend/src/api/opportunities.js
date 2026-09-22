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
  return {
    ...o,
    countriesEligibleNames: (o.countriesEligible || []).map((code) => getCountry(code)?.name || code),
    description: Array.isArray(o.description) ? o.description : o.description ? [{ type: 'paragraph', text: o.description }] : [],
    isClosed: o.isClosed ?? false,
  }
}

function mapOpportunity(o) {
  if (!o) return null
  return {
    id: o.id,
    slug: o.slug,
    title: o.title,
    organization: o.organization?.name || o.organization_name || null,
    organizationSlug: o.organization?.slug || null,
    organizationId: o.organization_id || o.organization?.id || null,
    logo: o.organization?.logo?.public_url || o.logo?.public_url || null,
    logoMedia: mapMediaRef(o.organization?.logo || o.logo),
    type: o.type,
    shortDescription: o.short_description,
    description: Array.isArray(o.description) ? o.description : o.description ? [{ type: 'paragraph', text: o.description }] : [],
    eligibility: o.eligibility,
    eligibilityNotes: o.eligibility_notes,
    careerStage: o.career_stage,
    countriesEligible: (o.countries_eligible || []).map((c) => c.code),
    countriesEligibleNames: (o.countries_eligible || []).map((c) => c.name),
    location: o.location,
    fundingType: o.funding_type,
    fundingMin: o.funding_min,
    fundingMax: o.funding_max,
    currency: o.currency,
    fundingValue: o.funding_value,
    applicationUrl: o.application_url,
    applicationInstructions: o.application_instructions,
    openingDate: o.opening_date,
    deadline: o.deadline,
    publishedDate: o.published_date,
    expiryDate: o.expiry_date,
    featured: o.featured,
    sponsored: o.sponsored,
    status: o.status,
    isClosed: o.is_closed ?? false,
    seo: o.seo || null,
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

function toApiPayload(form) {
  return {
    title: form.title,
    slug: form.slug || undefined,
    organizationId: form.organizationId || undefined,
    organizationName: form.organizationName || undefined,
    logoMediaId: form.logoMediaId || undefined,
    type: form.type || undefined,
    shortDescription: form.shortDescription || undefined,
    description: form.description || [],
    eligibility: form.eligibility || undefined,
    eligibilityNotes: form.eligibilityNotes || undefined,
    careerStage: form.careerStage || undefined,
    countriesEligible: form.countriesEligible || [],
    location: form.location || undefined,
    fundingType: form.fundingType || undefined,
    fundingMin: form.fundingMin === '' || form.fundingMin == null ? undefined : Number(form.fundingMin),
    fundingMax: form.fundingMax === '' || form.fundingMax == null ? undefined : Number(form.fundingMax),
    currency: form.currency || undefined,
    fundingValue: form.fundingValue || undefined,
    applicationUrl: form.applicationUrl || undefined,
    applicationInstructions: form.applicationInstructions || undefined,
    openingDate: form.openingDate || undefined,
    deadline: form.deadline || undefined,
    expiryDate: form.expiryDate || undefined,
    topicSlugs: form.topicSlugs || [],
    featured: !!form.featured,
    sponsored: !!form.sponsored,
    status: form.status || 'draft',
    seo: form.seo || undefined,
  }
}

export async function createOpportunity(form) {
  const { data } = await apiClient.post('/opportunities', toApiPayload(form))
  return mapOpportunity(data)
}

export async function updateOpportunity(slug, form) {
  const { data } = await apiClient.put(`/opportunities/${slug}`, toApiPayload(form))
  return mapOpportunity(data)
}

export async function deleteOpportunity(slug) {
  await apiClient.delete(`/opportunities/${slug}`)
}
