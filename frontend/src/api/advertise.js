import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// No dedicated Advertise mock dataset exists yet (this module is new) — a
// small self-contained fixture keeps mock mode functional without
// growing the shared mock/admin.js file for a shape nothing else reads.
const MOCK_PAGE = {
  id: 1,
  hero_heading: 'Advertise With Women Shaping Futures',
  hero_description:
    'Reach ambitious, career-driven women across media, leadership, careers, business, and community — through a trusted global editorial platform.',
  hero_media: null,
  intro_content: [],
  audience_overview: 'Our audience spans early-career professionals to senior leaders across multiple regions.',
  why_content: [],
  cta_heading: "Let's talk",
  cta_description: 'Tell us about your goals and our team will follow up.',
  cta_button_label: 'Get in touch',
  contact_email: 'partnerships@womenshapingfutures.example',
  contact_note: '',
  media_kit_title: '',
  media_kit_url: '',
  media_kit_updated_at: null,
  faq: [],
  status: 'published',
  seo: {},
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
}

const MOCK_METRICS = [
  { id: 1, label: 'LinkedIn followers', value: '132,000+', unit: null, source_note: '', as_of_date: '2026-01-01', display_order: 0, public_visible: true },
  { id: 2, label: 'Newsletter subscribers', value: '34,210+', unit: null, source_note: '', as_of_date: '2026-01-01', display_order: 1, public_visible: true },
  { id: 3, label: 'Monthly website visitors', value: '210,000+', unit: null, source_note: '', as_of_date: '2026-01-01', display_order: 2, public_visible: true },
  { id: 4, label: 'Countries reached', value: '42', unit: 'countries', source_note: '', as_of_date: '2026-01-01', display_order: 3, public_visible: true },
]

const MOCK_OFFERINGS = [
  {
    id: 1, name: 'Newsletter Sponsorship', short_description: 'A dedicated placement in our newsletter.',
    full_description: '', features: ['Reaches 34,000+ subscribers', 'Includes a tracked link'], cta_label: 'Enquire',
    display_order: 0, featured: true, status: 'active', pricing_mode: 'contact', price_amount: null, currency: null, pricing_note: '',
  },
  {
    id: 2, name: 'Homepage Feature', short_description: 'Featured placement on the homepage.',
    full_description: '', features: ['High visibility', 'Rotating placement'], cta_label: 'Enquire',
    display_order: 1, featured: false, status: 'active', pricing_mode: 'starting_from', price_amount: 500, currency: 'USD', pricing_note: '',
  },
]

export function mapAdvertisePage(p) {
  if (!p) return null
  return {
    id: p.id,
    heroHeading: p.hero_heading || '',
    heroDescription: p.hero_description || '',
    heroMedia: mapMediaRef(p.hero_media),
    heroMediaId: p.hero_media_id || null,
    introContent: Array.isArray(p.intro_content) ? p.intro_content : [],
    audienceOverview: p.audience_overview || '',
    whyContent: Array.isArray(p.why_content) ? p.why_content : [],
    ctaHeading: p.cta_heading || '',
    ctaDescription: p.cta_description || '',
    ctaButtonLabel: p.cta_button_label || '',
    contactEmail: p.contact_email || '',
    contactNote: p.contact_note || '',
    mediaKitTitle: p.media_kit_title || '',
    mediaKitUrl: p.media_kit_url || '',
    mediaKitUpdatedAt: p.media_kit_updated_at || '',
    faq: Array.isArray(p.faq) ? p.faq : [],
    status: p.status || 'draft',
    seo: p.seo || {},
    createdAt: p.created_at || null,
    updatedAt: p.updated_at || null,
  }
}

export function mapAdvertiseMetric(m) {
  if (!m) return null
  return {
    id: m.id,
    label: m.label || '',
    value: m.value || '',
    unit: m.unit || '',
    sourceNote: m.source_note || '',
    asOfDate: m.as_of_date || '',
    displayOrder: m.display_order ?? 0,
    publicVisible: !!m.public_visible,
  }
}

