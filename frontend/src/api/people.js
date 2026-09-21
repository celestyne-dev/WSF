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
    seriesSlugs: [],
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

export function getPeopleFilterOptions() {
  return {
    countries: countryFilterOptions(people.map((p) => p.countryCode)),
    regions: regionFilterOptions(),
    industries: [...new Set(people.map((p) => p.industry))].sort(),
    expertise: [...new Set(people.flatMap((p) => p.expertise))].sort(),
  }
}
