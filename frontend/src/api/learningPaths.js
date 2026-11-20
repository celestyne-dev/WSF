import { apiClient, USE_MOCK } from './client'
import { mapLearningProgram } from './learning'
import { mapMediaRef } from '../utils/media'

// ---------------------------------------------------------------------------
// Learning Paths
// ---------------------------------------------------------------------------

export function mapLearningPath(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    title: p.title,
    subtitle: p.subtitle || '',
    shortDescription: p.shortDescription || '',
    description: Array.isArray(p.description) ? p.description : [],
    heroMedia: mapMediaRef(p.heroMedia),
    careerGoal: p.careerGoal || null,
    difficultyLevel: p.difficultyLevel || null,
    featured: !!p.featured,
    courseTitles: Array.isArray(p.courseTitles) ? p.courseTitles : [],
    courseCount: p.courseCount || 0,
    lessonCount: p.lessonCount || 0,
    totalMinutes: p.totalMinutes || null,
    lifetimeIncluded: !!p.lifetimeIncluded,
    courses: Array.isArray(p.courses) ? p.courses.map(mapLearningProgram) : [],
    seo: p.seo || {},
    viewerProgress: p.viewerProgress || null,
    viewerIsLifetime: !!p.viewerIsLifetime,
  }
}

export async function fetchLearningPaths(params = {}) {
  if (USE_MOCK) return []
  const { data } = await apiClient.get('/learning-paths', { params: { goal: params.goal || undefined, featured: params.featured || undefined } })
  return (Array.isArray(data) ? data : data?.items || []).map(mapLearningPath)
}

export async function fetchRecommendedLearningPaths() {
  if (USE_MOCK) return { goals: [], items: [] }
  const { data } = await apiClient.get('/learning-paths/recommended')
  return { goals: data?.goals || [], items: (data?.items || []).map(mapLearningPath) }
}

export async function fetchLearningPathBySlug(slug) {
  try {
    const { data } = await apiClient.get(`/learning-paths/${slug}`)
    return mapLearningPath(data)
  } catch (err) {
    if (err.response?.status === 404) return null
    throw err
  }
}

export async function fetchAdminLearningPaths() {
  const { data } = await apiClient.get('/learning-paths/admin')
  return Array.isArray(data) ? data : data?.items || []
}

export async function fetchAdminLearningPath(id) {
  const { data } = await apiClient.get(`/learning-paths/admin/${id}`)
  return data
}

function toPathPayload(form) {
  return {
    title: form.title,
    slug: form.slug || undefined,
    subtitle: form.subtitle || null,
    shortDescription: form.shortDescription || null,
    description: form.description || [],
    careerGoal: form.careerGoal || null,
    difficultyLevel: form.difficultyLevel || null,
    heroMediaId: form.heroMedia?.id || null,
    status: form.status || 'draft',
    featured: !!form.featured,
    seo: form.seo || {},
    programIds: (form.programs || []).map((p) => p.id),
  }
}

export async function saveAdminLearningPath(id, form) {
  const payload = toPathPayload(form)
  const { data } = id ? await apiClient.put(`/learning-paths/admin/${id}`, payload) : await apiClient.post('/learning-paths/admin', payload)
  return data
}

export async function deleteAdminLearningPath(id) {
  await apiClient.delete(`/learning-paths/admin/${id}`)
}
