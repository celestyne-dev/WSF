// Plain-Node round-trip test: an Author's legacy freeform expertise
// survives API -> editor form -> save payload, including after an
// unrelated source edit (GEO Phase 4A pre-deploy correction).
// Run with: node --test src/utils/authorForm.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { authorFormToPayload, authorToForm, blankAuthorForm } from './authorForm.js'

test('legacy expertise survives an unrelated source edit', () => {
  const apiAuthor = { name: 'Writer', slug: 'writer', expertise: ['Leadership'], sources: [], social: {}, topicSlugs: ['finance'] }
  const form = authorToForm(apiAuthor)
  const edited = { ...form, sources: [{ title: 'Profile', url: 'https://news.example.org/writer' }] }
  const payload = authorFormToPayload(edited, 'active')
  assert.deepEqual(payload.expertise, ['Leadership'])
  assert.deepEqual(payload.topicSlugs, ['finance'])
  assert.deepEqual(payload.sources, [{ title: 'Profile', url: 'https://news.example.org/writer' }])
})

test('a new Author sends an empty expertise list', () => {
  assert.deepEqual(authorFormToPayload(blankAuthorForm(), 'draft').expertise, [])
  assert.deepEqual(authorToForm({ name: 'No expertise' }).expertise, [])
})

test('credential edits round-trip without touching expertise, topics or sources', () => {
  const apiAuthor = {
    name: 'Writer', slug: 'writer', expertise: ['Leadership'], topicSlugs: ['finance'], personId: 7,
    sources: [{ title: 'Profile', url: 'https://news.example.org/writer' }], social: {},
    credentials: [{ name: 'MBA', issuer: 'Example University' }],
  }
  const form = authorToForm(apiAuthor)
  const edited = { ...form, credentials: [...form.credentials, { name: ' CPA ', category: '', issuer: 'Board', url: '', note: '' }] }
  const payload = authorFormToPayload(edited, 'active')
  assert.deepEqual(payload.credentials, [{ name: 'MBA', issuer: 'Example University' }, { name: 'CPA', issuer: 'Board' }])
  assert.deepEqual(payload.expertise, ['Leadership'])
  assert.deepEqual(payload.topicSlugs, ['finance'])
  assert.equal(payload.personId, 7)
  assert.deepEqual(payload.sources, [{ title: 'Profile', url: 'https://news.example.org/writer' }])
})
