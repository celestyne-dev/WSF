import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// No dedicated Story Submissions mock dataset exists yet (this module is
// new) — a small self-contained fixture keeps mock mode functional
// without growing the shared mock/admin.js file for a shape nothing
// else reads.
const MOCK_SUBMISSIONS = []

export function mapSubmissionListItem(s) {
  if (!s) return null
  return {
    id: s.id,
    reference: s.reference || '',
    fullName: s.full_name || `${s.first_name || ''} ${s.last_name || ''}`.trim(),
    email: s.email || '',
    country: s.country ? { code: s.country.code, name: s.country.name } : null,
    title: s.title || '',
    storyType: s.story_type || '',
    status: s.status || 'submitted',
    assignedEditor: s.assigned_editor ? { id: s.assigned_editor.id, fullName: s.assigned_editor.full_name } : null,
    submittedAt: s.submitted_at || null,
    updatedAt: s.updated_at || null,
  }
}

export function mapSubmission(s) {
  if (!s) return null
  return {
    id: s.id,
    reference: s.reference || '',
    firstName: s.first_name || '',
    lastName: s.last_name || '',
    fullName: s.full_name || `${s.first_name || ''} ${s.last_name || ''}`.trim(),
    email: s.email || '',
    country: s.country ? { code: s.country.code, name: s.country.name } : null,
    countryCode: s.country?.code || '',
    city: s.city || '',
    professionalTitle: s.professional_title || '',
    organizationName: s.organization_name || '',
    linkedinUrl: s.linkedin_url || '',
    websiteUrl: s.website_url || '',

    title: s.title || '',
    summary: s.summary || '',
    body: s.body || '',
    whyItMatters: s.why_it_matters || '',
    keyLessons: s.key_lessons || '',
    storyType: s.story_type || '',
    topics: Array.isArray(s.topics) ? s.topics.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    topicSlugs: Array.isArray(s.topics) ? s.topics.map((t) => t.slug) : [],
    series: s.series ? { id: s.series.id, slug: s.series.slug, name: s.series.name } : null,
    seriesId: s.series_id || null,

    subjectIsSubmitter: s.subject_is_submitter ?? true,
    subjectName: s.subject_name || '',
    subjectRelationship: s.subject_relationship || '',
    subjectPermissionStatus: s.subject_permission_status || 'not_applicable',

    contentOrigin: s.content_origin || '',
    previousPublicationUrl: s.previous_publication_url || '',
    aiInvolvement: s.ai_involvement || 'none',
    aiProvenanceNote: s.ai_provenance_note || '',

    consentReviewGiven: !!s.consent_review_given,
    consentContactGiven: !!s.consent_contact_given,
    consentAccuracyConfirmed: !!s.consent_accuracy_confirmed,
    consentMediaRightsConfirmed: s.consent_media_rights_confirmed ?? null,
    consentRecordedAt: s.consent_recorded_at || null,
    newsletterOptIn: !!s.newsletter_opt_in,

    recommendedFormat: s.recommended_format || '',
    verificationStatus: s.verification_status || 'unverified',
    permissionFollowupRequired: !!s.permission_followup_required,
    mediaFollowupRequired: !!s.media_followup_required,
    informationRequestedNote: s.information_requested_note || '',

    status: s.status || 'submitted',
    editorialAssessment: s.editorial_assessment || '',
    assignedEditor: s.assigned_editor ? { id: s.assigned_editor.id, fullName: s.assigned_editor.full_name } : null,
    reviewedAt: s.reviewed_at || null,

    person: s.person ? { id: s.person.id, slug: s.person.slug, name: s.person.name } : null,
    personId: s.person_id || null,
    organization: s.organization ? { id: s.organization.id, slug: s.organization.slug, name: s.organization.name } : null,
    organizationId: s.organization_id || null,

    mediaItems: Array.isArray(s.media_items)
      ? s.media_items.map((m) => ({
          id: m.id,
          media: mapMediaRef(m.media),
          caption: m.caption || '',
          credit: m.credit || '',
          rightsConfirmed: !!m.rights_confirmed,
        }))
      : [],

    resultingArticle: s.resulting_article
      ? { id: s.resulting_article.id, slug: s.resulting_article.slug, title: s.resulting_article.title, status: s.resulting_article.status }
      : null,

    notes: Array.isArray(s.notes)
      ? s.notes.map((n) => ({ id: n.id, body: n.body, user: n.user?.full_name || null, createdAt: n.created_at }))
      : [],

    submittedAt: s.submitted_at || null,
    updatedAt: s.updated_at || null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function buildSubmissionPayload(payload) {
  return {
    firstName: payload.firstName,
    lastName: payload.lastName,
    email: payload.email,
    countryCode: payload.countryCode,
    city: payload.city || undefined,
    professionalTitle: payload.professionalTitle || undefined,
    organizationName: payload.organizationName || undefined,
    linkedinUrl: payload.linkedinUrl || undefined,
    websiteUrl: payload.websiteUrl || undefined,

    title: payload.title,
    summary: payload.summary,
    body: payload.body,
    whyItMatters: payload.whyItMatters || undefined,
    keyLessons: payload.keyLessons || undefined,
    storyType: payload.storyType || undefined,
    topicSlugs: payload.topicSlugs,

    subjectIsSubmitter: payload.subjectIsSubmitter,
    subjectName: payload.subjectIsSubmitter ? undefined : payload.subjectName || undefined,
    subjectRelationship: payload.subjectIsSubmitter ? undefined : payload.subjectRelationship || undefined,

    contentOrigin: payload.contentOrigin || undefined,
    previousPublicationUrl: payload.previousPublicationUrl || undefined,
    aiInvolvement: payload.aiInvolvement || 'none',
    aiProvenanceNote: payload.aiProvenanceNote || undefined,

    media: (payload.media || []).map((m) => ({
      mediaId: m.mediaId,
      caption: m.caption || undefined,
      credit: m.credit || undefined,
      rightsConfirmed: m.rightsConfirmed,
    })),

    consentReviewGiven: payload.consentReviewGiven,
    consentContactGiven: payload.consentContactGiven,
    consentAccuracyConfirmed: payload.consentAccuracyConfirmed,
    consentMediaRightsConfirmed: payload.media?.length ? payload.consentMediaRightsConfirmed : undefined,
    newsletterOptIn: payload.newsletterOptIn,

    acquisition: payload.acquisition,
  }
}

export async function submitStorySubmission(payload) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/submissions', buildSubmissionPayload(payload))
      return {
        success: true,
        reference: data.reference,
        message: `Your story has been received for editorial review (reference ${data.reference}). We can't guarantee publication, but our editorial team reviews every submission.`,
      }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({
    success: true,
    reference: 'WSF-STORY-2026-00001',
    message: "Your story has been received for editorial review (reference WSF-STORY-2026-00001). We can't guarantee publication, but our editorial team reviews every submission.",
  }, 500)
}

// Optional image upload used solely to attach a photo to a story
// submission before it's sent — reuses the same validated upload flow as
// the admin media library, but through a public, permission-free
// endpoint (see backend SubmissionMediaUploadResource).
export async function uploadSubmissionMedia(file, metadata = {}) {
  if (!USE_MOCK) {
    const formData = new FormData()
    formData.append('file', file)
    if (metadata.caption) formData.append('caption', metadata.caption)
    if (metadata.credit) formData.append('credit', metadata.credit)
    const { data } = await apiClient.post('/submissions/media', formData)
    return { id: data.id, publicUrl: data.publicUrl }
  }
  const objectUrl = URL.createObjectURL(file)
  return delay({ id: `mock-${Date.now()}`, publicUrl: objectUrl }, 400)
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export async function fetchSubmissions(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/submissions', { params })
    return { ...data, items: data.items.map(mapSubmissionListItem) }
  }
  return delay({ items: MOCK_SUBMISSIONS, meta: { page: 1, per_page: 20, total: 0, total_pages: 0, has_next: false, has_prev: false } })
}

export async function fetchSubmission(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/submissions/${id}`)
    return mapSubmission(data)
  }
  return delay(null)
}

export async function updateSubmission(id, payload) {
  const body = {
    storyType: payload.storyType || undefined,
    topicSlugs: payload.topicSlugs,
    seriesId: payload.seriesId === '' || payload.seriesId == null ? null : Number(payload.seriesId),
    recommendedFormat: payload.recommendedFormat || undefined,
    verificationStatus: payload.verificationStatus || undefined,
    permissionFollowupRequired: payload.permissionFollowupRequired,
    mediaFollowupRequired: payload.mediaFollowupRequired,
    informationRequestedNote: payload.informationRequestedNote || undefined,
    editorialAssessment: payload.editorialAssessment || undefined,
    subjectPermissionStatus: payload.subjectPermissionStatus || undefined,
    personId: payload.personId === '' || payload.personId == null ? null : Number(payload.personId),
    organizationId: payload.organizationId === '' || payload.organizationId == null ? null : Number(payload.organizationId),
  }
  const { data } = await apiClient.patch(`/submissions/${id}`, body)
  return mapSubmission(data)
}

export async function updateSubmissionStatus(id, status) {
  const { data } = await apiClient.patch(`/submissions/${id}/status`, { status })
  return mapSubmission(data)
}

export async function assignSubmissionEditor(id, editorId) {
  const { data } = await apiClient.post(`/submissions/${id}/assign`, { editorId: editorId || null })
  return mapSubmission(data)
}

export async function addSubmissionNote(id, body) {
  const { data } = await apiClient.post(`/submissions/${id}/notes`, { body })
  return mapSubmission(data)
}

export async function deleteSubmission(id) {
  await apiClient.delete(`/submissions/${id}`)
}

export async function fetchSubmissionHistory(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/submissions/${id}/history`)
    return data
  }
  return delay([])
}

export async function convertSubmissionToArticle(id, { authorId, includeMedia = true }) {
  const { data } = await apiClient.post(`/submissions/${id}/convert-to-article`, {
    authorId: Number(authorId),
    includeMedia,
  })
  return { submission: mapSubmission(data.submission), article: data.article }
}
