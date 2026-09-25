import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'
import { mapMediaRef } from '../utils/media'

// Each mock dataset here is only needed when VITE_USE_MOCK=true —
// dynamic-imported per module so a real-mode production build never
// fetches any of them.
let _mockNavigation
async function loadMockNavigation() {
  if (!_mockNavigation) _mockNavigation = await import('../mock/navigation')
  return _mockNavigation
}
let _mockHomepageModules
async function loadMockHomepageModules() {
  if (!_mockHomepageModules) _mockHomepageModules = await import('../mock/homepageModules')
  return _mockHomepageModules
}
let _mockAdmin
async function loadMockAdmin() {
  if (!_mockAdmin) _mockAdmin = await import('../mock/admin')
  return _mockAdmin
}

function mapNavItem(item) {
  return {
    id: item.id,
    label: item.label,
    url: item.url,
    order: item.sort_order,
    visible: item.visible,
    children: (item.children || []).map((c) => ({ id: c.id, label: c.label, url: c.url })),
  }
}

function mapFooterGroup(menus, key) {
  const menu = menus[key]
  if (!menu) return { heading: '', links: [] }
  return { heading: menu.heading, links: (menu.items || []).map((i) => ({ label: i.label, url: i.url })) }
}

function mapNavigation(data) {
  const menus = data.menus || {}
  return {
    primary: (menus.primary?.items || []).map(mapNavItem),
    secondary: (menus.secondary?.items || []).map(mapNavItem),
    footer: {
      explore: mapFooterGroup(menus, 'footer_explore'),
      opportunity: mapFooterGroup(menus, 'footer_opportunity'),
      wsf: mapFooterGroup(menus, 'footer_wsf'),
      legal: mapFooterGroup(menus, 'footer_legal'),
    },
    social: (data.socialLinks || []).map((s) => ({ platform: s.platform, url: s.url, handle: s.handle })),
  }
}

function mapHomepageModule(m) {
  return {
    id: m.id,
    type: m.type,
    enabled: m.enabled,
    order: m.sort_order,
    heading: m.heading,
    subheading: m.subheading,
    selectionMode: m.selection_mode,
    media: mapMediaRef(m.media),
    ctaLabel: m.cta_label,
    ctaUrl: m.cta_url,
    secondaryCtaLabel: m.secondary_cta_label,
    secondaryCtaUrl: m.secondary_cta_url,
    ...(m.config || {}),
  }
}

export async function fetchNavigation() {
  if (!USE_MOCK) return mapNavigation((await apiClient.get('/public/navigation')).data)
  const { primaryNavigation, secondaryNavigation, footerNavigation, socialLinks } = await loadMockNavigation()
  return delay({ primary: primaryNavigation, secondary: secondaryNavigation, footer: footerNavigation, social: socialLinks })
}

// GET /api/v1/public/settings — a flexible key/value store (site name,
// tagline, contact email, maintenance mode, ...). No mock equivalent
// exists since nothing was previously CMS-editable here; mock mode
// returns {} so consumers fall back to their current static copy.
export async function fetchSiteSettings() {
  if (!USE_MOCK) return (await apiClient.get('/public/settings')).data
  return delay({})
}

export async function fetchHomepageModules() {
  // The backend response carries a `meta.updatedAt` cache hint alongside
  // the module array, so the shared response interceptor (see api/client.js)
  // treats it like any other {data: [...], meta} paginated-list response
  // and unwraps it to {items, pagination} rather than a bare array.
  if (!USE_MOCK) return (await apiClient.get('/public/homepage')).data.items.map(mapHomepageModule)
  const { homepageModules } = await loadMockHomepageModules()
  return delay([...homepageModules].filter((m) => m.enabled).sort((a, b) => a.order - b.order))
}

// Newsletter archive/subscribe/unsubscribe live in api/newsletter.js —
// import fetchNewsletterArchive / subscribeToNewsletter from there.

// GET /api/v1/partnerships/audience — CMS-editable LinkedIn/newsletter/
// website audience numbers for the About, Community, and Partnerships
// pages' media-kit stats. Never hard-code these into a page component.
export async function fetchAudienceStats() {
  if (!USE_MOCK) return (await apiClient.get('/partnerships/audience')).data
  const { audienceStats } = await loadMockAdmin()
  return delay(audienceStats)
}

// submitPartnershipInquiry lives in api/partnerships.js.
// submitNomination lives in api/nominations.js.
