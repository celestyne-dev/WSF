// Plain-Node tests for the shared navigation destination rules (editor
// fields, type switching, save payloads, validation and the public link
// decision used by both Header and MobileNav).
// Run with: node --test src/utils/navigation.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  NAV_ITEM_TYPES,
  changeNavItemType,
  navEditorFields,
  navItemPreview,
  navItemToInput,
  publicNavLink,
  validateNavItem,
  validateNavItems,
} from './navigation.js'

const base = { id: 1, label: 'Item', visible: true, style: 'standard', children: [], url: null, pageId: null, topicId: null, seriesId: null, openNewTab: false }

test('every destination type renders its own editor fields', () => {
  assert.deepEqual(NAV_ITEM_TYPES, ['route', 'page', 'topic', 'series', 'external', 'group'])
  assert.deepEqual(navEditorFields('route'), ['url'])
  assert.deepEqual(navEditorFields('page'), ['pageId'])
  assert.deepEqual(navEditorFields('topic'), ['topicId'])
  assert.deepEqual(navEditorFields('series'), ['seriesId'])
  assert.deepEqual(navEditorFields('external'), ['url', 'openNewTab'])
  assert.deepEqual(navEditorFields('group'), [])
})

test('switching type never leaks a stale destination and never invents "/"', () => {
  const community = { ...base, label: 'Community', itemType: 'route', url: '/community', effectiveUrl: '/community' }
  const group = changeNavItemType(community, 'group')
  assert.equal(group.url, null)
  assert.equal(group.effectiveUrl, null)
  assert.equal(navItemToInput(group).url, null)
  const backToRoute = changeNavItemType(group, 'route')
  assert.equal(backToRoute.url, null) // must be chosen again — not "/"
  assert.match(validateNavItem(backToRoute), /needs an internal path/)
  const page = changeNavItemType({ ...base, itemType: 'topic', topicId: 7, linkedLabel: 'Leadership' }, 'page')
  assert.equal(page.topicId, null)
  assert.equal(page.linkedLabel, null)
  const external = changeNavItemType({ ...base, itemType: 'external', url: 'https://x.org', openNewTab: true }, 'route')
  assert.equal(external.openNewTab, false)
  assert.equal(external.url, null)
})

test('save payload for each destination type carries only its own field', () => {
  const route = navItemToInput({ ...base, itemType: 'route', url: ' /community ', pageId: 3 })
  assert.deepEqual([route.itemType, route.url, route.pageId, route.topicId, route.seriesId], ['route', '/community', null, null, null])
  const page = navItemToInput({ ...base, itemType: 'page', pageId: 4, url: '/stale' })
  assert.deepEqual([page.itemType, page.pageId, page.url], ['page', 4, null])
  const topic = navItemToInput({ ...base, itemType: 'topic', topicId: 5, seriesId: 9 })
  assert.deepEqual([topic.itemType, topic.topicId, topic.seriesId], ['topic', 5, null])
  const series = navItemToInput({ ...base, itemType: 'series', seriesId: 6, topicId: 1 })
  assert.deepEqual([series.itemType, series.seriesId, series.topicId], ['series', 6, null])
  const external = navItemToInput({ ...base, itemType: 'external', url: 'https://example.org', openNewTab: true })
  assert.deepEqual([external.url, external.openNewTab], ['https://example.org', true])
  const group = navItemToInput({ ...base, itemType: 'group', url: '/community', openNewTab: true, children: [{ ...base, label: 'Shop', itemType: 'route', url: '/shop' }] })
  assert.deepEqual([group.url, group.openNewTab, group.children[0].url], [null, false, '/shop'])
})

test('validation requires a real destination for navigable types', () => {
  assert.equal(validateNavItem({ ...base, itemType: 'route', url: '/community' }), null)
  assert.match(validateNavItem({ ...base, itemType: 'route', url: '' }), /internal path/)
  assert.match(validateNavItem({ ...base, itemType: 'route', url: 'community' }), /single "\/"/)
  assert.match(validateNavItem({ ...base, itemType: 'route', url: '/admin/x' }), /admin or API/)
  assert.match(validateNavItem({ ...base, itemType: 'external', url: 'javascript:alert(1)' }), /http/)
  assert.match(validateNavItem({ ...base, itemType: 'page' }), /Page selected/)
  assert.match(validateNavItem({ ...base, itemType: 'topic' }), /Topic selected/)
  assert.match(validateNavItem({ ...base, itemType: 'series' }), /Series selected/)
  assert.equal(validateNavItem({ ...base, itemType: 'group' }), null)
  assert.match(validateNavItems([{ ...base, itemType: 'group', children: [{ ...base, label: 'Kid', itemType: 'route' }] }]), /"Kid" needs an internal path/)
})

test('admin row preview reflects current form state, never a stale preview', () => {
  assert.equal(navItemPreview({ ...base, itemType: 'route', url: '/community' }), '/community')
  assert.equal(navItemPreview({ ...base, itemType: 'route', url: null }), 'No destination set')
  assert.equal(navItemPreview({ ...base, itemType: 'group' }), null)
  assert.equal(navItemPreview({ ...base, itemType: 'page', pageId: 2, effectiveUrl: '/about' }), '/about')
  assert.equal(navItemPreview({ ...base, itemType: 'topic', topicId: null }), 'Nothing selected')
})

test('public links: internal router links, external anchors, groups never link to "/"', () => {
  assert.deepEqual(publicNavLink({ url: '/community', linkType: 'internal' }), { kind: 'internal', to: '/community' })
  assert.deepEqual(publicNavLink({ url: '/shop', linkType: 'internal' }), { kind: 'internal', to: '/shop' })
  assert.deepEqual(publicNavLink({ url: 'https://ex.org', linkType: 'external', openNewTab: true }), { kind: 'external', href: 'https://ex.org', newTab: true })
  assert.deepEqual(publicNavLink({ url: null, linkType: 'group', children: [{ url: '/x' }] }), { kind: 'group' })
  assert.equal(publicNavLink({ url: null, linkType: 'group', children: [] }), null)
  // Older/mock payloads without linkType are inferred the same way.
  assert.deepEqual(publicNavLink({ url: '/topics/leadership' }), { kind: 'internal', to: '/topics/leadership' })
  assert.deepEqual(publicNavLink({ url: 'https://ex.org' }), { kind: 'external', href: 'https://ex.org', newTab: false })
  assert.deepEqual(publicNavLink({ itemType: 'group', url: null, children: [{}] }), { kind: 'group' })
  assert.equal(publicNavLink({ url: null }), null) // never a "/" fallback
})
