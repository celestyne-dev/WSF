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

// Footer groups (footer_* Menu keys) are deliberately NOT listed here.
// Footer CMS (AdminFooter.jsx, PUT /admin/footer) is their one canonical
// editor, gated by its own footer.manage/footer.publish permissions — see
// AdminNavigationResource.put's docstring in backend/app/api/v1/admin.py
// for the server-side half of this boundary. Listing a footer_* key here
// would let an ordinary Navigation editor (navigation.manage only) reach
// a Menu row Footer CMS owns.
export const EDITABLE_MENUS = [
  { key: 'primary', label: 'Primary navigation', hasHeading: false },
  { key: 'secondary', label: 'Utility bar', hasHeading: false },
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
