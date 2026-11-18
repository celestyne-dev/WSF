// Plain-Node tests for the Homepage Builder's Career Pathways / Content
// Collection rules (stale-config clearing, save payloads, validation and
// the public link decision).
// Run with: node --test src/utils/homepageCollections.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  COLLECTION_ENTITIES,
  changeCollectionEntity,
  changeCollectionMode,
  changePathwayDestination,
  collectionConfigToInput,
  moduleConfigToInput,
  newCollectionConfig,
  newPathwayCard,
  pathwayCardLink,
  pathwayCardToInput,
  setPathwayIcon,
  setPathwayMedia,
  validateCollectionModule,
  validateHomepageExtras,
  validatePathwayCard,
  validatePathwaysModule,
} from './homepageCollections.js'

const routeCard = (title, url = '/jobs') => ({ ...newPathwayCard(), title, destinationType: 'route', url })

test('a new pathway card has no destination (never "/")', () => {
  const card = newPathwayCard()
  assert.equal(card.destinationType, null)
  assert.equal(card.url, null)
  assert.match(validatePathwayCard({ ...card, title: 'x' }), /needs a destination/)
})

test('changing a card destination type clears every destination field', () => {
  const card = { ...routeCard('A', '/old'), pageId: 3, openNewTab: true }
  const next = changePathwayDestination(card, 'topic')
  assert.equal(next.destinationType, 'topic')
  assert.equal(next.url, null)
  assert.equal(next.pageId, null)
  assert.equal(next.openNewTab, false)
  assert.equal(changePathwayDestination(next, 'topic'), next)
})

test('pathway save payload keeps only the field its type uses', () => {
  const input = pathwayCardToInput({ ...routeCard(' Find work ', ' /jobs '), pageId: 9, topicId: 2, description: '  ', linkedLabel: 'x' })
  assert.deepEqual(input, {
    title: 'Find work', description: null, eyebrow: null, ariaLabel: null, icon: null, mediaId: null,
    destinationType: 'route', url: '/jobs', pageId: null, topicId: null, seriesId: null, openNewTab: false,
  })
  const page = pathwayCardToInput({ ...newPathwayCard(), title: 'P', destinationType: 'page', pageId: 4, url: '/stale' })
  assert.equal(page.pageId, 4)
  assert.equal(page.url, null)
  const ext = pathwayCardToInput({ ...newPathwayCard(), title: 'E', destinationType: 'external', url: 'https://x.org', openNewTab: true })
  assert.equal(ext.openNewTab, true)
})

test('icon and image are mutually exclusive', () => {
  const withMedia = setPathwayMedia(setPathwayIcon(routeCard('A'), 'users'), { id: 7 })
  assert.equal(withMedia.icon, null)
  assert.equal(withMedia.mediaId, 7)
  const withIcon = setPathwayIcon(withMedia, 'rocket')
  assert.equal(withIcon.mediaId, null)
  assert.equal(withIcon.icon, 'rocket')
})

test('pathway card validation mirrors navigation destination rules', () => {
  assert.equal(validatePathwayCard(routeCard('Ok')), null)
  assert.match(validatePathwayCard(routeCard('Admin', '/admin/users')), /admin or API/)
  assert.match(validatePathwayCard(routeCard('Proto', '//evil.example')), /single "\/"/)
  assert.match(validatePathwayCard({ ...newPathwayCard(), title: 'E', destinationType: 'external', url: 'javascript:x' }), /http/)
  assert.match(validatePathwayCard({ ...newPathwayCard(), title: 'P', destinationType: 'page' }), /Page selected/)
  assert.match(validatePathwayCard({ ...newPathwayCard(), destinationType: 'route', url: '/x' }, 2), /Card 3 needs a title/)
  assert.match(validatePathwayCard({ ...newPathwayCard(), title: 'G', destinationType: 'group' }), /needs a destination/)
})

test('pathways module needs 2–8 cards while enabled', () => {
  const module = (cards, extra = {}) => ({ type: 'career_pathways', enabled: true, config: { cards }, ...extra })
  assert.match(validatePathwaysModule(module([routeCard('A')])), /at least 2/)
  assert.equal(validatePathwaysModule(module([routeCard('A'), routeCard('B')])), null)
  assert.match(validatePathwaysModule(module(Array.from({ length: 9 }, (_, i) => routeCard(`C${i}`)))), /at most 8/)
  assert.equal(validatePathwaysModule(module([], { enabled: false })), null)
  assert.match(validatePathwaysModule(module([routeCard('A'), routeCard('B')], { ctaLabel: 'All' })), /both a label/)
  assert.match(validatePathwaysModule(module([routeCard('A'), routeCard('B')], { ctaLabel: 'All', ctaUrl: '/api/x' })), /admin or API/)
})

