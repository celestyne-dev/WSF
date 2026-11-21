import test from 'node:test'
import assert from 'node:assert/strict'
import { closingLabel, longDate, opensLabel, postedLabel, shortDate } from './listingDates.js'

test('date-only values never shift with the viewer timezone', () => {
  assert.equal(longDate('2026-11-30'), '30 November 2026')
  assert.equal(longDate('2027-01-01'), '1 January 2027')
  assert.equal(shortDate('2026-11-18', 2026), '18 Nov')
  assert.equal(shortDate('2027-01-31', 2026), '31 Jan 2027')
  assert.equal(longDate(null), '')
})

test('closing wording', () => {
  assert.equal(closingLabel({ closesOn: '2026-11-21', daysLeft: 0, closingSoon: true }, 2026), 'Closes today')
  assert.equal(closingLabel({ closesOn: '2026-11-22', daysLeft: 1, closingSoon: true }, 2026), 'Closes tomorrow')
  assert.equal(closingLabel({ closesOn: '2026-11-30', daysLeft: 9, closingSoon: false }, 2026), 'Closes 30 Nov · 9 days left')
  assert.equal(closingLabel(null), '')
})

test('posted and opens labels', () => {
  assert.equal(postedLabel('2026-11-18', 2026), 'Posted 18 Nov')
  assert.equal(opensLabel('2026-12-01'), 'Opens 1 December 2026')
  assert.equal(postedLabel(null), '')
})
