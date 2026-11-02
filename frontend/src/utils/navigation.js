// Navigation CMS — the ONE shared, pure (Node-testable) definition of how a
// navigation item's destination works, used by the admin editor
// (AdminNavigation / NavigationItemRow / NavigationItemFields), the admin
// API client (api/navigation.js) and the public renderers (Header,
// MobileNav). Mirrors backend services/navigation.py's
// DESTINATION_FIELD_BY_TYPE / clean_item_destination().
//
// Rules this module guarantees:
//   * A destination is NEVER silently "/" — a new or re-typed item starts
//     with NO destination and must be given one explicitly.
//   * Switching type clears every destination field of the previous type,
//     so a stale url/page/topic/series can't become a hidden destination.
//   * The save payload carries only the field the type actually uses.
//   * Public rendering never falls back to "/": a group (or an item with no
//     resolved url) is a non-navigating dropdown trigger, not a link.

export const NAV_ITEM_TYPES = ['route', 'page', 'topic', 'series', 'external', 'group']

// type -> the one item field holding its destination (null for a group).
export const DESTINATION_FIELD_BY_TYPE = {
  route: 'url',
  external: 'url',
  page: 'pageId',
  topic: 'topicId',
  series: 'seriesId',
  group: null,
}

const DESTINATION_FIELDS = ['url', 'pageId', 'topicId', 'seriesId']

// Which editor inputs the admin form shows for each type.
export function navEditorFields(type) {
  return {
    route: ['url'],
    external: ['url', 'openNewTab'],
    page: ['pageId'],
    topic: ['topicId'],
    series: ['seriesId'],
    group: [],
  }[type] || []
}

export function isExternalUrl(url) {
  return typeof url === 'string' && /^https?:\/\//i.test(url)
}

// Change an item's destination type: keep its label/visibility/children,
// clear EVERY destination field (and the stale server preview) so the new
// type starts empty and must be filled in explicitly.
export function changeNavItemType(item, nextType) {
  if (item.itemType === nextType) return item
  const next = { ...item, itemType: nextType, effectiveUrl: null, linkedLabel: null, warnings: [] }
  for (const field of DESTINATION_FIELDS) next[field] = null
  if (nextType !== 'external') next.openNewTab = false
  if (nextType === 'group') next.style = 'standard'
  return next
}

// Editor item -> exactly the admin PUT input for that type (recursive).
export function navItemToInput(item) {
  const type = item.itemType || 'route'
  const keep = DESTINATION_FIELD_BY_TYPE[type]
  const input = {
    label: (item.label || '').trim(),
    itemType: type,
    url: null,
    pageId: null,
    topicId: null,
    seriesId: null,
    openNewTab: type === 'external' ? !!item.openNewTab : false,
    style: type === 'group' ? 'standard' : item.style || 'standard',
    visible: item.visible !== false,
    children: (item.children || []).map(navItemToInput),
  }
  if (keep === 'url') input.url = typeof item.url === 'string' ? item.url.trim() || null : null
  else if (keep) input[keep] = item[keep] || null
  return input
}

const RESERVED_PREFIXES = ['/admin', '/api']

// Client-side mirror of backend validate_item_type_requirements — returns a
// message for the first problem in this one item (not its children), or null.
export function validateNavItem(item) {
  const type = item.itemType
  const name = item.label?.trim() ? `"${item.label.trim()}"` : 'An untitled item'
  if (!item.label?.trim()) return 'Every navigation item needs a label.'
  if (!NAV_ITEM_TYPES.includes(type)) return `${name} has an unknown destination type.`
  if (type === 'route') {
    const url = (item.url || '').trim()
    if (!url) return `${name} needs an internal path (for example /community).`
    if (!url.startsWith('/') || url.startsWith('//')) return `${name}: internal paths must start with a single "/".`
    const lowered = url.toLowerCase()
    if (RESERVED_PREFIXES.some((p) => lowered === p || lowered.startsWith(`${p}/`))) {
      return `${name}: navigation can't link into admin or API routes.`
    }
  }
  if (type === 'external' && !isExternalUrl((item.url || '').trim())) {
    return `${name} needs a full http:// or https:// URL.`
  }
  if (type === 'page' && !item.pageId) return `${name} needs a Page selected.`
  if (type === 'topic' && !item.topicId) return `${name} needs a Topic selected.`
  if (type === 'series' && !item.seriesId) return `${name} needs a Series selected.`
  return null
}

export function validateNavItems(items) {
  for (const item of items || []) {
    const error = validateNavItem(item) || validateNavItems(item.children)
    if (error) return error
  }
  return null
}

// Admin row summary: where this item points right now, from the CURRENT
// form state (never a stale server preview after a local type change).
export function navItemPreview(item) {
  if (item.itemType === 'route' || item.itemType === 'external') return item.url?.trim() || 'No destination set'
  if (item.itemType === 'group') return null
  const id = item[DESTINATION_FIELD_BY_TYPE[item.itemType]]
  if (!id) return 'Nothing selected'
  return item.effectiveUrl || item.linkedLabel || 'Selected — resolved on save'
}

// Public renderer decision for one item from GET /public/navigation:
//   { kind: 'internal', to } | { kind: 'external', href, newTab } |
//   { kind: 'group' } | null (nothing renderable). Prefers the server's
// `linkType`; infers from `url` for older/mock payloads. Never returns "/"
// unless "/" is the item's real destination.
export function publicNavLink(item) {
  if (!item) return null
  const url = typeof item.url === 'string' && item.url ? item.url : null
  const kind = item.linkType || (item.itemType === 'group' || !url ? 'group' : isExternalUrl(url) ? 'external' : 'internal')
  if (kind === 'group' || !url) return item.children?.length ? { kind: 'group' } : null
  if (kind === 'external') return { kind: 'external', href: url, newTab: !!item.openNewTab }
  return { kind: 'internal', to: url }
}

// rel for an external nav link: noopener+noreferrer when it opens a new
// tab, plain noopener otherwise.
export function externalRel(newTab) {
  return newTab ? 'noopener noreferrer' : 'noopener'
}
