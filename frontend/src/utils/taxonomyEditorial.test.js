// Plain-Node round-trip tests for the Topic/Series editorial form helpers.
// Run with: node --test src/utils/taxonomyEditorial.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { blankEditorialForm, editorialToForm, editorialToPayload } from './taxonomyEditorial.js'

test('a new Topic/Series sends empty editorial fields', () => {
  assert.deepEqual(editorialToPayload(blankEditorialForm()), { content: [], sources: [], featuredArticleId: null })
})

test('stored editorial depth round-trips through an unrelated edit', () => {
  const entity = {
    content: [{ type: 'paragraph', text: 'Why leadership matters.' }],
    sources: [{ title: 'Report', url: 'https://example.org/report', publisher: 'ILO' }],
    featuredArticleId: 12,
    featuredArticleSelection: { id: 12, slug: 'start', title: 'Start', status: 'published' },
  }
  const form = { ...editorialToForm(entity), seoTitle: 'Changed' }
  assert.deepEqual(editorialToPayload(form), {
    content: [{ type: 'paragraph', text: 'Why leadership matters.' }],
    sources: [{ title: 'Report', url: 'https://example.org/report', publisher: 'ILO' }],
    featuredArticleId: 12,
  })
})

test('clearing the featured article sends null', () => {
  const form = { ...editorialToForm({ featuredArticleId: 3 }), featuredArticleId: null }
  assert.equal(editorialToPayload(form).featuredArticleId, null)
})
