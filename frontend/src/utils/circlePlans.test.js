// Plain-Node tests for WSF Circle plan/membership display (Monthly, Yearly,
// Lifetime) and the lifetime checkout eligibility mirror.
// Run with: node --test src/utils/circlePlans.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  LIFETIME_SCOPE_NOTE,
  adminPeriodText,
  intervalLabel,
  membershipTermLines,
  planExtrasHeading,
  planGuidance,
  planPriceSuffix,
  planTagline,
} from './circlePlans.js'
import { getCheckoutErrorPresentation, getMembershipAction } from './circlePayment.js'

const monthly = { slug: 'm', billingInterval: 'monthly', isLifetime: false }
const yearly = { slug: 'y', billingInterval: 'yearly', isLifetime: false }
const lifetime = { slug: 'l', billingInterval: 'lifetime', isLifetime: true }

test('plan labels and suffixes for all three intervals', () => {
  assert.deepEqual([monthly, yearly, lifetime].map(planPriceSuffix), ['/ month', '/ year', 'one-time'])
  assert.deepEqual([monthly, yearly, lifetime].map(planTagline), ['Flexible access', 'Best annual value', 'One payment · no renewal'])
  assert.deepEqual(['monthly', 'yearly', 'lifetime', undefined].map(intervalLabel), ['Monthly', 'Yearly', 'Lifetime', 'Monthly'])
  assert.equal(planExtrasHeading(monthly), null)
  assert.equal(planExtrasHeading(lifetime), 'Lifetime member benefits')
})

test('guidance only mentions configured plan types', () => {
  assert.equal(planGuidance([monthly]), 'Choose Monthly for flexibility.')
  assert.match(planGuidance([monthly, yearly, lifetime]), /Monthly.*Yearly.*Lifetime/)
  assert.doesNotMatch(planGuidance([monthly, yearly]), /Lifetime/)
  assert.equal(planGuidance([]), '')
})

test('lifetime scope never promises everything WSF offers', () => {
  assert.match(LIFETIME_SCOPE_NOTE, /WSF Circle membership benefits/)
  assert.doesNotMatch(LIFETIME_SCOPE_NOTE, /everything/i)
})

test('lifetime membership shows no renewal or expiry date', () => {
  const sub = { status: 'active', isLifetime: true, currentPeriodEnd: null, plan: lifetime }
  const lines = membershipTermLines(sub)
  assert.deepEqual(lines, ['Lifetime access', 'No renewal required'])
  assert.ok(!lines.some((l) => /renews on|expires/i.test(l)))
  assert.deepEqual(membershipTermLines({ ...sub, status: 'revoked', endedAt: '2026-11-01' }), ['Ended 2026-11-01'])
  assert.equal(adminPeriodText(sub), 'Lifetime · No expiry')
})

test('recurring memberships keep their period end', () => {
  const sub = { status: 'active', plan: monthly, currentPeriodEnd: '2026-12-01', cancelAtPeriodEnd: false }
  assert.deepEqual(membershipTermLines(sub), ['Renews or ends 2026-12-01'])
  assert.deepEqual(membershipTermLines({ ...sub, cancelAtPeriodEnd: true }), ['Access ends 2026-12-01'])
  assert.equal(adminPeriodText(sub), '2026-12-01')
})

test('checkout eligibility mirrors the server lifetime rules', () => {
  const active = (plan, extra = {}) => ({ subscription: { status: 'active', plan, currentPeriodEnd: '2027-01-01', ...extra } })
  assert.equal(getMembershipAction(null, lifetime), 'new')
  assert.equal(getMembershipAction(active(lifetime, { isLifetime: true, currentPeriodEnd: null }), lifetime), 'blocked_lifetime_active')
  assert.equal(getMembershipAction(active(lifetime, { isLifetime: true, currentPeriodEnd: null }), monthly), 'blocked_lifetime_active')
  assert.equal(getMembershipAction(active(monthly), lifetime), 'blocked_lifetime_upgrade')
  assert.equal(getMembershipAction(active(yearly), lifetime), 'blocked_lifetime_upgrade')
  assert.equal(getMembershipAction(active(monthly), monthly), 'renew')
  assert.equal(getMembershipAction(active(monthly), yearly), 'blocked_different_plan')
  assert.equal(getCheckoutErrorPresentation('lifetime_membership_active').message, 'You already have Lifetime WSF Circle access.')
  assert.equal(getCheckoutErrorPresentation('lifetime_upgrade_unavailable').showAssistance, true)
})
