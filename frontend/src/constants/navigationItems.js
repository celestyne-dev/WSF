// Mirrors backend/app/models/cms.py's MENU_ITEM_TYPES / MENU_ITEM_STYLES /
// MENU_MAX_DEPTH — the controlled registry AdminNavigation's item editor
// keys off of. Kept in sync by convention (like RESERVED_SLUGS), not
// shared code.
export const MENU_ITEM_TYPE_LABELS = {
  route: 'Internal route',
  topic: 'Topic',
  series: 'Series',
  page: 'Page',
  external: 'External URL',
  group: 'Dropdown group (no link)',
}

export const MENU_ITEM_TYPES = Object.keys(MENU_ITEM_TYPE_LABELS)
export const MENU_ITEM_STYLES = ['standard', 'cta']
export const MENU_MAX_DEPTH = 2

export const EDITABLE_MENUS = [
  { key: 'primary', label: 'Primary navigation', hasHeading: false },
  { key: 'secondary', label: 'Utility bar', hasHeading: false },
  { key: 'footer_explore', label: 'Footer — Explore', hasHeading: true },
  { key: 'footer_opportunity', label: 'Footer — Opportunity', hasHeading: true },
  { key: 'footer_wsf', label: 'Footer — WSF', hasHeading: true },
  { key: 'footer_legal', label: 'Footer — Legal', hasHeading: true },
]

let tempIdCounter = 0
export function tempItemId() {
  tempIdCounter -= 1
  return tempIdCounter
}

export function newNavItem(type = 'route') {
  return {
    id: tempItemId(),
    label: '',
    itemType: type,
    url: type === 'route' ? '/' : null,
    topicId: null,
    seriesId: null,
    pageId: null,
    openNewTab: false,
    style: 'standard',
    visible: true,
    warnings: [],
    children: [],
  }
}
