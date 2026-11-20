// Run with: node --test src/utils/authorAuthority.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  authorBootstrapState,
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
  assert.deepEqual(m.sections, ['about', 'credentials', 'learning', 'resources', 'articles', 'sources'])
  assert.equal(m.subtitle, 'Career, Leadership & Future of Work')
  // Facts carry only real values; Role appears because the headline took the subtitle.
  assert.deepEqual(m.facts.map((f) => f.label).slice(0, 2), ['Location', 'Role'])
  assert.equal('stats' in m, false)
  assert.deepEqual(m.person, { slug: 'celestine' })
  assert.equal(m.hasPortrait, true)
})

test('case B: articles and resources but no courses', () => {
  const m = authorProfileModel({ ...full, authority: { counts: { articles: 4, resources: 2, courses: 0 }, learningPrograms: [], resources: [{ id: 2 }] } }, { articleCount: 4 })
  assert.deepEqual(m.sections, ['about', 'credentials', 'resources', 'articles', 'sources'])
})

test('case C: bio only renders just About, no sidebar, no empty headings', () => {
  const m = authorProfileModel({ name: 'Amara Diallo', bio: [{ type: 'paragraph', text: 'Bio.' }] }, { articleCount: 0 })
  assert.deepEqual(m.sections, ['about'])
  assert.deepEqual(m.facts, [])
  assert.equal(m.subtitle, '')
  assert.equal(m.headline, '')
  assert.equal(m.roleLine, '')
  assert.deepEqual(m.topics, [])
  assert.deepEqual(m.links, [])
  assert.equal(m.person, null)
})

test('case D/E: linked Person kept; no portrait uses the initials fallback', () => {
  const m = authorProfileModel({ name: 'Wanjiru Kamau', person: { slug: 'wanjiru' } })
  assert.deepEqual(m.person, { slug: 'wanjiru' })
  assert.equal(m.hasPortrait, false)
  assert.equal(m.initials, 'WK')
})

test('nothing at all: no sections; credentials alone get their own section', () => {
  assert.deepEqual(authorProfileModel({ name: 'X' }).sections, [])
  const m = authorProfileModel({ name: 'X', credentials: [{ name: 'MBA' }, { issuer: 'no name' }] })
  assert.deepEqual(m.sections, ['credentials'])
  assert.equal(m.credentials.length, 1)
  assert.deepEqual(m.facts, [{ key: 'education', label: 'Education', values: ['MBA'] }])
  // Later archive pages keep the articles section even if a page is short.
  assert.deepEqual(authorProfileModel({ name: 'X' }, { articleCount: 0, page: 2 }).sections, ['articles'])
})

const mappers = {
  mapAuthor: (a) => ({ id: a.id, slug: a.slug, name: a.name, mapped: true }),
  mapArticle: (a) => ({ id: a.id, slug: a.slug, mapped: true }),
}

test('bootstrap maps to the same state shapes the API path produces', () => {
  const state = authorBootstrapState(
    {
      key: 'celestine',
      data: {
        author: { id: 1, slug: 'celestine', name: 'Celestine' },
        authority: { counts: { articles: 12 } },
        articles: [{ id: 5, slug: 'a5' }],
        meta: { page: 1, per_page: 9, total: 12, total_pages: 2 },
      },
    },
    mappers,
  )
  assert.deepEqual(state.author, { id: 1, slug: 'celestine', name: 'Celestine', mapped: true, authority: { counts: { articles: 12 } } })
  assert.deepEqual(state.articles, [{ id: 5, slug: 'a5', mapped: true }])
  assert.deepEqual(state.pagination, { page: 1, pageSize: 9, totalItems: 12, totalPages: 2 })
})

test('missing or malformed bootstrap means fetch normally', () => {
  assert.equal(authorBootstrapState(null, mappers), null)
  assert.equal(authorBootstrapState({ key: 'x' }, mappers), null)
  assert.equal(authorBootstrapState({ key: 'x', data: { author: null } }, mappers), null)
  const noArticles = authorBootstrapState({ key: 'x', data: { author: { id: 1, slug: 'x' } } }, mappers)
  assert.deepEqual(noArticles.articles, [])
  assert.equal(noArticles.pagination, null)
  assert.equal(noArticles.author.authority, null)
})

import { readFileSync } from 'node:fs'
import { authorEducation } from './authorAuthority.js'

test('education is derived from degree-type credentials (shared fixture with the prerender)', () => {
  const { cases } = JSON.parse(readFileSync(new URL('../../../backend/tests/fixtures/author_education_cases.json', import.meta.url), 'utf8'))
  for (const c of cases) assert.deepEqual(authorEducation(c.credentials), c.expected)
})

test('role without a headline becomes the subtitle and is not repeated as a fact', () => {
  const m = authorProfileModel({ name: 'A B', role: 'Editor', location: 'Accra' })
  assert.equal(m.subtitle, 'Editor')
  assert.deepEqual(m.facts.map((f) => f.key), ['location'])
})
