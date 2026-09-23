import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// The mock resources dataset is only needed when VITE_USE_MOCK=true —
// dynamic-imported so a real-mode production build never fetches it.
let _mockResources
async function loadMockResources() {
  if (!_mockResources) _mockResources = await import('../mock/resources')
  return _mockResources
}

function mapResourceImage(img) {
  if (!img) return null
  // mapMediaRef() strips `id` (most callers only ever display media, never
  // resend it) — the gallery editor needs it back to reconstruct
  // galleryMediaIds on save, so it's restored here rather than widening
  // mapMediaRef for every other caller.
  return { id: img.id, position: img.position, media: { ...mapMediaRef(img.media), id: img.media?.id } }
}

export function mapResource(r) {
  if (!r) return null
  const topics = Array.isArray(r.topics) ? r.topics : r.topic ? [r.topic] : []
  return {
    id: r.id,
    slug: r.slug,
    name: r.name,
    subtitle: r.subtitle || '',
    shortDescription: r.short_description || r.shortDescription || '',
    description: Array.isArray(r.description) ? r.description : r.description ? [{ type: 'paragraph', text: r.description }] : [],
    coverImage: r.cover_media?.public_url || r.coverImage || null,
    coverMedia: mapMediaRef(r.cover_media) || r.coverMedia || null,
    images: Array.isArray(r.images) ? r.images.map(mapResourceImage) : [],
    type: r.type,
    topics: topics.map((t) => ({ id: t.id, slug: t.slug, name: t.name })),
    topicSlugs: topics.map((t) => t.slug),
    topicSlug: topics[0]?.slug || r.topicSlug || null,
    tags: Array.isArray(r.tags) ? r.tags.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    tagSlugs: Array.isArray(r.tags) ? r.tags.map((t) => t.slug) : [],
    author: r.author ? { id: r.author.id, slug: r.author.slug, name: r.author.name } : null,
    authorSlug: r.author?.slug || r.authorSlug || null,
    authorName: r.author_name || r.authorName || r.author?.name || null,
    price: r.price,
    currency: r.currency || 'USD',
    accessType: r.access_type || r.accessType || 'direct_download',
    isPremium: r.is_premium ?? r.isPremium ?? false,
    isDownloadable: r.is_downloadable ?? r.isDownloadable ?? true,
    isExternal: r.is_external ?? r.isExternal ?? false,
    isFree: r.is_free ?? !r.isPremium,
    requiresEmail: r.requires_email ?? (r.access_type === 'email_gate' || r.accessType === 'email_gate'),
    requiresAccount: r.requires_account ?? false,
    fileUrl: r.file_url || r.fileUrl || null,
    externalUrl: r.external_url || r.externalUrl || null,
    fileFormat: r.file_format || r.fileFormat || null,
    fileSize: r.file_size ?? r.fileSize ?? null,
    pageCount: r.page_count ?? r.pageCount ?? null,
    sponsor: r.sponsor ? { id: r.sponsor.id, slug: r.sponsor.slug, name: r.sponsor.name } : null,
    sponsorSlug: r.sponsor?.slug || null,
    sponsored: !!r.sponsored,
    downloadCount: r.download_count ?? r.downloadCount ?? 0,
    featured: !!r.featured,
    status: r.status || 'published',
    publishedDate: r.published_date || r.publishedDate || null,
    seo: r.seo || null,
    linkedProduct: r.linked_product || null,
  }
}

export async function fetchResources(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/resources', { params })
    return { ...data, items: data.items.map(mapResource) }
  }
  const { resources } = await loadMockResources()
  let results = [...resources]
  if (params.topic) results = results.filter((r) => r.topicSlug === params.topic)
  if (params.type) results = results.filter((r) => r.type === params.type)
  if (params.free === 'true') results = results.filter((r) => !r.isPremium)
  if (params.free === 'false') results = results.filter((r) => r.isPremium)
  if (params.premium === 'free') results = results.filter((r) => !r.isPremium)
  if (params.premium === 'premium') results = results.filter((r) => r.isPremium)
  if (params.featured) results = results.filter((r) => r.featured)
  if (params.q) {
    const q = params.q.toLowerCase()
    results = results.filter((r) => r.name.toLowerCase().includes(q))
  }
  results = results.map(mapResource)
  return delay(paginate(results, params))
}

export async function fetchResourceBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/resources/${slug}`)
      return mapResource(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { getResourceBySlug } = await loadMockResources()
  return delay(mapResource(getResourceBySlug(slug)) || null)
}

export async function fetchResourcesFilterOptions() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/resources', { params: { pageSize: 100 } })
    const all = data.items.map(mapResource)
    return { types: [...new Set(all.map((r) => r.type))].filter(Boolean) }
  }
  const { resources } = await loadMockResources()
  return delay({ types: [...new Set(resources.map((r) => r.type))] })
}

// Requests access to a resource per its access_type: a direct/email-gated
// download or external link returns { url }; premium/member-only resources
// (no payment/account system yet) reject with a typed error the caller
// renders as an honest "not yet available" state.
export async function requestResourceAccess(slug, payload = {}) {
  const { data } = await apiClient.post(`/resources/${slug}/access`, {
    email: payload.email || undefined,
    firstName: payload.firstName || undefined,
    countryCode: payload.countryCode || undefined,
    newsletterConsent: !!payload.newsletterConsent,
    acquisition: payload.acquisition || undefined,
  })
  return { url: data.url, accessType: data.accessType }
}

function toApiPayload(form) {
  return {
    name: form.name,
    slug: form.slug || undefined,
    subtitle: form.subtitle || undefined,
    shortDescription: form.shortDescription || undefined,
    description: form.description || [],
    coverMediaId: form.coverMedia?.id || undefined,
    galleryMediaIds: (form.images || []).map((img) => img.media?.id || img.id).filter(Boolean),
    type: form.type || undefined,
    topicSlugs: form.topicSlugs || (form.topicSlug ? [form.topicSlug] : []),
    tagSlugs: form.tagSlugs || [],
    authorSlug: form.authorSlug || undefined,
    authorName: form.authorName || undefined,
    price: form.price === '' || form.price == null ? 0 : Number(form.price),
    currency: form.currency || undefined,
    accessType: form.accessType || 'direct_download',
    fileUrl: form.fileUrl || undefined,
    externalUrl: form.externalUrl || undefined,
    fileFormat: form.fileFormat || undefined,
    fileSize: form.fileSize === '' || form.fileSize == null ? undefined : Number(form.fileSize),
    pageCount: form.pageCount === '' || form.pageCount == null ? undefined : Number(form.pageCount),
    sponsorSlug: form.sponsorSlug || undefined,
    sponsored: !!form.sponsored,
    featured: !!form.featured,
    status: form.status || 'draft',
    publishedDate: form.publishedDate || undefined,
    seo: form.seo || undefined,
  }
}

export async function createResource(form) {
  const { data } = await apiClient.post('/resources', toApiPayload(form))
  return mapResource(data)
}

export async function updateResource(slug, form) {
  const { data } = await apiClient.put(`/resources/${slug}`, toApiPayload(form))
  return mapResource(data)
}

export async function deleteResource(slug) {
  await apiClient.delete(`/resources/${slug}`)
}
