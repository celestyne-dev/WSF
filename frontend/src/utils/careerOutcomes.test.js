import { test } from 'node:test'
import assert from 'node:assert/strict'
import { outcomePublicCredit } from './careerOutcomes.js'

test('public credit never exposes more than first name and initial', () => {
  assert.equal(outcomePublicCredit('first_name', 'Amara', 'Diallo'), 'Amara D.')
  assert.equal(outcomePublicCredit('first_name', ' Amara ', ''), 'Amara')
  assert.equal(outcomePublicCredit('first_name', '', 'Diallo'), 'A WSF community member')
  assert.equal(outcomePublicCredit('anonymous', 'Amara', 'Diallo'), 'A WSF community member')
})
