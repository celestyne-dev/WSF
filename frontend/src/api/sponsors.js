import { apiClient, USE_MOCK } from './client'
import { delay, paginate } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// No dedicated Sponsors mock dataset exists yet (this module is new) — a
// small self-contained fixture keeps mock mode functional without
// growing the shared mock/admin.js file for a shape nothing else reads.
const MOCK_SPONSORS = [
  {
    id: 1,
    campaign_name: 'Kaziwave Leadership Series',
    organization: { id: 1, slug: 'kaziwave', name: 'Kaziwave', logo: null },
    partnership: null,
    sponsorship_type: 'Content Sponsor',
    status: 'active',
    starts_at: '2026-01-01',
    ends_at: '2026-12-31',
    logo: null,
    creative: null,
    sponsor_url: 'https://kaziwave.example.com',
    cta_label: 'Visit Sponsor',
    disclosure_label: 'Sponsored by',
    public_visible: true,
    is_exclusive: false,
    exclusivity_notes: '',
    tier: 'Gold',
    estimated_value: 15000,
    currency: 'USD',
    commercial_notes: '',
    internal_notes: '',
    internal_reference: '',
    public_name_override: '',
    public_description: 'Supporting our Leadership Series through 2026.',
    placements: [{ id: 1, placement_key: 'homepage_featured', position: 0, starts_at: null, ends_at: null, active: true }],
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

function mapPlacement(p) {
  if (!p) return null
  return {
    id: p.id,
    placementKey: p.placement_key,
    position: p.position,
    startsAt: p.starts_at,
    endsAt: p.ends_at,
    active: p.active,
  }
}

export function mapSponsor(s) {
  if (!s) return null
  return {
    id: s.id,
    campaignName: s.campaign_name,
    organization: s.organization ? { id: s.organization.id, slug: s.organization.slug, name: s.organization.name, logo: mapMediaRef(s.organization.logo) } : null,
    organizationSlug: s.organization?.slug || null,
    partnership: s.partnership ? { id: s.partnership.id, company: s.partnership.company, subject: s.partnership.subject, status: s.partnership.status } : null,
    partnershipId: s.partnership?.id || null,
    internalReference: s.internal_reference || '',
    publicNameOverride: s.public_name_override || '',
    publicDescription: s.public_description || '',
    sponsorshipType: s.sponsorship_type || '',
    startsAt: s.starts_at || '',
    endsAt: s.ends_at || '',
    logo: mapMediaRef(s.logo),
    creative: mapMediaRef(s.creative),
    sponsorUrl: s.sponsor_url || '',
    ctaLabel: s.cta_label || '',
    disclosureLabel: s.disclosure_label || 'Sponsored by',
    status: s.status || 'draft',
    publicVisible: !!s.public_visible,
    isExclusive: !!s.is_exclusive,
    exclusivityNotes: s.exclusivity_notes || '',
    tier: s.tier || '',
    estimatedValue: s.estimated_value ?? null,
    currency: s.currency || '',
    commercialNotes: s.commercial_notes || '',
    internalNotes: s.internal_notes || '',
    placements: Array.isArray(s.placements) ? s.placements.map(mapPlacement) : [],
    createdAt: s.created_at || null,
    updatedAt: s.updated_at || null,
  }
}

function buildSponsorPayload(payload) {
  return {
    campaignName: payload.campaignName,
    organizationSlug: payload.organizationSlug || undefined,
    partnershipId: payload.partnershipId || undefined,
    internalReference: payload.internalReference || undefined,
    publicNameOverride: payload.publicNameOverride || undefined,
    publicDescription: payload.publicDescription || undefined,
    sponsorshipType: payload.sponsorshipType || undefined,
    startsAt: payload.startsAt || undefined,
    endsAt: payload.endsAt || undefined,
    logoMediaId: payload.logo?.id || undefined,
    creativeMediaId: payload.creative?.id || undefined,
    sponsorUrl: payload.sponsorUrl || undefined,
    ctaLabel: payload.ctaLabel || undefined,
    disclosureLabel: payload.disclosureLabel || undefined,
    publicVisible: payload.publicVisible,
    isExclusive: payload.isExclusive,
    exclusivityNotes: payload.exclusivityNotes || undefined,
    tier: payload.tier || undefined,
    estimatedValue: payload.estimatedValue === '' || payload.estimatedValue == null ? undefined : Number(payload.estimatedValue),
    currency: payload.currency || undefined,
    commercialNotes: payload.commercialNotes || undefined,
    internalNotes: payload.internalNotes || undefined,
  }
}

// ---------------------------------------------------------------------------
// Admin
// ---------------------------------------------------------------------------

export async function fetchSponsors(params = {}) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/sponsors/', { params })
    return { ...data, items: data.items.map(mapSponsor) }
  }
  let results = MOCK_SPONSORS
  if (params.status) results = results.filter((s) => s.status === params.status)
  if (params.q) {
    const q = params.q.toLowerCase()
    results = results.filter((s) => s.campaign_name.toLowerCase().includes(q))
  }
  return delay(paginate(results.map(mapSponsor), params))
}

