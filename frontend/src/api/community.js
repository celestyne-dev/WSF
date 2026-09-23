import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// No dedicated Community mock dataset exists yet (this module is new) — a
// small self-contained fixture keeps mock mode functional without
// growing the shared mock/admin.js file for a shape nothing else reads.
const MOCK_PAGE = {
  id: 1,
  hero_heading: 'The WSF Community',
  hero_description:
    'A global home for ambitious, career-driven women — connect with members across industries, career stages, and countries.',
  hero_media: null,
  intro_content: [],
  benefits: [
    { title: 'Opportunities', description: 'Surface jobs, opportunities, and events curated for our community.' },
    { title: 'Insights', description: 'Leadership and business insights from across the WSF platform.' },
    { title: 'Connection', description: 'A global network of women shaping their industries and futures.' },
  ],
  who_for_text: 'Women at any career stage — early career to executive leadership — across every industry and country.',
  how_to_join_text: "Fill out the form below. It's free, takes two minutes, and membership is open to all.",
  cta_heading: 'Join the community',
  cta_description: 'Tell us a bit about yourself and we will be in touch.',
  cta_button_label: 'Join WSF',
  faq: [],
  status: 'published',
  seo: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const MOCK_MEMBERS = []

export function mapCommunityPage(p) {
  if (!p) return null
  return {
    id: p.id,
    heroHeading: p.hero_heading || '',
    heroDescription: p.hero_description || '',
    heroMedia: mapMediaRef(p.hero_media),
    heroMediaId: p.hero_media_id || null,
    introContent: Array.isArray(p.intro_content) ? p.intro_content : [],
    benefits: Array.isArray(p.benefits) ? p.benefits : [],
    whoForText: p.who_for_text || '',
    howToJoinText: p.how_to_join_text || '',
    ctaHeading: p.cta_heading || '',
    ctaDescription: p.cta_description || '',
    ctaButtonLabel: p.cta_button_label || '',
    faq: Array.isArray(p.faq) ? p.faq : [],
    status: p.status || 'draft',
    seo: p.seo || {},
    createdAt: p.created_at || null,
    updatedAt: p.updated_at || null,
  }
}

export function mapMember(m) {
  if (!m) return null
  return {
    id: m.id,
    firstName: m.first_name || '',
    lastName: m.last_name || '',
    fullName: m.full_name || `${m.first_name || ''} ${m.last_name || ''}`.trim(),
    email: m.email || '',
    professionalTitle: m.professional_title || '',
    organizationName: m.organization_name || '',
    shortBio: m.short_bio || '',
    websiteUrl: m.website_url || '',
    linkedinUrl: m.linkedin_url || '',
    profileImage: mapMediaRef(m.profile_image),
    profileImageMediaId: m.profile_image_media_id || null,
    country: m.country ? { code: m.country.code, name: m.country.name, region: m.country.region } : null,
    countryCode: m.country?.code || '',
    city: m.city || '',
    status: m.status || 'active',
    membershipType: m.membership_type || 'Community Member',
    source: m.source || '',
    referralNote: m.referral_note || '',
    appliedAt: m.applied_at || null,
    activatedAt: m.activated_at || null,
    leftAt: m.left_at || null,
    interests: Array.isArray(m.interests) ? m.interests.map((t) => ({ id: t.id, slug: t.slug, name: t.name })) : [],
    interestSlugs: Array.isArray(m.interests) ? m.interests.map((t) => t.slug) : [],
    consentGiven: !!m.consent_given,
    consentAt: m.consent_at || null,
    newsletterOptIn: !!m.newsletter_opt_in,
    communityUpdatesOptIn: !!m.community_updates_opt_in,
    directoryOptIn: !!m.directory_opt_in,
    person: m.person ? { id: m.person.id, slug: m.person.slug, name: m.person.name, title: m.person.title } : null,
    personId: m.person_id || null,
    adminTags: Array.isArray(m.admin_tags) ? m.admin_tags : [],
    notes: Array.isArray(m.notes)
      ? m.notes.map((n) => ({ id: n.id, body: n.body, user: n.user?.full_name || null, createdAt: n.created_at }))
      : [],
    createdAt: m.created_at || null,
    updatedAt: m.updated_at || null,
  }
}

function mapPublicMember(m) {
  return {
    id: m.id,
    name: m.name,
    professionalTitle: m.professionalTitle || '',
    organizationName: m.organizationName || '',
    shortBio: m.shortBio || '',
    country: m.country || null,
    interests: m.interests || [],
    profileImage: mapMediaRef(m.profileImage),
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function joinCommunity(payload) {
  const body = {
    firstName: payload.firstName,
    lastName: payload.lastName,
    email: payload.email,
    countryCode: payload.countryCode,
    interestSlugs: payload.interestSlugs || [],
    consentGiven: !!payload.consentGiven,
    professionalTitle: payload.professionalTitle || undefined,
    organizationName: payload.organizationName || undefined,
    shortBio: payload.shortBio || undefined,
    websiteUrl: payload.websiteUrl || undefined,
    linkedinUrl: payload.linkedinUrl || undefined,
    city: payload.city || undefined,
    referralNote: payload.referralNote || undefined,
    source: payload.source || undefined,
    subscribeNewsletter: !!payload.subscribeNewsletter,
    acquisition: payload.acquisition || undefined,
  }
  if (!USE_MOCK) {
    try {
      const { data } = await apiClient.post('/community/join', body)
      return { success: true, message: data.message }
    } catch (err) {
      return { success: false, message: err.apiError?.message || 'Something went wrong. Please try again.' }
    }
  }
  MOCK_MEMBERS.push({ ...body, status: 'active' })
  return delay({ success: true, message: 'Welcome to the Women Shaping Futures community!' }, 500)
}

export async function fetchPublicCommunity() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/community/public')
    return {
      page: {
        heroHeading: data.page.hero.heading || '',
        heroDescription: data.page.hero.description || '',
        heroMedia: mapMediaRef(data.page.hero.media),
        introContent: data.page.introContent || [],
        benefits: data.page.benefits || [],
        whoForText: data.page.whoForText || '',
        howToJoinText: data.page.howToJoinText || '',
        ctaHeading: data.page.cta.heading || '',
        ctaDescription: data.page.cta.description || '',
        ctaButtonLabel: data.page.cta.buttonLabel || '',
        faq: data.page.faq || [],
        seo: data.page.seo || {},
      },
      metrics: data.metrics || null,
    }
  }
  return delay({
    page: {
      heroHeading: MOCK_PAGE.hero_heading, heroDescription: MOCK_PAGE.hero_description, heroMedia: null,
      introContent: [], benefits: MOCK_PAGE.benefits, whoForText: MOCK_PAGE.who_for_text,
      howToJoinText: MOCK_PAGE.how_to_join_text, ctaHeading: MOCK_PAGE.cta_heading,
      ctaDescription: MOCK_PAGE.cta_description, ctaButtonLabel: MOCK_PAGE.cta_button_label, faq: [], seo: {},
    },
    metrics: null,
  })
}

export async function fetchCommunityDirectory(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/community/directory', { params })
    return (data || []).map(mapPublicMember)
  }
  return delay([])
}

