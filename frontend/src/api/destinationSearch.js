// Search loaders for the shared destination pickers (Navigation CMS item
// editor and Homepage Builder's Career Pathways cards). Values are ids —
// destinations link by id so a renamed slug never breaks a link.
import { fetchTopics, fetchSeries } from './taxonomies'
import { fetchPagesAdmin } from './pages'
import { fetchArticles } from './articles'
import { fetchPeople } from './people'
import { fetchOpportunities } from './opportunities'
import { fetchJobs } from './jobs'
import { fetchEvents } from './events'
import { fetchResources } from './resources'
import { fetchLearningPrograms } from './learning'

export async function searchTopicIds(query) {
  const all = await fetchTopics()
  const q = (query || '').toLowerCase()
  return all.filter((t) => !q || t.name.toLowerCase().includes(q)).slice(0, 12).map((t) => ({ value: t.id, label: t.name }))
}

export async function searchSeriesIds(query) {
  const all = await fetchSeries()
  const q = (query || '').toLowerCase()
  return all.filter((s) => !q || s.name.toLowerCase().includes(q)).slice(0, 12).map((s) => ({ value: s.id, label: s.name }))
}

export async function searchPageIds(query) {
  const res = await fetchPagesAdmin({ q: query, per_page: 10 })
  return res.items.map((p) => ({ value: p.id, label: p.title, sublabel: `/${p.slug}` }))
}

// --- slug-valued loaders (Homepage Content Collection) ---------------------

async function slugTerms(fetcher, query) {
  const all = await fetcher()
  const q = (query || '').toLowerCase()
  return all.filter((t) => !q || t.name.toLowerCase().includes(q)).slice(0, 12).map((t) => ({ value: t.slug, label: t.name }))
}

export const searchTopicSlugs = (query) => slugTerms(fetchTopics, query)
export const searchSeriesSlugs = (query) => slugTerms(fetchSeries, query)

// Public (published-only) list endpoints, searched by title; each returns
// { value: slug, label } for the manual picker. Search param names follow
// each endpoint (`query` for most, `q` for Resources/Learning).
export async function searchCollectionEntity(entityType, query) {
  const size = { pageSize: 8 }
  if (entityType === 'articles') {
    return (await fetchArticles({ query, ...size })).items.map((a) => ({ value: a.slug, label: a.title }))
  }
  if (entityType === 'people') {
    return (await fetchPeople({ query, ...size })).items.map((p) => ({ value: p.slug, label: p.name, sublabel: p.title || undefined }))
  }
  if (entityType === 'opportunities') {
    return (await fetchOpportunities({ query, ...size })).items.map((o) => ({ value: o.slug, label: o.title }))
  }
  if (entityType === 'jobs') {
    return (await fetchJobs({ query, ...size })).items.map((j) => ({ value: j.slug, label: j.title, sublabel: j.company || undefined }))
  }
  if (entityType === 'events') {
    return (await fetchEvents({ query, ...size })).items.map((e) => ({ value: e.slug, label: e.title }))
  }
  if (entityType === 'resources') {
    return (await fetchResources({ q: query, ...size })).items.map((r) => ({ value: r.slug, label: r.name }))
  }
  if (entityType === 'learning') {
    return (await fetchLearningPrograms({ q: query, ...size })).items.map((p) => ({ value: p.slug, label: p.title }))
  }
  return []
}