export async function fetchSponsor(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/sponsors/${id}`)
    return mapSponsor(data)
  }
  return delay(mapSponsor(MOCK_SPONSORS.find((s) => String(s.id) === String(id))))
}

export async function createSponsor(payload) {
  const { data } = await apiClient.post('/sponsors/', buildSponsorPayload(payload))
  return mapSponsor(data)
}

export async function updateSponsor(id, payload) {
  const { data } = await apiClient.patch(`/sponsors/${id}`, buildSponsorPayload(payload))
  return mapSponsor(data)
}

export async function updateSponsorStatus(id, status) {
  const { data } = await apiClient.patch(`/sponsors/${id}/status`, { status })
  return mapSponsor(data)
}

export async function deleteSponsor(id) {
  await apiClient.delete(`/sponsors/${id}`)
}

export async function addSponsorPlacement(id, payload) {
  const { data } = await apiClient.post(`/sponsors/${id}/placements`, {
    placementKey: payload.placementKey,
    position: payload.position ?? 0,
    startsAt: payload.startsAt || undefined,
    endsAt: payload.endsAt || undefined,
    active: payload.active,
  })
  return mapSponsor(data)
}

export async function updateSponsorPlacement(id, placementId, payload) {
  const { data } = await apiClient.patch(`/sponsors/${id}/placements/${placementId}`, {
    position: payload.position,
    startsAt: payload.startsAt || undefined,
    endsAt: payload.endsAt || undefined,
    active: payload.active,
  })
  return mapSponsor(data)
}

export async function removeSponsorPlacement(id, placementId) {
  const { data } = await apiClient.delete(`/sponsors/${id}/placements/${placementId}`)
  return mapSponsor(data)
}

export async function fetchSponsorHistory(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/sponsors/${id}/history`)
    return data
  }
  return delay([])
}

export async function fetchSponsorAnalytics(id) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get(`/sponsors/${id}/analytics`)
    return data
  }
  return delay({ impressions: 0, clicks: 0, clickThroughRate: null })
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

function mapPublicSponsor(s) {
  return {
    id: s.id,
    campaignName: s.campaignName,
    publicName: s.publicName,
    publicDescription: s.publicDescription,
    organization: s.organization,
    logo: mapMediaRef(s.logo),
    creative: mapMediaRef(s.creative),
    disclosureLabel: s.disclosureLabel,
    sponsorUrl: s.sponsorUrl,
    ctaLabel: s.ctaLabel,
    placementKey: s.placementKey,
  }
}

export async function fetchPublicSponsorPlacements(placementKey) {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/sponsors/public', { params: { placement: placementKey } })
    return data.map(mapPublicSponsor)
  }
  return delay(
    MOCK_SPONSORS.filter((s) => s.status === 'active' && s.public_visible && s.placements.some((p) => p.placement_key === placementKey)).map((s) =>
      mapPublicSponsor({
        id: s.id,
        campaignName: s.campaign_name,
        publicName: s.public_name_override || s.organization?.name,
        publicDescription: s.public_description,
        organization: s.organization,
        logo: s.logo,
        creative: s.creative,
        disclosureLabel: s.disclosure_label,
        sponsorUrl: s.sponsor_url,
        ctaLabel: s.cta_label,
        placementKey,
      }),
    ),
  )
}
