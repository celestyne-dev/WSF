import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'
import { attachMockCountry, countryOptionsFromItems } from './geography'
import { mapMediaRef } from '../utils/media'

// The mock people dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockPeople
async function loadMockPeople() {
  if (!_mockPeople) _mockPeople = await import('../mock/people')
  return _mockPeople
}

function mapPerson(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    photo: p.photo?.public_url || null,
    photoMedia: mapMediaRef(p.photo),
    title: p.title,
    organizationSlug: p.organization?.slug || null,
    organization: p.organization?.name || null,
    location: p.location,
    countryCode: p.country?.code || p.country_code || null,
    country: p.country ? { code: p.country.code, name: p.country.name, region: p.country.region } : null,
    industry: p.industry,
    profession: p.profession,
    expertise: p.expertise || [],
    featuredQuote: p.featured_quote,
    shortBio: p.short_bio,
    bio: p.bio,
    achievements: p.achievements || [],
    careerTimeline: p.career_timeline || [],
    awards: p.awards || [],
    website: p.website,
    social: p.social || {},
    seriesSlugs: (p.series || []).map((s) => s.slug),
    featured: p.featured,
  }
}

export async function fetchPeople(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/people', { params })
    return { ...data, items: data.items.map(mapPerson) }
  }
  const { people } = await loadMockPeople()
  let results = [...people]
  if (params.country) results = results.filter((p) => matchesCountry(p.countryCode, params.country))
  if (params.region) results = results.filter((p) => matchesRegion(p.countryCode, params.region))
  if (params.industry) results = results.filter((p) => p.industry === params.industry)
  if (params.expertise) results = results.filter((p) => p.expertise.includes(params.expertise))
  if (params.series) results = results.filter((p) => p.seriesSlugs.includes(params.series))
  if (params.organization) results = results.filter((p) => p.organizationSlug === params.organization)
  if (params.query) {
    const q = params.query.toLowerCase()
    results = results.filter((p) => p.name.toLowerCase().includes(q) || p.organization?.toLowerCase().includes(q))
  }
  results.sort((a, b) => (b.featured ? 1 : 0) - (a.featured ? 1 : 0))
  const page = paginate(results, params)
  return delay({ ...page, items: page.items.map(attachMockCountry) })
}

export async function fetchPersonBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/people/${slug}`)
      return mapPerson(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getPersonBySlug } = await loadMockPeople()
  return delay(attachMockCountry(getPersonBySlug(slug)))
}

// Filter dropdown options are derived from whichever people actually
// exist — in mock mode from the static array, in real mode from a large
// unfiltered page of the real API — so a filter never offers a country or
// industry with zero results. Async either way so callers don't need two
// code paths.
export async function fetchPeopleFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/people', { params: { pageSize: 200 } })
    const all = data.items.map(mapPerson)
    return {
      countries: countryOptionsFromItems(all),
      regions: regionFilterOptions(),
      industries: [...new Set(all.map((p) => p.industry))].filter(Boolean).sort(),
      expertise: [...new Set(all.flatMap((p) => p.expertise))].filter(Boolean).sort(),
    }
  }
  const { people } = await loadMockPeople()
  const enriched = people.map(attachMockCountry)
  return delay({
    countries: countryOptionsFromItems(enriched),
    regions: regionFilterOptions(),
    industries: [...new Set(people.map((p) => p.industry))].sort(),
    expertise: [...new Set(people.flatMap((p) => p.expertise))].sort(),
  })
}
