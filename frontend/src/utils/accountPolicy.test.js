import { test } from 'node:test'
import assert from 'node:assert/strict'
import { DEFAULT_MINIMUM_AGE, ageConfirmationLabel, minimumAgeOf, registerAgePayload } from './accountPolicy.js'

test('minimum age defaults to 16 and only accepts the 16-21 range', () => {
  assert.equal(DEFAULT_MINIMUM_AGE, 16)
  assert.equal(minimumAgeOf(null), 16)
  assert.equal(minimumAgeOf({}), 16)
  assert.equal(minimumAgeOf({ accountPolicy: { minimumAge: 18 } }), 18)
  for (const bad of [15, 22, '18', 17.5, null, true]) {
    assert.equal(minimumAgeOf({ accountPolicy: { minimumAge: bad } }), 16)
  }
})

test('checkbox wording matches the approved text', () => {
  assert.equal(ageConfirmationLabel(16), 'I confirm that I am at least 16 years old.')
})

test('only an explicit tick is sent as true', () => {
  assert.deepEqual(registerAgePayload(true), { age_confirmed: true })
  assert.deepEqual(registerAgePayload(false), { age_confirmed: false })
  assert.deepEqual(registerAgePayload('true'), { age_confirmed: false })
  assert.deepEqual(registerAgePayload(undefined), { age_confirmed: false })
})
