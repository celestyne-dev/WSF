// Homepage Builder — pure (Node-testable) rules for the two configurable
// section types, mirroring backend app/services/homepage_collections.py:
//
//   career_pathways     2–8 cards; each card's destination uses the SAME
//                       destination types as Navigation CMS (utils/
//                       navigation.js) minus "group". Never a "/" fallback.
//   content_collection  one entity type, manual (ordered slugs) or
//                       automatic (entity-aware sort + filters).
//
// Changing a card's destination type, a collection's entity type or its
// selection mode always clears the config that no longer applies, so a
// stale url/page/slug/filter can never be saved by accident.
import { DESTINATION_FIELD_BY_TYPE, isExternalUrl, publicNavLink, validateNavItem } from './navigation.js'

// --- career pathways -----------------------------------------------------------

export const PATHWAY_MIN_CARDS = 2
export const PATHWAY_MAX_CARDS = 8

export const PATHWAY_ICONS = [
  'briefcase', 'graduation-cap', 'users', 'book-open', 'lightbulb', 'compass', 'calendar',
  'sparkles', 'heart-handshake', 'rocket', 'target', 'megaphone', 'globe', 'award',
]

export const PATHWAY_DESTINATION_TYPES = ['route', 'page', 'topic', 'series', 'external']

export const PATHWAY_DESTINATION_LABELS = {
  route: 'Internal path (e.g. /jobs, /resources, /learning/…)',
  page: 'CMS Page',
  topic: 'Topic',
  series: 'Series',
  external: 'External URL',
}

const PATHWAY_DESTINATION_FIELDS = ['url', 'pageId', 'topicId', 'seriesId']

export function newPathwayCard() {
  return {
    title: '', description: null, eyebrow: null, icon: null, mediaId: null, ariaLabel: null,
    destinationType: null, url: null, pageId: null, topicId: null, seriesId: null, openNewTab: false,
  }
}

// Switch a card's destination type: every destination field is cleared so
// the new type starts empty and must be chosen explicitly.
export function changePathwayDestination(card, nextType) {
  if (card.destinationType === nextType) return card
  const next = { ...card, destinationType: nextType || null, openNewTab: false, linkedLabel: null }
  for (const field of PATHWAY_DESTINATION_FIELDS) next[field] = null
  return next
}

// Icon and image are mutually exclusive: picking one clears the other.
export function setPathwayIcon(card, icon) {
  return { ...card, icon: icon || null, mediaId: icon ? null : card.mediaId, media: icon ? null : card.media }
}

export function setPathwayMedia(card, media) {
  return { ...card, media: media || null, mediaId: media?.id ?? null, icon: media ? null : card.icon }
}

function trimOrNull(value) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

// Editor card -> exactly the PUT shape (only the destination field its type uses).
export function pathwayCardToInput(card) {
  const type = card.destinationType || null
  const keep = type ? DESTINATION_FIELD_BY_TYPE[type] : null
  const input = {
    title: (card.title || '').trim(),
    description: trimOrNull(card.description),
    eyebrow: trimOrNull(card.eyebrow),
    ariaLabel: trimOrNull(card.ariaLabel),
    icon: card.icon || null,
    mediaId: card.icon ? null : card.mediaId ?? null,
    destinationType: type,
    url: null,
    pageId: null,
    topicId: null,
    seriesId: null,
    openNewTab: type === 'external' ? !!card.openNewTab : false,
  }
  if (keep === 'url') input.url = trimOrNull(card.url)
  else if (keep) input[keep] = card[keep] || null
  return input
}

export function validatePathwayCard(card, index = 0) {
  const name = card.title?.trim() ? `"${card.title.trim()}"` : `Card ${index + 1}`
  if (!card.title?.trim()) return `Card ${index + 1} needs a title.`
  if (!PATHWAY_DESTINATION_TYPES.includes(card.destinationType)) return `${name} needs a destination.`
  if (card.icon && card.mediaId) return `${name}: choose an icon or an image, not both.`
  // Same destination rules as a navigation item (label = card title).
  const navError = validateNavItem({ ...card, label: card.title, itemType: card.destinationType })
  return navError
}

