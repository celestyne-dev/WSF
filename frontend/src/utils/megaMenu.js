// Pure (Node-testable) builder: CMS navigation (GET /public/navigation,
// shape from backend services/navigation.py serialize_public_menu_item)
// -> the header's presentation model, shared by the desktop mega menus and
// the mobile accordion so both always show the same destinations.
//
//   [{ id, label, link, style, menu: null | {
//        key, icon, title, description, cta: {label, link} | null,
//        groups: [{ key, label, links: [{ id, label, link, description, icon }] }]
//   }}]
//
// `link` is utils/navigation.js publicNavLink() output (never a fallback "/").
import { publicNavLink } from './navigation.js'
import {
  LINK_PRESENTATION,
  MENU_PRESENTATION,
  MIN_TOP_LEVEL,
  SECONDARY_FALLBACK_MENU,
  SECONDARY_PLACEMENT,
} from '../constants/megaMenu.js'

// "/opportunities/?x=1#y" -> "/opportunities"; external URLs -> null.
export function navPath(link) {
  if (!link || link.kind !== 'internal') return null
  const path = link.to.split('#')[0].split('?')[0].replace(/\/+$/, '')
  return path || '/'
}

function toLink(item) {
  const link = publicNavLink(item)
  if (!link || link.kind === 'group') return null
  const meta = LINK_PRESENTATION[navPath(link)] || {}
  return { id: item.id, label: item.label, link, description: meta.description || null, icon: meta.icon || null, group: meta.group || null }
}

// An item and (one level of) its children, as flat link entries.
function flattenLinks(item) {
  const own = toLink(item)
  const children = (item.children || []).map(toLink).filter(Boolean)
  return own ? [own, ...children] : children
}

function groupLinks(links, groupDefs) {
  const seen = new Set()
  const unique = links.filter((l) => {
    const id = l.link.kind === 'internal' ? navPath(l.link) : l.link.href
    if (seen.has(id)) return false
    seen.add(id)
    return true
  })
  const known = new Set(groupDefs.map((g) => g.key))
  const groups = groupDefs.map((g) => ({ key: g.key, label: g.label, links: unique.filter((l) => l.group === g.key) }))
  const rest = unique.filter((l) => !known.has(l.group))
  if (rest.length) groups.push({ key: 'more', label: groupDefs.length ? 'More' : null, links: rest })
  return groups
    .filter((g) => g.links.length)
    .map((g) => ({ ...g, links: g.links.map(({ id, label, link, description, icon }) => ({ id, label, link, description, icon })) }))
}

export function buildHeaderNavigation(navigation) {
  const primary = Array.isArray(navigation?.primary) ? navigation.primary : []
  const secondary = Array.isArray(navigation?.secondary) ? navigation.secondary : []

  const entries = primary
    .map((item) => {
      const link = publicNavLink(item)
      if (!link) return null
      const config = link.kind === 'internal' ? MENU_PRESENTATION[navPath(link)] : undefined
      return { item, link, config }
    })
    .filter(Boolean)

  // Fold an extra top-level item (e.g. Events, Shop) into the menu that
  // presents it (Opportunities, Resources), keeping the bar to about 5-7
  // items. Never folds a CTA-styled item, never a menu host itself, and
  // never below MIN_TOP_LEVEL visible items.
  const byKey = new Map(entries.filter((e) => e.config).map((e) => [e.config.key, e]))
  const absorbedBy = new Map()
  let visibleCount = entries.length
  for (const entry of entries) {
    if (entry.config || entry.item.style === 'cta' || visibleCount <= MIN_TOP_LEVEL) continue
    const path = navPath(entry.link)
    const host = entries.find((e) => e.config?.absorbs?.includes(path))
    if (host) {
      absorbedBy.set(entry, host)
      visibleCount -= 1
    }
  }

  const extraLinks = new Map() // host entry -> links folded in
  const addTo = (host, links) => extraLinks.set(host, [...(extraLinks.get(host) || []), ...links])
  for (const [entry, host] of absorbedBy) addTo(host, flattenLinks(entry.item))

  const menuEntries = entries.filter((e) => !absorbedBy.has(e) && (e.config || e.item.children?.length))
  const fallbackHost = byKey.get(SECONDARY_FALLBACK_MENU) || menuEntries[menuEntries.length - 1] || null
  const orphanSecondary = []
  for (const item of secondary) {
    const links = flattenLinks(item)
    if (!links.length) continue
    const path = navPath(links[0].link)
    const host = byKey.get(SECONDARY_PLACEMENT[path]) || fallbackHost
    if (host && !absorbedBy.has(host)) addTo(host, links)
    else orphanSecondary.push(...links)
  }

  const result = entries
    .filter((e) => !absorbedBy.has(e))
    .map((entry) => {
      const { item, link, config } = entry
      const childLinks = (item.children || []).map(toLink).filter(Boolean)
      const links = [...childLinks, ...(extraLinks.get(entry) || [])]
      if (!config && !links.length) {
        return { id: item.id, label: item.label, link, style: item.style || 'standard', menu: null }
      }
      const groups = groupLinks(links, config?.groups || [])
      if (!groups.length && !config) return { id: item.id, label: item.label, link, style: item.style || 'standard', menu: null }
      const navigable = link.kind !== 'group'
      return {
        id: item.id,
        label: item.label,
        link,
        style: item.style || 'standard',
        menu: {
          key: config?.key || `item-${item.id}`,
          icon: config?.icon || null,
          title: item.label,
          description: config?.description || null,
          cta: navigable ? { label: config?.ctaLabel || `Explore ${item.label}`, link } : null,
          groups,
        },
      }
    })
  // Nowhere to show a secondary link (no menus at all): keep it reachable
  // as a plain top-level link rather than dropping it.
  for (const link of orphanSecondary) result.push({ id: link.id, label: link.label, link: link.link, style: 'standard', menu: null })
  return result
}

// Is `pathname` inside this entry (its own destination or any menu link)?
export function isEntryActive(entry, pathname) {
  const current = (pathname || '/').replace(/\/+$/, '') || '/'
  const paths = [navPath(entry.link), entry.menu?.cta ? navPath(entry.menu.cta.link) : null]
  for (const group of entry.menu?.groups || []) for (const l of group.links) paths.push(navPath(l.link))
  return paths.some((p) => p && p !== '/' && (current === p || current.startsWith(`${p}/`)))
}
