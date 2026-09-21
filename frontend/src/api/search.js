import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

// Every mock dataset search touches is only needed when
// VITE_USE_MOCK=true — dynamic-imported as a batch so a real-mode
// production build never fetches any of them.
let _mockDeps
async function loadMockDeps() {
  if (!_mockDeps) {
    const [articlesMod, peopleMod, jobsMod, opportunitiesMod, eventsMod, resourcesMod, organizationsMod] = await Promise.all([
      import('../mock/articles'),
      import('../mock/people'),
      import('../mock/jobs'),
      import('../mock/opportunities'),
      import('../mock/events'),
      import('../mock/resources'),
      import('../mock/organizations'),
    ])
    _mockDeps = {
      articles: articlesMod.articles,
      people: peopleMod.people,
      jobs: jobsMod.jobs,
      opportunities: opportunitiesMod.opportunities,
      events: eventsMod.events,
      resources: resourcesMod.resources,
      organizations: organizationsMod.organizations,
    }
  }
  return _mockDeps
}

// GET /api/v1/search?q=&type=
export async function globalSearch(query, type = 'all') {
  if (!USE_MOCK) return (await apiClient.get('/search', { params: { q: query, type } })).data
  const q = query.trim().toLowerCase()
  if (!q) return delay({ query, results: [] })

  const { articles, people, jobs, opportunities, events, resources, organizations } = await loadMockDeps()
  const matches = (text) => text && text.toLowerCase().includes(q)

  const results = []
  if (type === 'all' || type === 'articles') {
    articles.filter((a) => matches(a.title) || matches(a.excerpt)).forEach((a) =>
      results.push({ resultType: 'Article', title: a.title, excerpt: a.excerpt, url: `/${a.slug}`, image: a.heroImage }),
    )
  }
  if (type === 'all' || type === 'people') {
    people.filter((p) => matches(p.name) || matches(p.organization)).forEach((p) =>
      results.push({ resultType: 'Person', title: p.name, excerpt: p.shortBio, url: `/people/${p.slug}`, image: p.photo }),
    )
  }
  if (type === 'all' || type === 'jobs') {
    jobs.filter((j) => matches(j.title) || matches(j.company)).forEach((j) =>
      results.push({ resultType: 'Job', title: j.title, excerpt: `${j.company} — ${j.location}`, url: `/jobs/${j.slug}`, image: j.logo }),
    )
  }
  if (type === 'all' || type === 'opportunities') {
    opportunities.filter((o) => matches(o.title) || matches(o.organization)).forEach((o) =>
      results.push({ resultType: 'Opportunity', title: o.title, excerpt: o.organization, url: `/opportunities/${o.slug}`, image: o.logo }),
    )
  }
  if (type === 'all' || type === 'events') {
    events.filter((e) => matches(e.title)).forEach((e) =>
      results.push({ resultType: 'Event', title: e.title, excerpt: e.location, url: `/events/${e.slug}`, image: e.coverImage }),
    )
  }
  if (type === 'all' || type === 'resources') {
    resources.filter((r) => matches(r.name)).forEach((r) =>
      results.push({ resultType: 'Resource', title: r.name, excerpt: r.description, url: `/resources/${r.slug}`, image: r.coverImage }),
    )
  }
  if (type === 'all' || type === 'organizations') {
    organizations.filter((o) => matches(o.name)).forEach((o) =>
      results.push({ resultType: 'Organization', title: o.name, excerpt: o.description, url: `/organizations/${o.slug}`, image: o.logo }),
    )
  }
  return delay({ query, results }, 300)
}