// ---------------------------------------------------------------------------
// Admin — members
// ---------------------------------------------------------------------------

export async function fetchMembers(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/community/members', { params })
    return { ...data, items: data.items.map(mapMember) }
  }
  return delay({ items: [], meta: { page: 1, per_page: 20, total: 0, total_pages: 0, has_next: false, has_prev: false } })
}

export async function fetchMember(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/community/members/${id}`)
    return mapMember(data)
  }
  return delay(null)
}

function buildMemberPayload(payload) {
  return {
    firstName: payload.firstName,
    lastName: payload.lastName,
    email: payload.email,
    professionalTitle: payload.professionalTitle || undefined,
    organizationName: payload.organizationName || undefined,
    shortBio: payload.shortBio || undefined,
    websiteUrl: payload.websiteUrl || undefined,
    linkedinUrl: payload.linkedinUrl || undefined,
    city: payload.city || undefined,
    countryCode: payload.countryCode || undefined,
    membershipType: payload.membershipType || undefined,
    interestSlugs: payload.interestSlugs,
    referralNote: payload.referralNote || undefined,
    source: payload.source || undefined,
    communityUpdatesOptIn: payload.communityUpdatesOptIn,
    directoryOptIn: payload.directoryOptIn,
    adminTags: payload.adminTags,
    personId: payload.personId === '' || payload.personId == null ? undefined : Number(payload.personId),
    profileImageMediaId: payload.profileImage?.id || undefined,
  }
}

export async function updateMember(id, payload) {
  const { data } = await apiClient.patch(`/community/members/${id}`, buildMemberPayload(payload))
  return mapMember(data)
}

export async function updateMemberStatus(id, status) {
  const { data } = await apiClient.patch(`/community/members/${id}/status`, { status })
  return mapMember(data)
}

export async function addMemberNote(id, body) {
  const { data } = await apiClient.post(`/community/members/${id}/notes`, { body })
  return mapMember(data)
}

export async function deleteMember(id) {
  await apiClient.delete(`/community/members/${id}`)
}

export async function fetchMemberHistory(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/community/members/${id}/history`)
    return data
  }
  return delay([])
}

export async function exportMembers(params = {}) {
  const response = await apiClient.get('/community/members/export', { params, responseType: 'blob' })
  const url = window.URL.createObjectURL(new Blob([response.data], { type: 'text/csv' }))
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `wsf-members-${new Date().toISOString().slice(0, 10)}.csv`)
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.URL.revokeObjectURL(url)
}

// ---------------------------------------------------------------------------
// Admin — community page
// ---------------------------------------------------------------------------

export async function fetchCommunityPage() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/community/page')
    return mapCommunityPage(data)
  }
  return delay(mapCommunityPage(MOCK_PAGE))
}

export async function updateCommunityPage(payload) {
  const body = {
    heroHeading: payload.heroHeading || undefined,
    heroDescription: payload.heroDescription || undefined,
    heroMediaId: payload.heroMedia?.id || undefined,
    introContent: payload.introContent,
    benefits: payload.benefits,
    whoForText: payload.whoForText || undefined,
    howToJoinText: payload.howToJoinText || undefined,
    ctaHeading: payload.ctaHeading || undefined,
    ctaDescription: payload.ctaDescription || undefined,
    ctaButtonLabel: payload.ctaButtonLabel || undefined,
    faq: payload.faq,
    seo: payload.seo,
  }
  if (!USE_MOCK) {
    const { data } = await apiClient.patch('/community/page', body)
    return mapCommunityPage(data)
  }
  Object.assign(MOCK_PAGE, { hero_heading: body.heroHeading ?? MOCK_PAGE.hero_heading })
  return delay(mapCommunityPage(MOCK_PAGE))
}

export async function updateCommunityPageStatus(status) {
  if (!USE_MOCK) {
    const { data } = await apiClient.patch('/community/page/status', { status })
    return mapCommunityPage(data)
  }
  MOCK_PAGE.status = status
  return delay(mapCommunityPage(MOCK_PAGE))
}