export function validatePathwaysModule(module) {
  const cards = module.config?.cards || []
  if (cards.length > PATHWAY_MAX_CARDS) return `Career Pathways supports at most ${PATHWAY_MAX_CARDS} cards.`
  if (module.enabled !== false && cards.length < PATHWAY_MIN_CARDS) {
    return `Career Pathways needs at least ${PATHWAY_MIN_CARDS} cards (or hide the section).`
  }
  for (let i = 0; i < cards.length; i += 1) {
    const error = validatePathwayCard(cards[i], i)
    if (error) return error
  }
  return validateSectionCta(module)
}

// Public: a resolved card from GET /public/homepage -> link decision.
export function pathwayCardLink(card) {
  if (!card?.href) return null
  return publicNavLink({ url: card.href, linkType: card.linkType, openNewTab: card.openNewTab })
}

// --- content collection -----------------------------------------------------

export const COLLECTION_MIN_ITEMS = 1
export const COLLECTION_MAX_ITEMS = 8
export const COLLECTION_DEFAULT_ITEMS = 4
export const COLLECTION_LAYOUTS = [
  { value: 'grid', label: 'Grid' },
  { value: 'compact', label: 'Compact grid' },
]

export const RESOURCE_ACCESS_TYPES = [
  { value: 'direct_download', label: 'Free download' },
  { value: 'email_gate', label: 'Email required' },
  { value: 'member_only', label: 'Members only' },
  { value: 'circle_only', label: 'Circle only' },
  { value: 'premium', label: 'Premium (paid)' },
  { value: 'external_link', label: 'External link' },
]

export const RESOURCE_TYPES = [
  'Guide', 'Workbook', 'Template', 'Checklist', 'Planner', 'Toolkit', 'Ebook', 'Worksheet', 'Report',
  'Download', 'Video Resource', 'External Resource', 'Playbook', 'Scripts', 'Challenge', 'Assessment', 'Research', 'Other',
].map((t) => ({ value: t, label: t }))

export const LEARNING_PROGRAM_TYPES = [
  { value: 'course', label: 'Course' },
  { value: 'masterclass', label: 'Masterclass' },
  { value: 'program', label: 'Program' },
  { value: 'learning_series', label: 'Learning series' },
  { value: 'challenge', label: 'Challenge' },
]

// "Most read" is intentionally absent: the only popularity signal is a
// public, client-sent analytics event that isn't reliable enough to rank by.
export const COLLECTION_ENTITIES = {
  articles: {
    label: 'Articles',
    sorts: [{ value: 'latest', label: 'Latest' }, { value: 'featured', label: 'Featured only' }],
    filters: { topic: { label: 'Topic', kind: 'topic' }, series: { label: 'Series', kind: 'series' } },
  },
  people: {
    label: 'People',
    sorts: [{ value: 'newest', label: 'Newest' }, { value: 'featured', label: 'Featured only' }],
    filters: { series: { label: 'Series', kind: 'series' } },
  },
  opportunities: {
    label: 'Opportunities',
    sorts: [{ value: 'newest', label: 'Newest' }, { value: 'closing_soon', label: 'Closing soon (by deadline)' }],
    filters: {},
  },
  jobs: {
    label: 'Jobs',
    sorts: [{ value: 'newest', label: 'Newest' }, { value: 'closing_soon', label: 'Closing soon (by deadline)' }],
    filters: {},
  },
  events: { label: 'Events', sorts: [{ value: 'upcoming', label: 'Upcoming' }], filters: {} },
  resources: {
    label: 'Resources',
    sorts: [{ value: 'newest', label: 'Newest' }, { value: 'featured', label: 'Featured only' }],
    filters: {
      accessType: { label: 'Access type', kind: 'choice', options: RESOURCE_ACCESS_TYPES },
      resourceType: { label: 'Resource type', kind: 'choice', options: RESOURCE_TYPES },
    },
  },
  learning: {
    label: 'Learning',
    sorts: [{ value: 'newest', label: 'Newest' }, { value: 'featured', label: 'Featured only' }],
    filters: { programType: { label: 'Program type', kind: 'choice', options: LEARNING_PROGRAM_TYPES } },
  },
}

export const COLLECTION_ENTITY_TYPES = Object.keys(COLLECTION_ENTITIES)

function modeDefaults(entityType, mode) {
  if (mode === 'manual') return { slugs: [] }
  return { itemCount: COLLECTION_DEFAULT_ITEMS, sort: COLLECTION_ENTITIES[entityType].sorts[0].value, filters: {} }
}

