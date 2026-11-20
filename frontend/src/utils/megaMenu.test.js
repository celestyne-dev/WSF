// Run with: node --test src/utils/megaMenu.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { buildHeaderNavigation, isEntryActive, navPath } from './megaMenu.js'

const r = (id, label, url, children = [], extra = {}) => ({ id, label, url, itemType: 'route', linkType: 'internal', openNewTab: false, style: 'standard', children, ...extra })

// The shape backend seed_default_navigation() produces (production default).
const seeded = {
  primary: [
    r(1, 'Stories', '/topics', [r(11, 'Topics', '/topics'), r(12, 'Series', '/series')]),
    r(2, 'People', '/people', [r(21, 'People Directory', '/people'), r(22, 'Authors', '/authors')]),
    r(3, 'Opportunities', '/opportunities', [r(31, 'Opportunities', '/opportunities'), r(32, 'Jobs', '/jobs')]),
    r(4, 'Resources', '/resources'),
    r(5, 'Events', '/events'),
    r(6, 'WSF Circle', '/circle'),
    r(7, 'Community', '/community'),
    r(8, 'Shop', '/shop'),
  ],
  secondary: [r(91, 'WSF Weekly Newsletter', '/newsletter'), r(92, 'Partner With Us', '/partnerships'), r(93, 'About', '/about')],
}

const labels = (nav) => nav.map((e) => e.label)
const groupOf = (entry, key) => entry.menu.groups.find((g) => g.key === key)
const linkLabels = (group) => group.links.map((l) => l.label)

test('seeded navigation becomes 6 top-level items with folded Events and Shop', () => {
  const nav = buildHeaderNavigation(seeded)
  assert.deepEqual(labels(nav), ['Stories', 'People', 'Opportunities', 'Resources', 'WSF Circle', 'Community'])
  const opp = nav.find((e) => e.label === 'Opportunities')
  assert.deepEqual(linkLabels(groupOf(opp, 'work')), ['Opportunities', 'Jobs'])
  assert.deepEqual(linkLabels(groupOf(opp, 'connect')), ['Events'])
  assert.equal(opp.menu.cta.label, 'View all opportunities')
  assert.equal(opp.menu.cta.link.to, '/opportunities')
  const res = nav.find((e) => e.label === 'Resources')
  assert.deepEqual(linkLabels(groupOf(res, 'tools')), ['Shop']) // the parent itself is the intro CTA
  assert.equal(res.menu.cta.link.to, '/resources')
})

test('secondary utility items move into menus instead of disappearing', () => {
  const nav = buildHeaderNavigation(seeded)
  const stories = nav.find((e) => e.label === 'Stories')
  assert.deepEqual(linkLabels(groupOf(stories, 'stay-informed')), ['WSF Weekly Newsletter'])
  const community = nav.find((e) => e.label === 'Community')
  assert.deepEqual(linkLabels(groupOf(community, 'about')), ['Partner With Us', 'About'])
  // Every CMS destination is still reachable from the header model.
  const all = new Set()
  for (const e of nav) {
    if (e.link.to) all.add(e.link.to)
    for (const g of e.menu?.groups || []) for (const l of g.links) all.add(l.link.to)
  }
  for (const url of ['/topics', '/series', '/people', '/authors', '/opportunities', '/jobs', '/resources', '/events', '/circle', '/community', '/shop', '/newsletter', '/partnerships', '/about']) {
    assert.ok(all.has(url), url)
  }
})

test('links carry descriptions and selective icons; plain links have no menu', () => {
  const nav = buildHeaderNavigation(seeded)
  const jobs = groupOf(nav.find((e) => e.label === 'Opportunities'), 'work').links.find((l) => l.label === 'Jobs')
  assert.equal(jobs.description, 'Roles at organizations hiring now.')
  assert.equal(jobs.icon, 'BriefcaseBusiness')
  const series = groupOf(nav.find((e) => e.label === 'Stories'), 'read').links.find((l) => l.label === 'Series')
  assert.equal(series.icon, null)
  assert.equal(nav.find((e) => e.label === 'WSF Circle').menu, null)
})

test('unknown destinations still render (under More) and externals keep newTab', () => {
  const nav = buildHeaderNavigation({
    primary: [
      r(1, 'Resources', '/resources', [
        r(2, 'Salary guide', '/topics/pay'),
        { id: 3, label: 'Partner site', url: 'https://example.org', itemType: 'external', linkType: 'external', openNewTab: true, children: [] },
      ]),
    ],
    secondary: [],
  })
  const more = groupOf(nav[0], 'more')
  assert.deepEqual(linkLabels(more), ['Salary guide', 'Partner site'])
  assert.deepEqual(more.links[1].link, { kind: 'external', href: 'https://example.org', newTab: true })
})

test('a CMS group item (no destination) gets a menu without a CTA; unknown top-level menus are generic', () => {
  const nav = buildHeaderNavigation({
    primary: [{ id: 1, label: 'Explore', url: null, itemType: 'group', linkType: 'group', children: [r(2, 'Events', '/events'), r(3, 'Odd page', '/odd')] }],
  })
  assert.equal(nav[0].link.kind, 'group')
  assert.equal(nav[0].menu.cta, null)
  assert.equal(nav[0].menu.description, null)
  assert.deepEqual(nav[0].menu.groups.map((g) => g.label), [null])
})

test('folding never drops the bar below 5 items and never folds CTA items', () => {
  const nav = buildHeaderNavigation({
    primary: [r(1, 'Opportunities', '/opportunities'), r(2, 'Events', '/events'), r(3, 'Resources', '/resources'), r(4, 'Shop', '/shop', [], { style: 'cta' })],
  })
  assert.deepEqual(labels(nav), ['Opportunities', 'Events', 'Resources', 'Shop'])
})

test('duplicates inside one menu are shown once; empty/missing navigation is safe', () => {
  const nav = buildHeaderNavigation({ primary: [r(1, 'Stories', '/topics', [r(2, 'Topics', '/topics'), r(3, 'Topics again', '/topics/')])], secondary: [r(4, 'News', '/newsletter'), r(5, 'News 2', '/newsletter')] })
  assert.deepEqual(linkLabels(groupOf(nav[0], 'read')), ['Topics'])
  assert.deepEqual(linkLabels(groupOf(nav[0], 'stay-informed')), ['News'])
  assert.deepEqual(buildHeaderNavigation(null), [])
  assert.deepEqual(buildHeaderNavigation({ primary: [{ id: 1, label: 'Broken', url: null, children: [] }] }), [])
})

test('active state follows the current path, including folded links', () => {
  const nav = buildHeaderNavigation(seeded)
  const opp = nav.find((e) => e.label === 'Opportunities')
  assert.equal(isEntryActive(opp, '/events/summit'), true)
  assert.equal(isEntryActive(opp, '/jobs'), true)
  assert.equal(isEntryActive(opp, '/topics'), false)
  assert.equal(isEntryActive(nav.find((e) => e.label === 'WSF Circle'), '/circle/checkout/callback'), true)
  assert.equal(navPath({ kind: 'internal', to: '/jobs/?a=1#x' }), '/jobs')
  assert.equal(navPath({ kind: 'external', href: 'https://x.org' }), null)
})
