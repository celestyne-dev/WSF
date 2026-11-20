import { test } from 'node:test'
import assert from 'node:assert/strict'
import { awardLine, isPublicHttpUrl, normalizeAchievements, normalizeAwards, normalizeTimeline } from './personEvidence.js'

test('legacy strings and new evidence objects normalize to one shape', () => {
  assert.deepEqual(normalizeAchievements(['Appointed CEO in 2025', { text: 'First woman chair', sourceUrl: 'https://x.org/a', sourceLabel: 'Board release' }, null]), [
    { text: 'Appointed CEO in 2025', date: '', sourceLabel: '', sourceUrl: '' },
    { text: 'First woman chair', date: '', sourceLabel: 'Board release', sourceUrl: 'https://x.org/a' },
  ])
  assert.deepEqual(normalizeAwards(['Africa 40 Under 40 (2023)'])[0], { name: 'Africa 40 Under 40 (2023)', issuer: '', date: '', sourceLabel: '', sourceUrl: '' })
  assert.deepEqual(normalizeTimeline([{ year: 2020, title: 'CEO' }])[0], { year: '2020', title: 'CEO', organization: '', sourceLabel: '', sourceUrl: '' })
  assert.deepEqual(normalizeAchievements(undefined), [])
})

test('award line and URL check', () => {
  assert.equal(awardLine({ name: 'Award', issuer: 'Forbes', date: '2024' }), 'Award — Forbes, 2024')
  assert.equal(awardLine({ name: 'Award', issuer: '', date: '' }), 'Award')
  assert.equal(isPublicHttpUrl('https://example.org/a'), true)
  assert.equal(isPublicHttpUrl('javascript:alert(1)'), false)
  assert.equal(isPublicHttpUrl('/people/x'), false)
})
