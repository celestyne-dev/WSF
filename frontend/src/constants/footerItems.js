// Mirrors the backend's controlled registries (SOCIAL_PLATFORMS in
// app/models/cms.py, MENU_ITEM_TYPES in the same file) by hand-maintained
// convention — same pattern as constants/navigationItems.js.

export const SOCIAL_PLATFORM_LABELS = {
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  facebook: 'Facebook',
  tiktok: 'TikTok',
  threads: 'Threads',
  pinterest: 'Pinterest',
  youtube: 'YouTube',
  whatsapp: 'WhatsApp',
  twitter: 'Twitter',
}

export const SOCIAL_PLATFORMS = Object.keys(SOCIAL_PLATFORM_LABELS)

// Footer links never use itemType "group" — a footer group is already the
// grouping construct (Group -> flat Links, no dropdown-of-dropdowns), so
// there's no need for a second, non-clickable "group" item type inside one.
export const FOOTER_LINK_TYPE_LABELS = {
  route: 'Internal route',
  page: 'Page',
  topic: 'Topic',
  series: 'Series',
  external: 'External URL',
}

export const FOOTER_LINK_TYPES = Object.keys(FOOTER_LINK_TYPE_LABELS)

export const FOOTER_MAX_GROUPS = 8

// A footer link resolving to one of these public paths is a required
// legal link — removing one gets a stronger confirmation than an ordinary
// link (see AdminFooter's handleRemoveLink) rather than a hard block, so
// admins can still legitimately restructure the Legal group when needed.
export const LEGAL_LINK_PATHS = ['/privacy', '/terms', '/cookies', '/editorial-policy']

let _tempId = -1
export function tempFooterId() {
  _tempId -= 1
  return _tempId
}

export function newFooterLink(type = 'route') {
  return {
    id: tempFooterId(),
    label: '',
    itemType: type,
    url: type === 'route' ? '' : null,
    topicId: null,
    seriesId: null,
    pageId: null,
    openNewTab: false,
    style: 'standard',
    visible: true,
    effectiveUrl: null,
    warnings: [],
    children: [],
  }
}

export function newFooterGroup() {
  return {
    key: null,
    heading: '',
    visible: true,
    items: [],
  }
}

export function newSocialLink() {
  return {
    id: tempFooterId(),
    platform: 'linkedin',
    url: '',
    handle: '',
    label: '',
    visible: true,
  }
}
