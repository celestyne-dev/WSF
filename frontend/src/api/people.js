import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { people, getPersonBySlug as findBySlug } from '../mock/people'
import { countryFilterOptions, regionFilterOptions, matchesRegion, matchesCountry } from '../mock/geography'

function mapPerson(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    photo: p.photo?.public_url || null,
    title: p.title,
    organizationSlug: p.organization?.slug || null,
    organization: p.organization?.name || null,
    location: p.location,
    countryCode: p.country?.code || p.country_code || null,
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
  return delay(paginate(results, params))
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
  return delay(findBySlug(slug) || null)
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
      countries: countryFilterOptions(all.map((p) => p.countryCode)),
      regions: regionFilterOptions(),
      industries: [...new Set(all.map((p) => p.industry))].filter(Boolean).sort(),
      expertise: [...new Set(all.flatMap((p) => p.expertise))].filter(Boolean).sort(),
    }
  }
  return delay({
    countries: countryFilterOptions(people.map((p) => p.countryCode)),
    regions: regionFilterOptions(),
    industries: [...new Set(people.map((p) => p.industry))].sort(),
    expertise: [...new Set(people.flatMap((p) => p.expertise))].sort(),
  })
}
