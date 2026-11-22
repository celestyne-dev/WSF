// Run with: node --test src/utils/articleProvenance.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { expertRowsFromArticle, expertRowsToPayload, isDisplayableUpdate, todayInputValue, editorialUpdatedAtToPayload } from './articleProvenance.js'

test('provenance rows round-trip between Studio and the API', () => {
  const refs = [{ role: 'reviewed_by', authorSlug: 'jane' }, { role: 'fact_checked_by', personSlug: 'amara' }]
  const rows = expertRowsFromArticle(refs)
  assert.deepEqual(rows, [{ role: 'reviewed_by', profile: 'author:jane' }, { role: 'fact_checked_by', profile: 'person:amara' }])
  assert.deepEqual(expertRowsToPayload(rows), refs)
})

test('incomplete rows are never sent (no profile = no claim)', () => {
  assert.deepEqual(expertRowsToPayload([{ role: 'reviewed_by', profile: '' }]), [])
})

test('Updated is shown only for a past update after publication', () => {
  const now = new Date('2026-11-22T12:00:00Z')
  assert.equal(isDisplayableUpdate('2026-11-20T10:00:00Z', '2026-11-01T10:00:00Z', now), true)
  assert.equal(isDisplayableUpdate('2026-12-01T10:00:00Z', '2026-11-01T10:00:00Z', now), false) // future
  assert.equal(isDisplayableUpdate('2026-10-01T10:00:00Z', '2026-11-01T10:00:00Z', now), false) // before publication
  assert.equal(isDisplayableUpdate(null, '2026-11-01T10:00:00Z', now), false)
  assert.equal(isDisplayableUpdate('not a date', null, now), false)
})

test('the Studio date input max is today', () => {
  assert.equal(todayInputValue(new Date(2026, 10, 22, 9)), '2026-11-22')
})

test('choosing today never sends a future timestamp', () => {
  const now = new Date(2026, 10, 22, 1, 30)
  assert.equal(editorialUpdatedAtToPayload('2026-11-22', now), now.toISOString())
  assert.equal(editorialUpdatedAtToPayload('', now), null)
  assert.ok(new Date(editorialUpdatedAtToPayload('2026-11-20', now)) < now)
})
