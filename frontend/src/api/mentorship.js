import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// No dedicated Mentorship mock dataset exists yet (this module is new) — a
// small self-contained fixture keeps mock mode functional without
// growing the shared mock/admin.js file for a shape nothing else reads.
const MOCK_PROGRAMS = [
  {
    id: 1,
    slug: 'wsf-career-mentorship',
    name: 'WSF Career Mentorship',
    short_description: 'Structured, six-month mentorship pairing early-career women with senior leaders.',
    full_description: [],
    status: 'applications_open',
    application_open_now: true,
    application_opens_at: '2026-01-01',
    application_closes_at: '2026-12-31',
    program_starts_at: null,
    program_ends_at: null,
    country: null,
    eligibility_summary: 'Open to women of any career stage, anywhere in the world.',
    topics: ['Leadership', 'Career'],
    hero_media: null,
    seo: {},
  },
]

export function mapPublicProgram(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    shortDescription: p.shortDescription || p.short_description || '',
    fullDescription: p.fullDescription || p.full_description || [],
    status: p.status,
    applicationOpenNow: p.applicationOpenNow ?? p.application_open_now ?? false,
    applicationOpensAt: p.applicationOpensAt || p.application_opens_at || null,
    applicationClosesAt: p.applicationClosesAt || p.application_closes_at || null,
    programStartsAt: p.programStartsAt || p.program_starts_at || null,
    programEndsAt: p.programEndsAt || p.program_ends_at || null,
    country: p.country || null,
    eligibilitySummary: p.eligibilitySummary || p.eligibility_summary || '',
    topics: p.topics || [],
    heroMedia: mapMediaRef(p.heroMedia || p.hero_media),
    seo: p.seo || {},
  }
}

export function mapProgram(p) {
  if (!p) return null
  return {
    id: p.id,
    slug: p.slug,
    name: p.name,
    shortDescription: p.short_description || '',
    fullDescription: Array.isArray(p.full_description) ? p.full_description : [],
    status: p.status || 'draft',
    publicVisible: !!p.public_visible,
    applicationOpenNow: !!p.application_open_now,
    applicationOpensAt: p.application_opens_at || '',
    applicationClosesAt: p.application_closes_at || '',
    programStartsAt: p.program_starts_at || '',
    programEndsAt: p.program_ends_at || '',
    mentorCapacity: p.mentor_capacity ?? null,
    menteeCapacity: p.mentee_capacity ?? null,
    country: p.country ? { code: p.country.code, name: p.country.name } : null,
    countryCode: p.country?.code || '',
    eligibilitySummary: p.eligibility_summary || '',
    heroMedia: mapMediaRef(p.hero_media),
    heroMediaId: p.hero_media_id || null,
    topics: Array.isArray(p.topics) ? p.topics.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    topicSlugs: Array.isArray(p.topics) ? p.topics.map((t) => t.slug) : [],
    seo: p.seo || {},
    createdAt: p.created_at || null,
    updatedAt: p.updated_at || null,
  }
}

function mapApplicationPreview(a) {
  if (!a) return null
  return {
    id: a.id,
    role: a.role,
    fullName: a.full_name || `${a.first_name || ''} ${a.last_name || ''}`.trim(),
    email: a.email || '',
    professionalTitle: a.professional_title || '',
    organizationName: a.organization_name || '',
    status: a.status || 'submitted',
    mentorCapacity: a.mentor_capacity ?? null,
    mentorActive: !!a.mentor_active,
  }
}

