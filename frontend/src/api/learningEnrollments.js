import { apiClient } from './client'
import { mapLearningProgram } from './learning'

// First-party WSF Learning enrollment + lesson-progress tracking — free
// published programs only (see backend app/services/learning_enrollments.py
// and app/api/v1/learning_enrollments.py). Real-backend only, same
// convention as api/eventRegistrations.js — no mock-mode branch.
function mapEnrollment(e) {
  if (!e) return null
  return {
    id: e.id,
    status: e.status,
    enrolledAt: e.enrolled_at,
    withdrawnAt: e.withdrawn_at,
    completedAt: e.completed_at,
    completedLessons: e.completed_lessons,
    totalLessons: e.total_lessons,
    progressPercent: e.progress_percent,
    completedLessonIds: Array.isArray(e.completed_lesson_ids) ? e.completed_lesson_ids : [],
    programAvailable: e.program_available !== false,
    program: mapLearningProgram(e.program),
  }
}

function mapAdminEnrollment(e) {
  if (!e) return null
  return {
    id: e.id,
    status: e.status,
    enrolledAt: e.enrolled_at,
    withdrawnAt: e.withdrawn_at,
    completedAt: e.completed_at,
    completedLessons: e.completed_lessons,
    totalLessons: e.total_lessons,
    progressPercent: e.progress_percent,
    learnerName: e.learner_name,
    learnerEmail: e.learner_email,
    learnerCountry: e.learner_country,
  }
}

export async function enrollInProgram(programId) {
  const { data } = await apiClient.post('/learning-enrollments', { program_id: programId })
  return { enrolled: !!data?.enrolled, enrollment: mapEnrollment(data?.enrollment) }
}

export async function checkLearningEnrollment(programId) {
  const { data } = await apiClient.get('/learning-enrollments/check', { params: { programId } })
  return { enrolled: !!data?.enrolled, enrollment: mapEnrollment(data?.enrollment) }
}

// params: { state, page, perPage } — state: current|completed|withdrawn
export async function fetchMyLearningEnrollments(params = {}) {
  const { data } = await apiClient.get('/learning-enrollments/me', {
    params: { state: params.state, page: params.page, perPage: params.perPage },
  })
  return {
    items: (data.items || []).map(mapEnrollment),
    pagination: data.pagination,
  }
}

export async function withdrawFromProgram(enrollmentId) {
  const { data } = await apiClient.post(`/learning-enrollments/${enrollmentId}/withdraw`)
  return mapEnrollment(data?.enrollment)
}

export async function markLessonComplete(enrollmentId, lessonId) {
  const { data } = await apiClient.post(`/learning-enrollments/${enrollmentId}/lessons/${lessonId}/complete`)
  return mapEnrollment(data?.enrollment)
}

export async function markLessonIncomplete(enrollmentId, lessonId) {
  const { data } = await apiClient.delete(`/learning-enrollments/${enrollmentId}/lessons/${lessonId}/complete`)
  return mapEnrollment(data?.enrollment)
}

// --- Admin (learning.manage) --------------------------------------------

// params: { state, q, page, perPage }
// Pagination nested inside `data` (not the `meta=` kwarg) so the shared
// response interceptor's bare-array reshaping never fires and `counts`
// survives alongside `items` — same convention as
// fetchAdminEventRegistrations() in api/eventRegistrations.js. Because
// that bypasses the interceptor, `data.pagination` still carries the
// backend's raw snake_case keys and needs the same manual camelCase
// mapping fetchSavedItems() applies in api/saved.js.
export async function fetchAdminLearningEnrollments(programId, params = {}) {
  const { data } = await apiClient.get(`/learning/admin/programs/${programId}/enrollments`, {
    params: { state: params.state, q: params.q, page: params.page, perPage: params.perPage },
  })
  const pagination = data?.pagination || {}
  return {
    items: (data.items || []).map(mapAdminEnrollment),
    counts: data.counts || {},
    pagination: {
      page: pagination.page || 1,
      pageSize: pagination.per_page,
      totalItems: pagination.total || 0,
      totalPages: pagination.total_pages || 0,
    },
  }
}