test('public pathway link never falls back to "/"', () => {
  assert.equal(pathwayCardLink({ title: 'x' }), null)
  assert.equal(pathwayCardLink({ title: 'x', href: '' }), null)
  assert.deepEqual(pathwayCardLink({ href: '/topics/money', linkType: 'internal' }), { kind: 'internal', to: '/topics/money' })
  assert.deepEqual(pathwayCardLink({ href: 'https://x.org', linkType: 'external', openNewTab: true }), {
    kind: 'external', href: 'https://x.org', newTab: true,
  })
})

test('new collection defaults to automatic articles with real sorts only', () => {
  assert.deepEqual(newCollectionConfig(), { eyebrow: null, entityType: 'articles', layout: 'grid', itemCount: 4, sort: 'latest', filters: {} })
  assert.deepEqual(newCollectionConfig('jobs', 'manual'), { eyebrow: null, entityType: 'jobs', layout: 'grid', slugs: [] })
  const sorts = Object.values(COLLECTION_ENTITIES).flatMap((e) => e.sorts.map((s) => s.value))
  assert.ok(!sorts.includes('most_read'))
  assert.ok(!('products' in COLLECTION_ENTITIES))
})

test('changing entity type clears sort, filters and picked items', () => {
  const module = {
    type: 'content_collection', selectionMode: 'automatic',
    config: { eyebrow: 'Hi', entityType: 'articles', layout: 'compact', itemCount: 6, sort: 'featured', filters: { topic: 'money' } },
  }
  const next = changeCollectionEntity(module, 'resources')
  assert.deepEqual(next.config, { eyebrow: 'Hi', entityType: 'resources', layout: 'compact', itemCount: 4, sort: 'newest', filters: {} })
  const manual = changeCollectionEntity({ ...module, selectionMode: 'manual', config: { entityType: 'articles', slugs: ['a'] } }, 'events')
  assert.deepEqual(manual.config.slugs, [])
})

test('changing selection mode clears the other mode config', () => {
  const auto = { type: 'content_collection', selectionMode: 'automatic', config: newCollectionConfig('learning') }
  auto.config.filters = { programType: 'course' }
  const manual = changeCollectionMode(auto, 'manual')
  assert.equal(manual.selectionMode, 'manual')
  assert.deepEqual(manual.config, { eyebrow: null, entityType: 'learning', layout: 'grid', slugs: [] })
  const back = changeCollectionMode({ ...manual, config: { ...manual.config, slugs: ['x'] } }, 'automatic')
  assert.equal(back.config.slugs, undefined)
  assert.equal(back.config.sort, 'newest')
})

test('collection save payload keeps only keys valid for the entity and mode', () => {
  const config = { entityType: 'events', itemCount: 3, sort: 'latest', filters: { topic: 'x', accessType: 'premium' }, slugs: ['e'] }
  assert.deepEqual(collectionConfigToInput(config, 'automatic'), {
    eyebrow: null, entityType: 'events', layout: 'grid', itemCount: 3, sort: 'upcoming', filters: {},
  })
  assert.deepEqual(collectionConfigToInput({ ...config, entityType: 'resources', filters: { accessType: 'premium', resourceType: '' } }, 'automatic').filters, {
    accessType: 'premium',
  })
  assert.deepEqual(collectionConfigToInput(config, 'manual'), { eyebrow: null, entityType: 'events', layout: 'grid', slugs: ['e'] })
})

test('collection validation', () => {
  const base = { type: 'content_collection', selectionMode: 'automatic', config: newCollectionConfig() }
  assert.equal(validateCollectionModule(base), null)
  assert.match(validateCollectionModule({ ...base, config: { ...base.config, entityType: 'products' } }), /Choose what/)
  assert.match(validateCollectionModule({ ...base, selectionMode: null }), /manual or automatic/)
  assert.match(validateCollectionModule({ ...base, config: { ...base.config, itemCount: 9 } }), /between 1 and 8/)
  assert.match(validateCollectionModule({ ...base, selectionMode: 'manual', config: { entityType: 'jobs', slugs: [] } }), /at least one/)
})

test('builder-level validation and payloads leave existing types untouched', () => {
  const legacy = { type: 'latest_stories', config: { itemCount: 6, anything: true } }
  assert.equal(validateHomepageExtras([legacy]), null)
  assert.deepEqual(moduleConfigToInput(legacy), { itemCount: 6, anything: true })
  assert.match(validateHomepageExtras([legacy, { type: 'career_pathways', enabled: true, config: { cards: [] } }]), /at least 2/)
  const pathways = moduleConfigToInput({ type: 'career_pathways', config: { eyebrow: ' x ', cards: [routeCard('A')] } })
  assert.equal(pathways.eyebrow, 'x')
  assert.equal(pathways.cards[0].url, '/jobs')
})