export function mapApplication(a) {
  if (!a) return null
  return {
    id: a.id,
    programId: a.program_id,
    program: a.program ? { id: a.program.id, slug: a.program.slug, name: a.program.name, status: a.program.status } : null,
    role: a.role,
    firstName: a.first_name || '',
    lastName: a.last_name || '',
    fullName: a.full_name || `${a.first_name || ''} ${a.last_name || ''}`.trim(),
    email: a.email || '',
    professionalTitle: a.professional_title || '',
    organizationName: a.organization_name || '',
    industry: a.industry || '',
    yearsExperience: a.years_experience ?? null,
    linkedinUrl: a.linkedin_url || '',
    websiteUrl: a.website_url || '',
    backgroundText: a.background_text || '',
    goalsText: a.goals_text || '',
    supportOfferedText: a.support_offered_text || '',
    careerStage: a.career_stage || '',
    careerStagesSupported: Array.isArray(a.career_stages_supported) ? a.career_stages_supported : [],
    country: a.country ? { code: a.country.code, name: a.country.name } : null,
    countryCode: a.country?.code || '',
    timezone: a.timezone || '',
    meetingFrequency: a.meeting_frequency || '',
    mentorshipFormat: a.mentorship_format || '',
    availabilityNote: a.availability_note || '',
    mentorCapacity: a.mentor_capacity ?? null,
    mentorActive: !!a.mentor_active,
    activeMenteeCount: a.active_mentee_count ?? 0,
    status: a.status || 'submitted',
    consentGiven: !!a.consent_given,
    consentAt: a.consent_at || null,
    newsletterOptIn: !!a.newsletter_opt_in,
    member: a.member ? { id: a.member.id, firstName: a.member.first_name, lastName: a.member.last_name, email: a.member.email } : null,
    memberId: a.member_id || null,
    person: a.person ? { id: a.person.id, slug: a.person.slug, name: a.person.name, title: a.person.title } : null,
    personId: a.person_id || null,
    reviewedBy: a.reviewed_by?.full_name || null,
    topics: Array.isArray(a.topics) ? a.topics.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    topicSlugs: Array.isArray(a.topics) ? a.topics.map((t) => t.slug) : [],
    notes: Array.isArray(a.notes)
      ? a.notes.map((n) => ({ id: n.id, body: n.body, user: n.user?.full_name || null, createdAt: n.created_at }))
      : [],
    submittedAt: a.submitted_at || null,
    updatedAt: a.updated_at || null,
  }
}

function mapSession(s) {
  return {
    id: s.id,
    sessionDate: s.session_date,
    sessionNumber: s.session_number ?? null,
    status: s.status || 'scheduled',
    summary: s.summary || '',
    nextStepNote: s.next_step_note || '',
    createdAt: s.created_at || null,
  }
}

export function mapMatch(m) {
  if (!m) return null
  return {
    id: m.id,
    programId: m.program_id,
    program: m.program ? { id: m.program.id, slug: m.program.slug, name: m.program.name } : null,
    mentorApplicationId: m.mentor_application_id,
    mentorApplication: mapApplicationPreview(m.mentor_application),
    menteeApplicationId: m.mentee_application_id,
    menteeApplication: mapApplicationPreview(m.mentee_application),
    status: m.status || 'proposed',
    matchedAt: m.matched_at || null,
    plannedStartDate: m.planned_start_date || '',
    plannedEndDate: m.planned_end_date || '',
    actualCompletionDate: m.actual_completion_date || null,
    matchingNotes: m.matching_notes || '',
    closureReason: m.closure_reason || '',
    notes: Array.isArray(m.notes)
      ? m.notes.map((n) => ({ id: n.id, body: n.body, user: n.user?.full_name || null, createdAt: n.created_at }))
      : [],
    sessions: Array.isArray(m.sessions) ? m.sessions.map(mapSession) : [],
    createdAt: m.created_at || null,
    updatedAt: m.updated_at || null,
    capacityWarning: m.capacityWarning || null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function fetchPublicPrograms() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/mentorship/programs/public')
    return (data || []).map(mapPublicProgram)
  }
  return delay(MOCK_PROGRAMS.map(mapPublicProgram))
}

export async function submitMentorshipApplication(payload) {
  const body = {
    programId: payload.programId,
    role: payload.role,
    firstName: payload.firstName,
    lastName: payload.lastName,
    email: payload.email,
    countryCode: payload.countryCode,
    consentGiven: !!payload.consentGiven,
    professionalTitle: payload.professionalTitle || undefined,
    organizationName: payload.organizationName || undefined,
    industry: payload.industry || undefined,
    yearsExperience: payload.yearsExperience === '' || payload.yearsExperience == null ? undefined : Number(payload.yearsExperience),
    linkedinUrl: payload.linkedinUrl || undefined,
    websiteUrl: payload.websiteUrl || undefined,
    backgroundText: payload.backgroundText || undefined,
    goalsText: payload.goalsText || undefined,
    supportOfferedText: payload.supportOfferedText || undefined,
    careerStage: payload.careerStage || undefined,
    careerStagesSupported: payload.careerStagesSupported || undefined,
    timezone: payload.timezone || undefined,
    meetingFrequency: payload.meetingFrequency || undefined,
    mentorshipFormat: payload.mentorshipFormat || undefined,
    availabilityNote: payload.availabilityNote || undefined,
    topicSlugs: payload.topicSlugs || [],
    subscribeNewsletter: !!payload.subscribeNewsletter,
    acquisition: payload.acquisition || undefined,
  }
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/mentorship/applications', body)
      return { success: true, message: data.message }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({ success: true, message: `Thank you — your ${payload.role} application has been received.` }, 500)
}

