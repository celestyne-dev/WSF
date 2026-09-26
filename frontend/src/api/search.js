import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

// Every mock dataset search touches is only needed when
// VITE_USE_MOCK=true — dynamic-imported as a batch so a real-mode
// production build never fetches any of them.
let _mockDeps
async function loadMockDeps() {
  if (!_mockDeps) {
    const [articlesMod, peopleMod, jobsMod, opportunitiesMod, eventsMod, resourcesMod, organizationsMod, topicsMod] =
      await Promise.all([
        import('../mock/articles'),
        import('../mock/people'),
        import('../mock/jobs'),
        import('../mock/opportunities'),
        import('../mock/events'),
        import('../mock/resources'),
        import('../mock/organizations'),
        import('../mock/topics'),
      ])
    _mockDeps = {
      articles: articlesMod.articles,
      people: peopleMod.people,
      jobs: jobsMod.jobs,
      opportunities: opportunitiesMod.opportunities,
      events: eventsMod.events,
      resources: resourcesMod.resources,
      organizations: organizationsMod.organizations,
      topics: topicsMod.topics || [],
    }
  }
  return _mockDeps
}

// Mirrors the backend's controlled type vocabulary (app/services/search.py:
// TYPE_LABELS) — used for the SearchPage type-filter tabs.
export const SEARCH_TYPES = [
  { key: 'all', label: 'All' },
  { key: 'articles', label: 'Stories' },
  { key: 'people', label: 'People' },
  { key: 'jobs', label: 'Jobs' },
  { key: 'opportunities', label: 'Opportunities' },
  { key: 'events', label: 'Events' },
  { key: 'resources', label: 'Resources' },
  { key: 'products', label: 'Shop' },
]

const PER_PAGE = 20

function mockMatches(text, q) {
  return text && text.toLowerCase().includes(q)
}

function mockSearch(deps, q, type) {
  const results = []
  if (type === 'all' || type === 'articles') {
    deps.articles
      .filter((a) => mockMatches(a.title, q) || mockMatches(a.excerpt, q))
      .forEach((a) => results.push({ resultType: 'Story', resultTypeKey: 'articles', title: a.title, excerpt: a.excerpt, url: `/${a.slug}`, image: a.heroImage, meta: {} }))
  }
  if (type === 'all' || type === 'people') {
    deps.people
      .filter((p) => mockMatches(p.name, q) || mockMatches(p.organization, q))
      .forEach((p) => results.push({ resultType: 'Person', resultTypeKey: 'people', title: p.name, excerpt: p.shortBio, url: `/people/${p.slug}`, image: p.photo, meta: {} }))
  }
  if (type === 'all' || type === 'jobs') {
    deps.jobs
      .filter((j) => mockMatches(j.title, q) || mockMatches(j.company, q))
      .forEach((j) => results.push({ resultType: 'Job', resultTypeKey: 'jobs', title: j.title, excerpt: `${j.company} — ${j.location}`, url: `/jobs/${j.slug}`, image: j.logo, meta: {} }))
  }
  if (type === 'all' || type === 'opportunities') {
    deps.opportunities
      .filter((o) => mockMatches(o.title, q) || mockMatches(o.organization, q))
      .forEach((o) => results.push({ resultType: 'Opportunity', resultTypeKey: 'opportunities', title: o.title, excerpt: o.organization, url: `/opportunities/${o.slug}`, image: o.logo, meta: {} }))
  }
  if (type === 'all' || type === 'events') {
    deps.events
      .filter((e) => mockMatches(e.title, q))
      .forEach((e) => results.push({ resultType: 'Event', resultTypeKey: 'events', title: e.title, excerpt: e.location, url: `/events/${e.slug}`, image: e.coverImage, meta: {} }))
  }
  if (type === 'all' || type === 'resources') {
    deps.resources
      .filter((r) => mockMatches(r.name, q))
      .forEach((r) => results.push({ resultType: 'Resource', resultTypeKey: 'resources', title: r.name, excerpt: r.description, url: `/resources/${r.slug}`, image: r.coverImage, meta: {} }))
  }
  return results
}

/**
 * GET /api/v1/search?q=&type=&page=&perPage=&topic=&country=&region=&remote=
 * See app/services/search.py for eligibility/relevance/field rules — this
 * adapter only shapes params and passes the response straight through
 * (the backend already returns camelCase field names for this endpoint).
 */
export async function globalSearch(query, { type = 'all', page = 1, topic, country, region, remote } = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/search', {
      params: { q: query, type, page, perPage: PER_PAGE, topic, country, region, remote: remote || undefined },
    })
    return data
  }

  const q = (query || '').trim().toLowerCase()
  if (!q) return delay({ query, type, results: [], pagination: { page: 1, perPage: PER_PAGE, total: 0, totalPages: 0 } })

  const deps = await loadMockDeps()
  const results = mockSearch(deps, q, type)
  return delay({ query, type, results, pagination: { page: 1, perPage: PER_PAGE, total: results.length, totalPages: 1 } }, 300)
}
