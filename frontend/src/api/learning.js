import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// Learning / Courses & Programs CMS — structured educational offerings
// (short courses, masterclasses, programs, learning series). Deliberately
// NOT a full LMS: no learner accounts, progress tracking, quizzes, grades,
// or certificates (see backend app/models/learning.py). Public read
// functions support VITE_USE_MOCK=true; the admin surface is real-backend
// only, same convention as Directory/Editorial-Workflow CMS.

let _mockLearning
async function loadMockLearning() {
  if (!_mockLearning) _mockLearning = await import('../mock/learning')
  return _mockLearning
}

function mapInstructor(a) {
  if (!a) return null
  return { id: a.id, slug: a.slug, name: a.name, role: a.role || null, photo: mapMediaRef(a.photo) }
}

function mapOrganizationRef(o) {
  if (!o) return null
  return { id: o.id, slug: o.slug, name: o.name, logo: mapMediaRef(o.logo) }
}

function mapProductRef(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    price: p.price,
    salePrice: p.sale_price ?? p.salePrice ?? null,
    currency: p.currency || 'USD',
    status: p.status,
    isAvailable: p.is_available ?? p.isAvailable ?? true,
  }
}

function mapEventRef(e) {
  if (!e) return null
  return {
    id: e.id,
    slug: e.slug,
    title: e.title,
    date: e.date,
    endDate: e.end_date ?? e.endDate ?? null,
    location: e.location || null,
    format: e.format || null,
    status: e.status,
    registrationUrl: e.registration_url ?? e.registrationUrl ?? null,
    ticketPrice: e.ticket_price ?? e.ticketPrice ?? null,
    currency: e.currency || null,
  }
}

function mapLesson(l) {
  if (!l) return null
  return {
    id: l.id,
    title: l.title,
    lessonType: l.lesson_type || l.lessonType || 'text',
    summary: l.summary || '',
    content: Array.isArray(l.content) ? l.content : [],
    article: l.article ? { id: l.article.id, slug: l.article.slug, title: l.article.title } : null,
    resource: l.resource ? { id: l.resource.id, slug: l.resource.slug, name: l.resource.name } : null,
    externalUrl: l.external_url || l.externalUrl || null,
    durationMinutes: l.duration_minutes ?? l.durationMinutes ?? null,
    sortOrder: l.sort_order ?? l.sortOrder ?? 0,
  }
}

function mapModule(m) {
  if (!m) return null
  return {
    id: m.id,
    title: m.title,
    description: m.description || '',
    sortOrder: m.sort_order ?? m.sortOrder ?? 0,
    lessons: Array.isArray(m.lessons) ? m.lessons.map(mapLesson) : [],
  }
}

// Shared mapper for public list cards, public detail, and admin rows — the
// backend excludes different subsets of fields per shape (see
// schemas/learning.py's summary/admin-summary/full variants), so every
// field here is read defensively and simply absent where the API omitted it.
export function mapLearningProgram(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    title: p.title,
    subtitle: p.subtitle || '',
    shortDescription: p.short_description ?? p.shortDescription ?? '',
    programType: p.program_type ?? p.programType ?? 'course',
    difficultyLevel: p.difficulty_level ?? p.difficultyLevel ?? null,
    audience: Array.isArray(p.audience) ? p.audience : [],
    topics: Array.isArray(p.topics) ? p.topics.map((t) => ({ slug: t.slug, name: t.name })) : [],
    overview: Array.isArray(p.overview) ? p.overview : [],
    learningOutcomes: Array.isArray(p.learning_outcomes ?? p.learningOutcomes) ? (p.learning_outcomes ?? p.learningOutcomes) : [],
    prerequisites: Array.isArray(p.prerequisites) ? p.prerequisites : [],
    durationValue: p.duration_value ?? p.durationValue ?? null,
    durationUnit: p.duration_unit ?? p.durationUnit ?? null,
    heroMedia: mapMediaRef(p.hero_media ?? p.heroMedia),
    primaryInstructor: mapInstructor(p.primary_instructor ?? p.primaryInstructor),
    coInstructors: Array.isArray(p.co_instructors ?? p.coInstructors) ? (p.co_instructors ?? p.coInstructors).map(mapInstructor) : [],
    providerOrganization: mapOrganizationRef(p.provider_organization ?? p.providerOrganization),
    deliveryMode: p.delivery_mode ?? p.deliveryMode ?? 'self_paced',
    events: Array.isArray(p.events) ? p.events.map(mapEventRef) : [],
    accessType: p.access_type ?? p.accessType ?? 'free',
    product: mapProductRef(p.product),
    externalUrl: p.external_url ?? p.externalUrl ?? null,
    modules: Array.isArray(p.modules) ? p.modules.map(mapModule) : [],
    relatedArticles: Array.isArray(p.related_articles ?? p.relatedArticles) ? (p.related_articles ?? p.relatedArticles) : [],
    relatedResources: Array.isArray(p.related_resources ?? p.relatedResources) ? (p.related_resources ?? p.relatedResources) : [],
    featured: !!p.featured,
    status: p.status || 'published',
    publishedAt: p.published_at ?? p.publishedAt ?? null,
    archivedAt: p.archived_at ?? p.archivedAt ?? null,
    seo: p.seo || null,
    createdAt: p.created_at ?? p.createdAt ?? null,
    updatedAt: p.updated_at ?? p.updatedAt ?? null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function fetchLearningPrograms(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/learning', {
      params: {
        programType: params.programType || undefined,
        difficultyLevel: params.difficultyLevel || undefined,
        deliveryMode: params.deliveryMode || undefined,
        accessType: params.accessType || undefined,
        topic: params.topic || undefined,
        audience: params.audience || undefined,
        featured: params.featured || undefined,
        q: params.q || undefined,
        page: params.page,
        pageSize: params.pageSize,
      },
    })
    return { ...data, items: data.items.map(mapLearningProgram) }
  }
  const { learningPrograms } = await loadMockLearning()
  let results = learningPrograms.filter((p) => p.status === 'published')
  if (params.programType) results = results.filter((p) => p.programType === params.programType)
  if (params.difficultyLevel) results = results.filter((p) => p.difficultyLevel === params.difficultyLevel)
  if (params.deliveryMode) results = results.filter((p) => p.deliveryMode === params.deliveryMode)
  if (params.accessType) results = results.filter((p) => p.accessType === params.accessType)
  if (params.topic) results = results.filter((p) => p.topics.some((t) => t.slug === params.topic))
  if (params.audience) results = results.filter((p) => p.audience.includes(params.audience))
  if (params.featured) results = results.filter((p) => p.featured)
  if (params.q) {
    const q = params.q.toLowerCase()
    results = results.filter((p) => p.title.toLowerCase().includes(q))
  }
  results = [...results].sort((a, b) => Number(b.featured) - Number(a.featured))
  return delay(paginate(results, params))
}

