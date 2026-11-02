import { apiClient } from './client'
import { navItemToInput } from '../utils/navigation'

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
    linkedLabel: item.linkedLabel || null,
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

// Admin-only computed fields (effectiveUrl/linkedLabel/warnings/sortOrder)
// and `id` are never sent back — the write path is a full replace per menu
// key (backend services/cms.py:replace_menu). utils/navigation.js's
// navItemToInput() sends ONLY the destination field the item's type uses.
const toItemInput = navItemToInput

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
