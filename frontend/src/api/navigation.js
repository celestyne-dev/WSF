import { apiClient } from './client'

// Navigation CMS admin surface — real-data-only, same as Pages/Taxonomy's
// admin areas (there's no mock/navigation.js admin equivalent; public
// consumption of navigation still goes through api/site.js:fetchNavigation,
// unchanged, for both mock and real mode).

function mapMenuItemAdmin(item) {
  return {
    id: item.id,
    label: item.label,
    itemType: item.itemType,
    url: item.url,
    topicId: item.topicId,
    seriesId: item.seriesId,
    pageId: item.pageId,
    openNewTab: item.openNewTab,
    style: item.style,
    sortOrder: item.sort_order,
    visible: item.visible,
    effectiveUrl: item.effectiveUrl,
    warnings: item.warnings || [],
    children: (item.children || []).map(mapMenuItemAdmin),
  }
}

function mapMenuAdmin(menu) {
  return {
    id: menu.id,
    key: menu.key,
    heading: menu.heading,
    items: (menu.items || []).map(mapMenuItemAdmin),
  }
}

// Strips the admin-only computed fields (effectiveUrl/warnings/sortOrder)
// back out before sending to PUT — the backend derives/recomputes all of
// those, and `id` is dropped too since the write path is a full replace
// per menu key (see backend services/cms.py:replace_menu), not a per-row
// upsert keyed by id.
function toItemInput(item) {
  return {
    label: item.label,
    itemType: item.itemType,
    url: item.url || null,
    topicId: item.topicId || null,
    seriesId: item.seriesId || null,
    pageId: item.pageId || null,
    openNewTab: !!item.openNewTab,
    style: item.style || 'standard',
    visible: item.visible !== false,
    children: (item.children || []).map(toItemInput),
  }
}

export async function fetchAdminNavigation() {
  const { data } = await apiClient.get('/admin/navigation')
  return data.map(mapMenuAdmin)
}

// Saves exactly one menu's full item tree — every other menu key is left
// untouched (see AdminNavigationResource's docstring), so editing "primary"
// can never accidentally wipe the footer menus.
export async function saveMenu(key, heading, items) {
  const body = { menus: [{ key, heading, items: items.map(toItemInput) }] }
  const { data } = await apiClient.put('/admin/navigation', body)
  return data.map(mapMenuAdmin)
}