export async function fetchLearningProgramBySlug(slug) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.get(`/learning/${slug}`)
      return mapLearningProgram(data)
    } catch (err) {
      if (err.response?.status === 404) return null
      throw err
    }
  }
  const { learningPrograms } = await loadMockLearning()
  const program = learningPrograms.find((p) => p.slug === slug && p.status === 'published')
  return delay(program || null)
}

// ---------------------------------------------------------------------------
// Admin — learning.manage. No mock-mode fallback, same convention as
// Directory/Taxonomy/Contact admin surfaces.
// ---------------------------------------------------------------------------

export async function fetchAdminLearningPrograms(params = {}) {
  const { data } = await apiClient.get('/learning/admin/programs', {
    params: {
      status: params.status || undefined,
      programType: params.programType || undefined,
      deliveryMode: params.deliveryMode || undefined,
      accessType: params.accessType || undefined,
      instructor: params.instructor || undefined,
      featured: params.featured || undefined,
      q: params.query || undefined,
      page: params.page,
      pageSize: params.pageSize || 20,
    },
  })
  return { items: data.items.map(mapLearningProgram), pagination: data.pagination }
}

export async function fetchAdminLearningProgram(id) {
  const { data } = await apiClient.get(`/learning/admin/programs/${id}`)
  return mapLearningProgram(data)
}

function toApiPayload(form) {
  return {
    title: form.title,
    slug: form.slug || undefined,
    subtitle: form.subtitle || undefined,
    shortDescription: form.shortDescription || undefined,
    programType: form.programType || 'course',
    difficultyLevel: form.difficultyLevel || undefined,
    audience: form.audience || [],
    topicSlugs: form.topicSlugs || [],
    overview: form.overview || [],
    learningOutcomes: form.learningOutcomes || [],
    prerequisites: form.prerequisites || [],
    durationValue: form.durationValue === '' || form.durationValue == null ? undefined : Number(form.durationValue),
    durationUnit: form.durationUnit || undefined,
    heroMediaId: form.heroMedia?.id || undefined,
    primaryInstructorSlug: form.primaryInstructorSlug || undefined,
    coInstructorSlugs: form.coInstructorSlugs || [],
    providerOrganizationSlug: form.providerOrganizationSlug || undefined,
    deliveryMode: form.deliveryMode || 'self_paced',
    eventSlugs: form.eventSlugs || [],
    accessType: form.accessType || 'free',
    productSlug: form.productSlug || undefined,
    externalUrl: form.externalUrl || undefined,
    relatedArticleSlugs: form.relatedArticleSlugs || [],
    relatedResourceSlugs: form.relatedResourceSlugs || [],
    featured: !!form.featured,
    status: form.status || 'draft',
    seo: form.seo || undefined,
  }
}

export async function createAdminLearningProgram(form) {
  const { data } = await apiClient.post('/learning/admin/programs', toApiPayload(form))
  return mapLearningProgram(data)
}

export async function updateAdminLearningProgram(id, form) {
  const { data } = await apiClient.patch(`/learning/admin/programs/${id}`, toApiPayload(form))
  return mapLearningProgram(data)
}

function toCurriculumPayload(modules) {
  return {
    modules: (modules || []).map((m) => ({
      id: m.id || undefined,
      title: m.title,
      description: m.description || undefined,
      lessons: (m.lessons || []).map((l) => ({
        id: l.id || undefined,
        title: l.title,
        lessonType: l.lessonType || 'text',
        summary: l.summary || undefined,
        content: l.content || [],
        articleSlug: l.articleSlug || undefined,
        resourceSlug: l.resourceSlug || undefined,
        externalUrl: l.externalUrl || undefined,
        durationMinutes: l.durationMinutes === '' || l.durationMinutes == null ? undefined : Number(l.durationMinutes),
      })),
    })),
  }
}

export async function updateAdminLearningCurriculum(id, modules) {
  const { data } = await apiClient.put(`/learning/admin/programs/${id}/curriculum`, toCurriculumPayload(modules))
  return mapLearningProgram(data)
}
