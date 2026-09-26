import { apiClient, USE_MOCK } from './client'
import { delay } from './mockUtils'

let _mockNavigation
async function loadMockNavigation() {
  if (!_mockNavigation) _mockNavigation = await import('../mock/navigation')
  return _mockNavigation
}

// ---------------------------------------------------------------------------
// Public footer (GET /api/v1/public/footer) — consumed by Footer.jsx
// ---------------------------------------------------------------------------

function mapPublicFooterLink(item) {
  return { id: item.id, label: item.label, url: item.url, openNewTab: item.openNewTab }
}

function mapPublicFooterGroup(group) {
  return { key: group.key, heading: group.heading, links: (group.items || []).map(mapPublicFooterLink) }
}

function mapPublicFooter(data) {
  const settings = data.settings || {}
  return {
    brandDescription: settings.brandDescription || '',
    newsletterHeading: settings.newsletterHeading || '',
    newsletterDescription: settings.newsletterDescription || '',
    newsletterVisible: settings.newsletterVisible !== false,
    contactEmail: settings.contactEmail || '',
    copyrightText: settings.copyrightText || 'Women Shaping Futures. All rights reserved.',
    groups: (data.groups || []).map(mapPublicFooterGroup),
    social: (data.socialLinks || []).map((s) => ({ platform: s.platform, url: s.url, label: s.label })),
  }
}

// The old mock shape (a fixed explore/opportunity/wsf/legal object) predates
// dynamic, admin-creatable groups — adapted here into the new array shape
// rather than rewriting the mock data file, since mock mode only needs to
// stay renderable, not mirror every real-mode capability.
function adaptMockFooter({ footerNavigation, socialLinks }) {
  return {
    brandDescription: 'A global media, opportunity, and community platform for ambitious women.',
    newsletterHeading: 'WSF Weekly',
    newsletterDescription: 'Stories, jobs, and opportunities — every Thursday.',
    newsletterVisible: true,
    contactEmail: 'hello@womenshapingfutures.org',
    copyrightText: 'Women Shaping Futures. All rights reserved.',
    groups: Object.values(footerNavigation).map((group) => ({
      key: group.heading,
      heading: group.heading,
      links: group.links.map((l, i) => ({ id: `${group.heading}-${i}`, label: l.label, url: l.url, openNewTab: false })),
    })),
    social: socialLinks.map((s) => ({ platform: s.platform, url: s.url, label: null })),
  }
}

export async function fetchFooter() {
  if (!USE_MOCK) return mapPublicFooter((await apiClient.get('/public/footer')).data)
  const mock = await loadMockNavigation()
  return delay(adaptMockFooter(mock))
}

// ---------------------------------------------------------------------------
// Admin footer (GET/PUT /api/v1/admin/footer) — real-data-only, consumed by
// AdminFooter.jsx. No mock equivalent, same as api/navigation.js.
// ---------------------------------------------------------------------------

function mapAdminFooterLink(item) {
  return {
    id: item.id,
    label: item.label,
    itemType: item.itemType,
    url: item.url,
    topicId: item.topicId,
    seriesId: item.seriesId,
    pageId: item.pageId,
    openNewTab: item.openNewTab,
    effectiveUrl: item.effectiveUrl,
    warnings: item.warnings || [],
  }
}

function mapAdminFooterGroup(group) {
  return {
    key: group.key,
    heading: group.heading,
    visible: group.visible,
    items: (group.items || []).map(mapAdminFooterLink),
  }
}

function mapAdminSocialLink(link) {
  return {
    id: link.id,
    platform: link.platform,
    url: link.url,
    handle: link.handle,
    label: link.label,
    visible: link.visible,
  }
}

function mapAdminFooter(data) {
  return {
    groups: (data.groups || []).map(mapAdminFooterGroup),
    socialLinks: (data.socialLinks || []).map(mapAdminSocialLink),
    settings: {
      brandDescription: data.settings?.brandDescription || '',
      newsletterHeading: data.settings?.newsletterHeading || '',
      newsletterDescription: data.settings?.newsletterDescription || '',
      newsletterVisible: data.settings?.newsletterVisible !== false,
      contactEmail: data.settings?.contactEmail || '',
      copyrightText: data.settings?.copyrightText || '',
    },
  }
}

// Strips admin-only computed fields (effectiveUrl/warnings) back out
// before sending to PUT — the backend recomputes both; `id` is dropped
// too since the write path is a full replace (see
// backend/app/services/cms.py:replace_footer_groups), not a per-row
// upsert keyed by id.
function toLinkInput(item) {
  return {
    label: item.label,
    itemType: item.itemType,
    url: item.url || null,
    topicId: item.topicId || null,
    seriesId: item.seriesId || null,
    pageId: item.pageId || null,
    openNewTab: !!item.openNewTab,
    visible: item.visible !== false,
  }
}

function toGroupInput(group) {
  return {
    key: group.key || null,
    heading: group.heading,
    visible: group.visible !== false,
    items: (group.items || []).map(toLinkInput),
  }
}

function toSocialLinkInput(link) {
  return {
    platform: link.platform,
    url: link.url,
    handle: link.handle || null,
    label: link.label || null,
    visible: link.visible !== false,
  }
}

export async function fetchAdminFooter() {
  const { data } = await apiClient.get('/admin/footer')
  return mapAdminFooter(data)
}

export async function saveAdminFooter({ groups, socialLinks, settings }) {
  const body = {
    groups: groups.map(toGroupInput),
    socialLinks: socialLinks.map(toSocialLinkInput),
    settings,
  }
  const { data } = await apiClient.put('/admin/footer', body)
  return mapAdminFooter(data)
}