export function mapAdvertiseOffering(o) {
  if (!o) return null
  return {
    id: o.id,
    name: o.name || '',
    shortDescription: o.short_description || '',
    fullDescription: o.full_description || '',
    features: Array.isArray(o.features) ? o.features : [],
    ctaLabel: o.cta_label || '',
    displayOrder: o.display_order ?? 0,
    featured: !!o.featured,
    status: o.status || 'active',
    pricingMode: o.pricing_mode || 'contact',
    priceAmount: o.price_amount ?? null,
    currency: o.currency || '',
    pricingNote: o.pricing_note || '',
  }
}

// ---------------------------------------------------------------------------
// Public
// ---------------------------------------------------------------------------

export async function fetchPublicAdvertise() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/advertise/public')
    return {
      page: {
        heroHeading: data.page.hero.heading || '',
        heroDescription: data.page.hero.description || '',
        heroMedia: mapMediaRef(data.page.hero.media),
        introContent: data.page.introContent || [],
        audienceOverview: data.page.audienceOverview || '',
        whyContent: data.page.whyContent || [],
        ctaHeading: data.page.cta.heading || '',
        ctaDescription: data.page.cta.description || '',
        ctaButtonLabel: data.page.cta.buttonLabel || '',
        contactEmail: data.page.contact.email || '',
        contactNote: data.page.contact.note || '',
        mediaKit: data.page.mediaKit || null,
        faq: data.page.faq || [],
        seo: data.page.seo || {},
      },
      metrics: (data.metrics || []).map((m) => ({
        id: m.id, label: m.label, value: m.value, unit: m.unit || '', asOfDate: m.asOfDate || '',
      })),
      offerings: (data.offerings || []).map((o) => ({
        id: o.id, name: o.name, shortDescription: o.shortDescription || '', fullDescription: o.fullDescription || '',
        features: o.features || [], ctaLabel: o.ctaLabel || '', featured: !!o.featured, pricingMode: o.pricingMode,
        priceAmount: o.priceAmount ?? null, currency: o.currency || '', pricingNote: o.pricingNote || '',
      })),
    }
  }
  return delay({
    page: {
      heroHeading: MOCK_PAGE.hero_heading, heroDescription: MOCK_PAGE.hero_description, heroMedia: null,
      introContent: [], audienceOverview: MOCK_PAGE.audience_overview, whyContent: [],
      ctaHeading: MOCK_PAGE.cta_heading, ctaDescription: MOCK_PAGE.cta_description, ctaButtonLabel: MOCK_PAGE.cta_button_label,
      contactEmail: MOCK_PAGE.contact_email, contactNote: MOCK_PAGE.contact_note, mediaKit: null, faq: [], seo: {},
    },
    metrics: MOCK_METRICS.filter((m) => m.public_visible).map((m) => ({
      id: m.id, label: m.label, value: m.value, unit: m.unit || '', asOfDate: m.as_of_date,
    })),
    offerings: MOCK_OFFERINGS.filter((o) => o.status === 'active').map((o) => ({
      id: o.id, name: o.name, shortDescription: o.short_description, fullDescription: o.full_description,
      features: o.features, ctaLabel: o.cta_label, featured: o.featured, pricingMode: o.pricing_mode,
      priceAmount: o.price_amount, currency: o.currency, pricingNote: o.pricing_note,
    })),
  })
}

// ---------------------------------------------------------------------------
// Admin — page
// ---------------------------------------------------------------------------

export async function fetchAdvertisePage() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/advertise/page')
    return mapAdvertisePage(data)
  }
  return delay(mapAdvertisePage(MOCK_PAGE))
}

