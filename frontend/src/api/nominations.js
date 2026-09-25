import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

// No dedicated Nominations mock dataset exists yet (this module is new) —
// an empty list keeps mock mode functional without growing the shared
// mock/admin.js file for a shape nothing else reads.
const MOCK_NOMINATIONS = []

export function mapNominationListItem(n) {
  if (!n) return null
  return {
    id: n.id,
    reference: n.reference || '',
    nomineeName: n.nominee_name || '',
    country: n.country ? { code: n.country.code, name: n.country.name } : null,
    professionalTitle: n.professional_title || '',
    organizationName: n.organization_name || '',
    series: n.series ? { id: n.series.id, slug: n.series.slug, name: n.series.name } : null,
    status: n.status || 'submitted',
    possibleDuplicate: !!n.possible_duplicate,
    assignedReviewer: n.assigned_reviewer ? { id: n.assigned_reviewer.id, fullName: n.assigned_reviewer.full_name } : null,
    submittedAt: n.submitted_at || null,
    updatedAt: n.updated_at || null,
  }
}

export function mapNomination(n) {
  if (!n) return null
  return {
    id: n.id,
    reference: n.reference || '',

    nomineeName: n.nominee_name || '',
    country: n.country ? { code: n.country.code, name: n.country.name } : null,
    countryCode: n.country?.code || '',
    city: n.city || '',
    professionalTitle: n.professional_title || '',
    organizationName: n.organization_name || '',
    websiteUrl: n.website_url || '',
    linkedinUrl: n.linkedin_url || '',
    shortBio: n.short_bio || '',
    nomineeEmail: n.nominee_email || '',

    nominationSummary: n.nomination_summary || '',
    achievements: n.achievements || '',
    whySignificant: n.why_significant || '',
    whoImpacted: n.who_impacted || '',
    supportingLinks: Array.isArray(n.supporting_links) ? n.supporting_links : [],
    topics: Array.isArray(n.topics) ? n.topics.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    topicSlugs: Array.isArray(n.topics) ? n.topics.map((t) => t.slug) : [],
    series: n.series ? { id: n.series.id, slug: n.series.slug, name: n.series.name } : null,
    seriesId: n.series_id || null,

    isSelfNomination: !!n.is_self_nomination,

    nominatorName: n.nominator_name || '',
    nominatorEmail: n.nominator_email || '',
    nominatorOrganization: n.nominator_organization || '',
    relationshipToNominee: n.relationship_to_nominee || '',
    nomineeAwareness: n.nominee_awareness || 'unknown',

    consentAccuracyConfirmed: !!n.consent_accuracy_confirmed,
    consentReviewGiven: !!n.consent_review_given,
    consentContactGiven: !!n.consent_contact_given,
    consentRecordedAt: n.consent_recorded_at || null,
    newsletterOptIn: !!n.newsletter_opt_in,

    possibleDuplicate: !!n.possible_duplicate,
    relatedNominations: Array.isArray(n.related_nominations)
      ? n.related_nominations.map((r) => ({ id: r.id, reference: r.reference, status: r.status, submittedAt: r.submitted_at }))
      : [],

    status: n.status || 'submitted',
    editorialAssessment: n.editorial_assessment || '',
    assignedReviewer: n.assigned_reviewer ? { id: n.assigned_reviewer.id, fullName: n.assigned_reviewer.full_name } : null,
    reviewedAt: n.reviewed_at || null,

    verificationState: n.verification_state || 'not_started',
    verificationNotes: n.verification_notes || '',
    contactNomineeBeforePublication: !!n.contact_nominee_before_publication,

    person: n.person ? { id: n.person.id, slug: n.person.slug, name: n.person.name } : null,
    personId: n.person_id || null,
    organization: n.organization ? { id: n.organization.id, slug: n.organization.slug, name: n.organization.name } : null,
    organizationId: n.organization_id || null,
    personProfileNeeded: !!n.person_profile_needed,

    resultingArticle: n.resulting_article
      ? { id: n.resulting_article.id, slug: n.resulting_article.slug, title: n.resulting_article.title, status: n.resulting_article.status }
      : null,

    notes: Array.isArray(n.notes)
      ? n.notes.map((note) => ({ id: note.id, body: note.body, user: note.user?.full_name || null, createdAt: note.created_at }))
      : [],

    submittedAt: n.submitted_at || null,
    updatedAt: n.updated_at || null,
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function buildNominationPayload(payload) {
  return {
    nomineeName: payload.nomineeName,
    countryCode: payload.countryCode,
    city: payload.city || undefined,
    professionalTitle: payload.professionalTitle || undefined,
    organizationName: payload.organizationName || undefined,
    websiteUrl: payload.websiteUrl || undefined,
    linkedinUrl: payload.linkedinUrl || undefined,
    shortBio: payload.shortBio || undefined,

    nominationSummary: payload.nominationSummary || undefined,
    achievements: payload.achievements,
    whySignificant: payload.whySignificant || undefined,
    whoImpacted: payload.whoImpacted || undefined,
    supportingLinks: (payload.supportingLinks || []).filter((l) => l.url?.trim()),
    topicSlugs: payload.topicSlugs,
    seriesId: payload.seriesId || undefined,

    isSelfNomination: payload.isSelfNomination,

    nominatorName: payload.nominatorName,
    nominatorEmail: payload.nominatorEmail,
    nominatorOrganization: payload.nominatorOrganization || undefined,
    relationshipToNominee: payload.relationshipToNominee || undefined,
    nomineeAwareness: payload.nomineeAwareness || 'unknown',

    consentAccuracyConfirmed: payload.consentAccuracyConfirmed,
    consentReviewGiven: payload.consentReviewGiven,
    consentContactGiven: payload.consentContactGiven,
    newsletterOptIn: payload.newsletterOptIn,

    acquisition: payload.acquisition,
  }
}

export async function submitNomination(payload) {
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/nominations', buildNominationPayload(payload))
      return {
        success: true,
        reference: data.reference,
        message: `Thank you — your nomination has been received for editorial review (reference ${data.reference}). We can't guarantee recognition, but our editorial team reviews every nomination.`,
      }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  return delay({
    success: true,
    reference: 'WSF-NOM-2026-00001',
    message: "Thank you — your nomination has been received for editorial review (reference WSF-NOM-2026-00001). We can't guarantee recognition, but our editorial team reviews every nomination.",
  }, 500)
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export async function fetchNominationsList(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/nominations', { params })
    return { ...data, items: data.items.map(mapNominationListItem) }
  }
  return delay({ items: MOCK_NOMINATIONS, meta: { page: 1, per_page: 20, total: 0, total_pages: 0, has_next: false, has_prev: false } })
}

export async function fetchNominationDetail(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/nominations/${id}`)
    return mapNomination(data)
  }
  return delay(null)
}

export async function updateNomination(id, payload) {
  const body = {
    topicSlugs: payload.topicSlugs,
    seriesId: payload.seriesId === '' || payload.seriesId == null ? null : Number(payload.seriesId),
    editorialAssessment: payload.editorialAssessment || undefined,
    verificationState: payload.verificationState || undefined,
    verificationNotes: payload.verificationNotes || undefined,
    contactNomineeBeforePublication: payload.contactNomineeBeforePublication,
    nomineeAwareness: payload.nomineeAwareness || undefined,
    personProfileNeeded: payload.personProfileNeeded,
    personId: payload.personId === '' || payload.personId == null ? null : Number(payload.personId),
    organizationId: payload.organizationId === '' || payload.organizationId == null ? null : Number(payload.organizationId),
  }
  const { data } = await apiClient.patch(`/nominations/${id}`, body)
  return mapNomination(data)
}

export async function updateNominationStatus(id, status) {
  const { data } = await apiClient.patch(`/nominations/${id}/status`, { status })
  return mapNomination(data)
}

export async function assignNominationReviewer(id, reviewerId) {
  const { data } = await apiClient.post(`/nominations/${id}/assign`, { reviewerId: reviewerId || null })
  return mapNomination(data)
}

export async function addNominationNote(id, body) {
  const { data } = await apiClient.post(`/nominations/${id}/notes`, { body })
  return mapNomination(data)
}

export async function deleteNomination(id) {
  await apiClient.delete(`/nominations/${id}`)
}

export async function fetchNominationHistory(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/nominations/${id}/history`)
    return data
  }
  return delay([])
}

export async function convertNominationToArticle(id, { authorId }) {
  const { data } = await apiClient.post(`/nominations/${id}/convert-to-article`, { authorId: Number(authorId) })
  return { nomination: mapNomination(data.nomination), article: data.article }
}