// ---------------------------------------------------------------------------
// Admin — programs
// ---------------------------------------------------------------------------

export async function fetchPrograms(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/mentorship/programs', { params })
    return { ...data, items: data.items.map(mapProgram) }
  }
  return delay({ items: MOCK_PROGRAMS.map(mapProgram), meta: { page: 1, per_page: 20, total: 1, total_pages: 1, has_next: false, has_prev: false } })
}

export async function fetchProgram(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/mentorship/programs/${id}`)
    return mapProgram(data)
  }
  return delay(mapProgram(MOCK_PROGRAMS.find((p) => String(p.id) === String(id))))
}

function buildProgramPayload(payload) {
  return {
    slug: payload.slug,
    name: payload.name,
    shortDescription: payload.shortDescription || undefined,
    fullDescription: payload.fullDescription,
    publicVisible: payload.publicVisible,
    applicationOpensAt: payload.applicationOpensAt || undefined,
    applicationClosesAt: payload.applicationClosesAt || undefined,
    programStartsAt: payload.programStartsAt || undefined,
    programEndsAt: payload.programEndsAt || undefined,
    mentorCapacity: payload.mentorCapacity === '' || payload.mentorCapacity == null ? undefined : Number(payload.mentorCapacity),
    menteeCapacity: payload.menteeCapacity === '' || payload.menteeCapacity == null ? undefined : Number(payload.menteeCapacity),
    countryCode: payload.countryCode || undefined,
    eligibilitySummary: payload.eligibilitySummary || undefined,
    heroMediaId: payload.heroMedia?.id || undefined,
    topicSlugs: payload.topicSlugs,
    seo: payload.seo,
  }
}

export async function createProgram(payload) {
  const { data } = await apiClient.post('/mentorship/programs', buildProgramPayload(payload))
  return mapProgram(data)
}

export async function updateProgram(id, payload) {
  const { data } = await apiClient.patch(`/mentorship/programs/${id}`, buildProgramPayload(payload))
  return mapProgram(data)
}

export async function updateProgramStatus(id, status) {
  const { data } = await apiClient.patch(`/mentorship/programs/${id}/status`, { status })
  return mapProgram(data)
}

export async function deleteProgram(id) {
  await apiClient.delete(`/mentorship/programs/${id}`)
}

// ---------------------------------------------------------------------------
// Admin — applications
// ---------------------------------------------------------------------------

export async function fetchApplications(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/mentorship/applications', { params })
    return { ...data, items: data.items.map(mapApplication) }
  }
  return delay({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0, has_next: false, has_prev: false } })
}

export async function fetchApplication(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/mentorship/applications/${id}`)
    return mapApplication(data)
  }
  return delay(null)
}

function buildApplicationPayload(payload) {
  return {
    firstName: payload.firstName,
    lastName: payload.lastName,
    email: payload.email,
    professionalTitle: payload.professionalTitle || undefined,
    organizationName: payload.organizationName || undefined,
    industry: payload.industry || undefined,
    yearsExperience: payload.yearsExperience === '' || payload.yearsExperience == null ? undefined : Number(payload.yearsExperience),
    linkedinUrl: payload.linkedinUrl || undefined,
    websiteUrl: payload.websiteUrl || undefined,
    backgroundText: payload.backgroundText || undefined,
    goalsText: payload.goalsText || undefined,
    supportOfferedText: payload.supportOfferedText || undefined,
    careerStage: payload.careerStage || undefined,
    careerStagesSupported: payload.careerStagesSupported,
    countryCode: payload.countryCode || undefined,
    timezone: payload.timezone || undefined,
    meetingFrequency: payload.meetingFrequency || undefined,
    mentorshipFormat: payload.mentorshipFormat || undefined,
    availabilityNote: payload.availabilityNote || undefined,
    mentorCapacity: payload.mentorCapacity === '' || payload.mentorCapacity == null ? undefined : Number(payload.mentorCapacity),
    mentorActive: payload.mentorActive,
    topicSlugs: payload.topicSlugs,
    memberId: payload.memberId === '' || payload.memberId == null ? undefined : Number(payload.memberId),
    personId: payload.personId === '' || payload.personId == null ? undefined : Number(payload.personId),
  }
}

