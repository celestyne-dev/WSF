import test from 'node:test'
import assert from 'node:assert/strict'
import { premiumCourseState, programAccessLabel, programCardAccessLabel } from './learningAccess.js'

const product = { accessType: 'product', product: { slug: 'p', price: 4500, currency: 'KES' }, lifetimeIncluded: true }

test('a premium course never shows its linked Product price', () => {
  assert.equal(programAccessLabel(product), 'Premium course')
  assert.equal(programCardAccessLabel(product), 'Premium')
  assert.doesNotMatch(programAccessLabel(product) + programCardAccessLabel(product), /KES|4,?500/)
})

test('free, Circle and external labels are unchanged', () => {
  assert.equal(programAccessLabel({ accessType: 'free' }), 'Free')
  assert.equal(programAccessLabel({ accessType: 'circle_only' }), 'Included with WSF Circle')
  assert.equal(programAccessLabel({ accessType: 'external' }), 'External enrollment')
  assert.equal(programCardAccessLabel({ accessType: 'circle_only' }), 'WSF Circle')
  assert.equal(programCardAccessLabel({ accessType: 'external' }), 'External')
  assert.equal(programCardAccessLabel({ accessType: 'free' }), 'Free')
})

test('premium course state: Lifetime offer, information only, or unavailable', () => {
  assert.equal(premiumCourseState(product, { lifetimeOnSale: true }), 'lifetime')
  assert.equal(premiumCourseState(product, { lifetimeOnSale: false }), 'info')
  assert.equal(premiumCourseState({ ...product, lifetimeIncluded: false }, { lifetimeOnSale: true }), 'unavailable')
  // A Lifetime member with access goes through the normal Start/Continue flow.
  assert.equal(premiumCourseState({ ...product, viewerCanAccess: true }, { lifetimeOnSale: true }), null)
  assert.equal(premiumCourseState({ accessType: 'free' }), null)
})
