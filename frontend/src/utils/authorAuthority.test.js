// Run with: node --test src/utils/authorAuthority.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  authorExternalLinks,
  authorFirstName,
  authorInitials,
  authorPlace,
  authorProfileModel,
  authorRoleLine,
  authorStatItems,
  hasItems,
} from './authorAuthority.js'

test('stats show only real, non-zero derived counts with correct plurals', () => {
  assert.deepEqual(authorStatItems({ articles: 24, resources: 6, courses: 3 }), [
    { value: 24, label: 'Articles' },
    { value: 6, label: 'Career Tools' },
    { value: 3, label: 'Courses' },
  ])
  assert.deepEqual(authorStatItems({ articles: 1, resources: 0, courses: 1 }), [
    { value: 1, label: 'Article' },
    { value: 1, label: 'Course' },
  ])
  assert.deepEqual(authorStatItems({ articles: 16, resources: 6, courses: 0 }).map((s) => s.label), ['Articles', 'Career Tools'])
  assert.deepEqual(authorStatItems(null), [])
})

test('first name and empty-section guards', () => {
  assert.equal(authorFirstName('Celestine Nyamoita'), 'Celestine')
  assert.equal(authorFirstName('  '), '')
  assert.equal(hasItems([]), false)
  assert.equal(hasItems([{}]), true)
  assert.equal(hasItems(undefined), false)
})

test('role and place use real fields without duplicating the country', () => {
  assert.equal(authorPlace({ location: 'Nairobi', country: { name: 'Kenya' } }), 'Nairobi, Kenya')
  assert.equal(authorPlace({ location: 'Nairobi, Kenya', country: { name: 'Kenya' } }), 'Nairobi, Kenya')
  assert.equal(authorPlace({ country: { name: 'Kenya' } }), 'Kenya')
  assert.equal(authorPlace({}), '')
  assert.equal(authorRoleLine({ role: 'Founder & Editor', location: 'Nairobi', country: { name: 'Kenya' } }), 'Founder & Editor · Nairobi, Kenya')
  assert.equal(authorRoleLine({ role: 'Contributor' }), 'Contributor')
  assert.equal(authorRoleLine({}), '')
})

test('external links have visible labels and only safe destinations', () => {
  const links = authorExternalLinks({
    website: 'https://example.org',
    social: { linkedin: 'celestine', twitter: '@wsf', instagram: 'https://www.instagram.com/wsf' },
  })
  assert.deepEqual(links.map((l) => [l.label, l.href]), [
    ['Website', 'https://example.org'],
    ['LinkedIn', 'https://www.linkedin.com/in/celestine'],
    ['X (Twitter)', 'https://x.com/wsf'],
    ['Instagram', 'https://www.instagram.com/wsf'],
  ])
  assert.deepEqual(authorExternalLinks({ website: 'javascript:alert(1)', social: { linkedin: 'bad handle!' } }), [])
  assert.deepEqual(authorExternalLinks({}), [])
})

test('portrait fallback initials', () => {
  assert.equal(authorInitials('Celestine Nyamoita'), 'CN')
  assert.equal(authorInitials('Amara'), 'A')
  assert.equal(authorInitials('Mary Ann de Souza'), 'MS')
  assert.equal(authorInitials(''), '')
})

const full = {
  name: 'Celestine Nyamoita',
  headline: 'Career, Leadership & Future of Work',
  role: 'Founder & Editor',
  location: 'Nairobi',
  country: { name: 'Kenya' },
  topics: [{ slug: 'leadership', name: 'Leadership' }],
  bio: [{ type: 'paragraph', text: 'Bio.' }],
  credentials: [{ name: 'BCom, Marketing' }],
  sources: [{ title: 'Interview', url: 'https://example.org' }],
  website: 'https://example.org',
  social: { linkedin: 'celestine' },
  person: { slug: 'celestine' },
  photoMedia: { id: 1 },
  authority: {
    counts: { articles: 16, resources: 6, courses: 3 },
    learningPrograms: [{ id: 1 }],
    resources: [{ id: 2 }],
  },
}

test('case A: full authority profile renders every section in order', () => {
  const m = authorProfileModel(full, { articleCount: 9 })
  assert.equal(m.headline, 'Career, Leadership & Future of Work')
  assert.equal(m.roleLine, 'Founder & Editor · Nairobi, Kenya')
  assert.deepEqual(m.sections, ['profile', 'learning', 'resources', 'articles', 'sources'])
  assert.equal(m.sidebar, true)
  assert.equal(m.stats.length, 3)
  assert.deepEqual(m.person, { slug: 'celestine' })
  assert.equal(m.hasPortrait, true)
})

test('case B: articles and resources but no courses', () => {
  const m = authorProfileModel({ ...full, authority: { counts: { articles: 4, resources: 2, courses: 0 }, learningPrograms: [], resources: [{ id: 2 }] } }, { articleCount: 4 })
  assert.deepEqual(m.sections, ['profile', 'resources', 'articles', 'sources'])
  assert.deepEqual(m.stats.map((s) => s.label), ['Articles', 'Career Tools'])
})

test('case C: bio only renders just About, no sidebar, no empty headings', () => {
  const m = authorProfileModel({ name: 'Amara Diallo', bio: [{ type: 'paragraph', text: 'Bio.' }] }, { articleCount: 0 })
  assert.deepEqual(m.sections, ['profile'])
  assert.equal(m.sidebar, false)
  assert.equal(m.headline, '')
  assert.equal(m.roleLine, '')
  assert.deepEqual(m.topics, [])
  assert.deepEqual(m.stats, [])
  assert.deepEqual(m.links, [])
  assert.equal(m.person, null)
})

test('case D/E: linked Person kept; no portrait uses the initials fallback', () => {
  const m = authorProfileModel({ name: 'Wanjiru Kamau', person: { slug: 'wanjiru' } })
  assert.deepEqual(m.person, { slug: 'wanjiru' })
  assert.equal(m.hasPortrait, false)
  assert.equal(m.initials, 'WK')
})

test('nothing at all: no sections; credentials without a bio take the main column', () => {
  assert.deepEqual(authorProfileModel({ name: 'X' }).sections, [])
  const m = authorProfileModel({ name: 'X', credentials: [{ name: 'MBA' }, { issuer: 'no name' }] })
  assert.deepEqual(m.sections, ['profile'])
  assert.equal(m.sidebar, false)
  assert.equal(m.credentials.length, 1)
  // Later archive pages keep the articles section even if a page is short.
  assert.deepEqual(authorProfileModel({ name: 'X' }, { articleCount: 0, page: 2 }).sections, ['articles'])
})
