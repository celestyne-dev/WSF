import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { articles } from '../mock/articles'
import { people } from '../mock/people'
import { jobs } from '../mock/jobs'
import { opportunities } from '../mock/opportunities'
import { events } from '../mock/events'
import { resources } from '../mock/resources'
import { organizations } from '../mock/organizations'

// GET /api/v1/search?q=&type=
export async function globalSearch(query, type = 'all') {
  if (!USE_MOCK) return (await apiClient.get('/search', { params: { q: query, type } })).data
  const q = query.trim().toLowerCase()
  if (!q) return delay({ query, results: [] })

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