export function newCollectionConfig(entityType = 'articles', mode = 'automatic') {
  return { eyebrow: null, entityType, layout: 'grid', ...modeDefaults(entityType, mode) }
}

// Entity change: keep only the presentational settings (eyebrow, layout);
// sort, filters and picked items belong to the old entity and are cleared.
export function changeCollectionEntity(module, entityType) {
  const config = module.config || {}
  if (config.entityType === entityType) return module
  const mode = module.selectionMode === 'manual' ? 'manual' : 'automatic'
  return {
    ...module,
    config: { eyebrow: config.eyebrow ?? null, entityType, layout: config.layout || 'grid', ...modeDefaults(entityType, mode) },
  }
}

// Mode change: manual picks and automatic sort/filters never coexist.
export function changeCollectionMode(module, mode) {
  if (module.selectionMode === mode) return module
  const config = module.config || {}
  const entityType = COLLECTION_ENTITIES[config.entityType] ? config.entityType : 'articles'
  return {
    ...module,
    selectionMode: mode,
    config: { eyebrow: config.eyebrow ?? null, entityType, layout: config.layout || 'grid', ...modeDefaults(entityType, mode) },
  }
}

// Editor config -> exactly the keys the backend keeps for this entity+mode.
export function collectionConfigToInput(config, mode) {
  const entityType = config?.entityType
  const spec = COLLECTION_ENTITIES[entityType]
  const base = { eyebrow: trimOrNull(config?.eyebrow), entityType, layout: config?.layout || 'grid' }
  if (!spec) return base
  if (mode === 'manual') return { ...base, slugs: [...(config.slugs || [])] }
  const filters = {}
  for (const key of Object.keys(spec.filters)) {
    const value = config.filters?.[key]
    if (value) filters[key] = value
  }
  return {
    ...base,
    itemCount: config.itemCount ?? COLLECTION_DEFAULT_ITEMS,
    sort: spec.sorts.some((s) => s.value === config.sort) ? config.sort : spec.sorts[0].value,
    filters,
  }
}

export function validateCollectionModule(module) {
  const config = module.config || {}
  if (!COLLECTION_ENTITIES[config.entityType]) return 'Choose what the Content Collection shows.'
  if (!['manual', 'automatic'].includes(module.selectionMode)) return 'Choose manual or automatic selection.'
  if (module.selectionMode === 'manual') {
    const slugs = config.slugs || []
    if (slugs.length === 0) return 'Pick at least one item for the Content Collection, or switch to automatic.'
    if (slugs.length > COLLECTION_MAX_ITEMS) return `Pick at most ${COLLECTION_MAX_ITEMS} items.`
  } else {
    const n = config.itemCount ?? COLLECTION_DEFAULT_ITEMS
    if (!Number.isInteger(n) || n < COLLECTION_MIN_ITEMS || n > COLLECTION_MAX_ITEMS) {
      return `Show between ${COLLECTION_MIN_ITEMS} and ${COLLECTION_MAX_ITEMS} items.`
    }
  }
  return validateSectionCta(module)
}

// --- shared ---------------------------------------------------------------------

export function validateSectionCta(module) {
  const label = trimOrNull(module.ctaLabel)
  const url = trimOrNull(module.ctaUrl)
  if (!label && !url) return null
  if (!label || !url) return 'A section link needs both a label and a destination.'
  if (url.startsWith('/')) {
    return validateNavItem({ label, itemType: 'route', url }) ? `Section link: ${validateNavItem({ label, itemType: 'route', url })}` : null
  }
  return isExternalUrl(url) ? null : 'Section links must be an internal path starting with "/" or a full https:// URL.'
}

// Pre-save check for the whole builder: first problem, or null.
export function validateHomepageExtras(modules) {
  for (const module of modules || []) {
    const error =
      module.type === 'career_pathways' ? validatePathwaysModule(module)
        : module.type === 'content_collection' ? validateCollectionModule(module)
          : null
    if (error) return error
  }
  return null
}

// Save payload config for one module (other types pass through unchanged).
export function moduleConfigToInput(module) {
  if (module.type === 'career_pathways') {
    return { eyebrow: trimOrNull(module.config?.eyebrow), cards: (module.config?.cards || []).map(pathwayCardToInput) }
  }
  if (module.type === 'content_collection') return collectionConfigToInput(module.config, module.selectionMode)
  return module.config || {}
}