export async function updateAdvertisePage(payload) {
  const body = {
    heroHeading: payload.heroHeading || undefined,
    heroDescription: payload.heroDescription || undefined,
    heroMediaId: payload.heroMedia?.id || undefined,
    introContent: payload.introContent,
    audienceOverview: payload.audienceOverview || undefined,
    whyContent: payload.whyContent,
    ctaHeading: payload.ctaHeading || undefined,
    ctaDescription: payload.ctaDescription || undefined,
    ctaButtonLabel: payload.ctaButtonLabel || undefined,
    contactEmail: payload.contactEmail || undefined,
    contactNote: payload.contactNote || undefined,
    mediaKitTitle: payload.mediaKitTitle || undefined,
    mediaKitUrl: payload.mediaKitUrl || undefined,
    mediaKitUpdatedAt: payload.mediaKitUpdatedAt || undefined,
    faq: payload.faq,
    seo: payload.seo,
  }
  if (!USE_MOCK) {
    const { data } = await apiClient.patch('/advertise/page', body)
    return mapAdvertisePage(data)
  }
  Object.assign(MOCK_PAGE, {
    hero_heading: body.heroHeading ?? MOCK_PAGE.hero_heading,
    hero_description: body.heroDescription ?? MOCK_PAGE.hero_description,
  })
  return delay(mapAdvertisePage(MOCK_PAGE))
}

export async function updateAdvertisePageStatus(status) {
  if (!USE_MOCK) {
    const { data } = await apiClient.patch('/advertise/page/status', { status })
    return mapAdvertisePage(data)
  }
  MOCK_PAGE.status = status
  return delay(mapAdvertisePage(MOCK_PAGE))
}

// ---------------------------------------------------------------------------
// Admin — metrics
// ---------------------------------------------------------------------------

export async function fetchAdvertiseMetrics() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/advertise/metrics')
    return data.map(mapAdvertiseMetric)
  }
  return delay(MOCK_METRICS.map(mapAdvertiseMetric))
}

function buildMetricPayload(payload) {
  return {
    label: payload.label,
    value: payload.value,
    unit: payload.unit || undefined,
    sourceNote: payload.sourceNote || undefined,
    asOfDate: payload.asOfDate || undefined,
    displayOrder: payload.displayOrder ?? 0,
    publicVisible: payload.publicVisible,
  }
}

export async function createAdvertiseMetric(payload) {
  const { data } = await apiClient.post('/advertise/metrics', buildMetricPayload(payload))
  return mapAdvertiseMetric(data)
}

export async function updateAdvertiseMetric(id, payload) {
  const { data } = await apiClient.patch(`/advertise/metrics/${id}`, buildMetricPayload(payload))
  return mapAdvertiseMetric(data)
}

export async function deleteAdvertiseMetric(id) {
  await apiClient.delete(`/advertise/metrics/${id}`)
}

// ---------------------------------------------------------------------------
// Admin — offerings
// ---------------------------------------------------------------------------

export async function fetchAdvertiseOfferings() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/advertise/offerings')
    return data.map(mapAdvertiseOffering)
  }
  return delay(MOCK_OFFERINGS.map(mapAdvertiseOffering))
}

function buildOfferingPayload(payload) {
  return {
    name: payload.name,
    shortDescription: payload.shortDescription || undefined,
    fullDescription: payload.fullDescription || undefined,
    features: payload.features,
    ctaLabel: payload.ctaLabel || undefined,
    displayOrder: payload.displayOrder ?? 0,
    featured: payload.featured,
    status: payload.status || undefined,
    pricingMode: payload.pricingMode || undefined,
    priceAmount: payload.priceAmount === '' || payload.priceAmount == null ? undefined : Number(payload.priceAmount),
    currency: payload.currency || undefined,
    pricingNote: payload.pricingNote || undefined,
  }
}

export async function createAdvertiseOffering(payload) {
  const { data } = await apiClient.post('/advertise/offerings', buildOfferingPayload(payload))
  return mapAdvertiseOffering(data)
}

export async function updateAdvertiseOffering(id, payload) {
  const { data } = await apiClient.patch(`/advertise/offerings/${id}`, buildOfferingPayload(payload))
  return mapAdvertiseOffering(data)
}

export async function deleteAdvertiseOffering(id) {
  await apiClient.delete(`/advertise/offerings/${id}`)
}

export async function fetchAdvertiseHistory() {
  if (!USE_MOCK) {
    const { data } = await apiClient.get('/advertise/history')
    return data
  }
  return delay([])
}
