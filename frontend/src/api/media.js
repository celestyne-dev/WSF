import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'

// The mock media library reuses existing article hero images as stand-in
// uploads — only needed when VITE_USE_MOCK=true, dynamic-imported so a
// real-mode production build never fetches it.
let _mockMedia
async function loadMockMedia() {
  if (!_mockMedia) {
    const { articles } = await import('../mock/articles')
    _mockMedia = articles
      .filter((a) => a.heroImage)
      .map((a, i) => ({
        id: `mock-${i}`,
        public_url: a.heroImage,
        alt_text: a.heroImageAlt || '',
        caption: a.heroImageCaption || '',
        credit: a.heroImageCredit || '',
        copyright_source: null,
        original_filename: `${a.slug}.jpg`,
        mime_type: 'image/jpeg',
        width: 1600,
        height: 1000,
        file_size: 240000,
        uploaded_by: { full_name: 'WSF Editorial' },
        created_at: a.publishDate,
        referenced: true,
      }))
  }
  return _mockMedia
}

function mapMedia(m) {
  if (!m) return null
  return {
    id: m.id,
    mediaPath: m.public_url,
    url: m.public_url,
    altText: m.alt_text || '',
    caption: m.caption || '',
    credit: m.credit || '',
    copyrightSource: m.copyright_source || '',
    originalFilename: m.original_filename,
    mimeType: m.mime_type,
    width: m.width,
    height: m.height,
    fileSize: m.file_size,
    uploadedBy: m.uploaded_by?.full_name || m.uploaded_by?.first_name || null,
    createdAt: m.created_at,
  }
}

// GET /api/v1/media?q=&mime_type=&page=&pageSize= — the CMS media library
// browser. `q` searches filename/alt/caption/credit (see
// backend/app/api/v1/media.py).
export async function fetchMediaLibrary(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/media', { params })
    return { ...data, items: data.items.map(mapMedia) }
  }
  const items = await loadMockMedia()
  let results = items
  if (params.q) {
    const q = params.q.toLowerCase()
    results = results.filter((m) =>
      [m.original_filename, m.alt_text, m.caption, m.credit].filter(Boolean).some((s) => s.toLowerCase().includes(q)),
    )
  }
  const page = paginate(results, { page: params.page, pageSize: params.pageSize || 24 })
  return delay({ items: page.items.map(mapMedia), pagination: page.pagination })
}

// POST /api/v1/media/upload — multipart. Axios sets the multipart boundary
// itself when given a FormData body; never set Content-Type manually here.
export async function uploadMedia(file, metadata = {}) {
  if (!USE_MOCK) {
    const formData = new FormData()
    formData.append('file', file)
    if (metadata.altText) formData.append('alt_text', metadata.altText)
    if (metadata.caption) formData.append('caption', metadata.caption)
    if (metadata.credit) formData.append('credit', metadata.credit)
    const { data } = await apiClient.post('/media/upload', formData)
    return mapMedia(data)
  }
  const objectUrl = URL.createObjectURL(file)
  return delay(
    mapMedia({
      id: `mock-${Date.now()}`,
      public_url: objectUrl,
      alt_text: metadata.altText || '',
      caption: metadata.caption || '',
      credit: metadata.credit || '',
      original_filename: file.name,
      mime_type: file.type,
      width: null,
      height: null,
      file_size: file.size,
      created_at: new Date().toISOString(),
    }),
    600,
  )
}

export async function updateMediaMetadata(id, metadata) {
  if (!USE_MOCK) {
    const { data } = await apiClient.patch(`/media/${id}`, {
      altText: metadata.altText,
      caption: metadata.caption,
      credit: metadata.credit,
      copyrightSource: metadata.copyrightSource,
    })
    return mapMedia(data)
  }
  const items = await loadMockMedia()
  const item = items.find((m) => m.id === id)
  if (item) Object.assign(item, { alt_text: metadata.altText, caption: metadata.caption, credit: metadata.credit, copyright_source: metadata.copyrightSource })
  return delay(mapMedia(item))
}

// DELETE /api/v1/media/{id} — the backend refuses (409) when the file is
// still referenced by an article/person/author/org/series/job/opportunity/
// event/resource/product/user avatar. Surface that as data, not a thrown
// error the caller has to special-case, so the UI can show a clear reason.
export async function deleteMedia(id) {
  if (!USE_MOCK) {
    try {
      await apiClient.delete(`/media/${id}`)
      return { success: true }
    } catch (err) {
      if (err.response?.status === 409) {
        return { success: false, reason: err.apiError?.message || 'This file is still in use and cannot be deleted.' }
      }
      throw err
    }
  }
  const items = await loadMockMedia()
  const item = items.find((m) => m.id === id)
  if (item?.referenced) {
    return delay({ success: false, reason: 'This file is a stand-in for existing mock content and cannot be deleted in mock mode.' }, 300)
  }
  _mockMedia = items.filter((m) => m.id !== id)
  return delay({ success: true }, 300)
}
