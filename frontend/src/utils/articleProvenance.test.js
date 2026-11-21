// Run with: node --test src/utils/articleProvenance.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { expertRowsFromArticle, expertRowsToPayload } from './articleProvenance.js'

test('provenance rows round-trip between Studio and the API', () => {
  const refs = [{ role: 'reviewed_by', authorSlug: 'jane' }, { role: 'fact_checked_by', personSlug: 'amara' }]
  const rows = expertRowsFromArticle(refs)
  assert.deepEqual(rows, [{ role: 'reviewed_by', profile: 'author:jane' }, { role: 'fact_checked_by', profile: 'person:amara' }])
  assert.deepEqual(expertRowsToPayload(rows), refs)
})

test('incomplete rows are never sent (no profile = no claim)', () => {
  assert.deepEqual(expertRowsToPayload([{ role: 'reviewed_by', profile: '' }]), [])
})
