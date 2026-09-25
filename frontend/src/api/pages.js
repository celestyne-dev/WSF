import { apiClient } from './client'
import { mapMediaRef } from '../utils/media'

// Static/legal Pages CMS — no mock-mode branch. Unlike most content types
// here, this admin area is real-data-only (same as Taxonomy's admin
// surface): there's no pre-existing mock/pages.js this stands in for, and
// the public pages that consume fetchPublicPage (AboutPage, ContactPage,
// LegalPage) fall back to nothing but a clean "not available" state if the
// backend has no row for a key yet — never fabricated legal text.

function mapPagePublic(p) {
  if (!p) return null
  return {
    key: p.key,
    slug: p.slug,
    pageType: p.page_type,
    title: p.title,
    subtitle: p.subtitle,
    content: p.content || [],
    heroMedia: mapMediaRef(p.hero_media),
    seo: p.seo || null,
    effectiveDate: p.effective_date || null,
  }
}

function mapPageAdmin(p) {
  if (!p) return null
  return {
    id: p.id,
    key: p.key,
    slug: p.slug,
    pageType: p.page_type,
    isSystem: !!p.is_system,
    title: p.title,
    internalName: p.internal_name,
    subtitle: p.subtitle,
    content: p.content || [],
    heroMedia: mapMediaRef(p.hero_media),
    heroMediaId: p.hero_media_id || null,
    seo: p.seo || null,
    status: p.status || 'draft',
    effectiveDate: p.effective_date || null,
    lastReviewedAt: p.last_reviewed_at || null,
    lastReviewedBy: p.last_reviewed_by || null,
    publishedAt: p.published_at || null,
    updatedBy: p.updated_by || null,
    createdAt: p.created_at || null,
    updatedAt: p.updated_at || null,
  }
}

function mapRevision(r) {
  if (!r) return null
  return { id: r.id, note: r.note, createdBy: r.created_by, createdAt: r.created_at }
}

// Public — GET /pages/public/{key}, published-only. Returns null (not a
// thrown error) on 404 so a page component can render a graceful "not
// available yet" state instead of a raw API error.
export async function fetchPublicPage(key) {
  try {
    return mapPagePublic((await apiClient.get(`/pages/public/${key}`)).data)
  } catch (err) {
    if (err.response?.status === 404) return null
    throw err
  }
}

export async function fetchPagesAdmin(params = {}) {
  const { data } = await apiClient.get('/pages', { params })
  return { ...data, items: data.items.map(mapPageAdmin) }
}

export async function fetchPageAdmin(id) {
  return mapPageAdmin((await apiClient.get(`/pages/${id}`)).data)
}

export async function createPage(payload) {
  return mapPageAdmin((await apiClient.post('/pages', payload)).data)
}

export async function updatePage(id, payload) {
  return mapPageAdmin((await apiClient.put(`/pages/${id}`, payload)).data)
}

export async function setPageStatus(id, status) {
  return mapPageAdmin((await apiClient.put(`/pages/${id}/status`, { status })).data)
}

export async function markPageReviewed(id, note) {
  return mapPageAdmin((await apiClient.put(`/pages/${id}/review`, { note })).data)
}

// Hard delete — the backend rejects this with a 409 for any system page
// (About/Contact/Privacy/Terms/Cookies/Editorial Policy); only an
// admin-created general page can actually be removed this way.
export async function deletePage(id) {
  await apiClient.delete(`/pages/${id}`)
}

export async function fetchPageRevisions(id) {
  const { data } = await apiClient.get(`/pages/${id}/revisions`)
  return data.map(mapRevision)
}
