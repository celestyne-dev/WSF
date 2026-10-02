import { apiClient, USE_MOCK } from './client'
import { mapArticle } from './articles'
import { mapJob } from './jobs'
import { mapOpportunity } from './opportunities'
import { mapEvent } from './events'
import { mapResource } from './resources'
import { mapLearningProgram } from './learning'

// Private "save for later" bookmarks (see backend app/api/v1/saved.py).
// Real-backend only in any meaningful sense — mock mode below is just
// enough of a no-op that a logged-out/demo session doesn't crash, never an
// elaborate fake saved-items system (there is no mock "saved" dataset).
const CONTENT_MAPPERS = {
  article: mapArticle,
  job: mapJob,
  opportunity: mapOpportunity,
  resource: mapResource,
  event: mapEvent,
  learning_program: mapLearningProgram,
}

function mapSavedItem(item) {
  if (!item) return null
  const mapContent = CONTENT_MAPPERS[item.content_type]
  return {
    id: item.id,
    contentType: item.content_type,
    contentId: item.content_id,
    savedAt: item.saved_at,
    content: mapContent ? mapContent(item.content) : item.content,
  }
}

export async function saveItem(contentType, contentId) {
  if (!USE_MOCK) {
    const { data } = await apiClient.post('/saved', { content_type: contentType, content_id: contentId })
    return !!data?.saved
  }
  return true
}

export async function unsaveItem(contentType, contentId) {
  if (!USE_MOCK) {
    const { data } = await apiClient.delete(`/saved/${contentType}/${contentId}`)
    return !!data?.saved
  }
  return false
}

export async function checkSaved(contentType, contentId) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/saved/check', {
      params: { contentType, contentId },
    })
    return !!data?.saved
  }
  return false
}

// params: { type, page, perPage }
export async function fetchSavedItems(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/saved', {
      params: { type: params.type, page: params.page, perPage: params.perPage },
    })
    const pagination = data?.pagination || {}
    return {
      items: (data?.items || []).map(mapSavedItem),
      counts: data?.counts || {},
      pagination: {
        page: pagination.page || 1,
        pageSize: pagination.per_page,
        totalItems: pagination.total || 0,
        totalPages: pagination.total_pages || 0,
      },
    }
  }
  return {
    items: [],
    counts: {},
    pagination: { page: 1, pageSize: 20, totalItems: 0, totalPages: 0 },
  }
}
