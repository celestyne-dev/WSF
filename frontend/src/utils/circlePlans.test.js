// Plain-Node tests for WSF Circle plan/membership display (Monthly, Yearly,
// Lifetime) and the lifetime checkout eligibility mirror.
// Run with: node --test src/utils/circlePlans.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  LIFETIME_EXCLUSIONS,
  LIFETIME_INCLUDED,
  LIFETIME_PLAN_HIGHLIGHTS,
  LIFETIME_SCOPE_NOTE,
  memberBadge,
  planOfferState,
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
  assert.deepEqual([monthly, yearly, lifetime].map(planTagline), ['Flexible access', 'Best for ongoing career growth', 'Pay once. Keep growing with WSF for life.'])
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
  assert.equal(LIFETIME_SCOPE_NOTE, 'Lifetime access to eligible WSF Circle digital membership benefits.')
  assert.doesNotMatch(LIFETIME_SCOPE_NOTE, /everything/i)
  assert.match(LIFETIME_EXCLUSIONS, /coaching/)
  assert.match(LIFETIME_EXCLUSIONS, /physical products/)
  assert.ok(LIFETIME_INCLUDED.some((line) => /Learning/.test(line)))
  assert.deepEqual(LIFETIME_PLAN_HIGHLIGHTS, ['One-time payment', 'No renewal', 'Lifetime access to eligible WSF digital membership benefits'])
})

test('founding offer state only reports real availability', () => {
  const founding = (availability) => ({ ...lifetime, isFounding: true, availability })
  assert.deepEqual(planOfferState({ ...lifetime, availability: { limited: false } }), { heading: null, status: null, remaining: null, full: false })
  const open = planOfferState(founding({ limited: true, maxMembers: 100, remaining: 37, full: false }))
  assert.equal(open.heading, 'Founding Lifetime Membership')
  assert.equal(open.status, 'Limited availability')
  assert.equal(open.remainingText, '37 places remaining')
  assert.equal(planOfferState(founding({ limited: true, maxMembers: 100, remaining: 1, full: false })).remainingText, '1 place remaining')
  const full = planOfferState(founding({ limited: true, maxMembers: 100, remaining: 0, full: true }))
  assert.equal(full.status, 'Founding offer full')
  assert.equal(full.full, true)
  assert.equal(planOfferState({ ...monthly, availability: { limited: true, remaining: 0, full: true } }).status, 'Plan full')
  // No count from the server -> no invented number.
  assert.equal(planOfferState(founding({ limited: true, full: false })).remainingText, null)
})

test('member badge comes from the server only', () => {
  assert.equal(memberBadge({ memberBadge: 'Lifetime Member' }), 'Lifetime Member')
  assert.equal(memberBadge({ memberBadge: 'Founding Lifetime Member' }), 'Founding Lifetime Member')
  assert.equal(memberBadge({ isLifetime: true, memberBadge: null }), null)
  assert.equal(memberBadge(null), null)
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