export async function updateApplication(id, payload) {
  const { data } = await apiClient.patch(`/mentorship/applications/${id}`, buildApplicationPayload(payload))
  return mapApplication(data)
}

export async function updateApplicationStatus(id, status) {
  const { data } = await apiClient.patch(`/mentorship/applications/${id}/status`, { status })
  return mapApplication(data)
}

export async function addApplicationNote(id, body) {
  const { data } = await apiClient.post(`/mentorship/applications/${id}/notes`, { body })
  return mapApplication(data)
}

export async function deleteApplication(id) {
  await apiClient.delete(`/mentorship/applications/${id}`)
}

export async function fetchApplicationHistory(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/mentorship/applications/${id}/history`)
    return data
  }
  return delay([])
}

// ---------------------------------------------------------------------------
// Admin — matches
// ---------------------------------------------------------------------------

export async function fetchMatches(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/mentorship/matches', { params })
    return { ...data, items: data.items.map(mapMatch) }
  }
  return delay({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0, has_next: false, has_prev: false } })
}

export async function fetchMatch(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/mentorship/matches/${id}`)
    return mapMatch(data)
  }
  return delay(null)
}

export async function createMatch(payload) {
  const { data } = await apiClient.post('/mentorship/matches', {
    mentorApplicationId: Number(payload.mentorApplicationId),
    menteeApplicationId: Number(payload.menteeApplicationId),
    plannedStartDate: payload.plannedStartDate || undefined,
    plannedEndDate: payload.plannedEndDate || undefined,
    matchingNotes: payload.matchingNotes || undefined,
  })
  return mapMatch(data)
}

export async function updateMatch(id, payload) {
  const { data } = await apiClient.patch(`/mentorship/matches/${id}`, {
    plannedStartDate: payload.plannedStartDate || undefined,
    plannedEndDate: payload.plannedEndDate || undefined,
  })
  return mapMatch(data)
}

export async function updateMatchStatus(id, status, closureReason) {
  const { data } = await apiClient.patch(`/mentorship/matches/${id}/status`, { status, closureReason: closureReason || undefined })
  return mapMatch(data)
}

export async function addMatchNote(id, body) {
  const { data } = await apiClient.post(`/mentorship/matches/${id}/notes`, { body })
  return mapMatch(data)
}

export async function fetchMatchHistory(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/mentorship/matches/${id}/history`)
    return data
  }
  return delay([])
}

export async function addMatchSession(matchId, payload) {
  const { data } = await apiClient.post(`/mentorship/matches/${matchId}/sessions`, {
    sessionDate: payload.sessionDate,
    sessionNumber: payload.sessionNumber || undefined,
    status: payload.status || undefined,
    summary: payload.summary || undefined,
    nextStepNote: payload.nextStepNote || undefined,
  })
  return mapMatch(data)
}

export async function updateMatchSession(matchId, sessionId, payload) {
  const { data } = await apiClient.patch(`/mentorship/matches/${matchId}/sessions/${sessionId}`, {
    sessionDate: payload.sessionDate || undefined,
    sessionNumber: payload.sessionNumber || undefined,
    status: payload.status || undefined,
    summary: payload.summary || undefined,
    nextStepNote: payload.nextStepNote || undefined,
  })
  return mapMatch(data)
}

// ---------------------------------------------------------------------------
// Admin — overview
// ---------------------------------------------------------------------------

export async function fetchMentorshipOverview() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/mentorship/overview')
    return data
  }
  return delay({
    openPrograms: 0, mentorApplications: 0, menteeApplications: 0, approvedMentors: 0,
    unmatchedMentees: 0, activeMatches: 0, completedMatches: 0,
  })
}
