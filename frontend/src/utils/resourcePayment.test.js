// Plain-Node tests for the pure Resource payment-state helper — see
// articleStructuredData.test.js for why this repo uses node:test directly
// rather than a DOM/React testing stack.
// Run with: node --test src/utils/resourcePayment.test.js
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  getResourcePaymentPhase,
  getResourcePendingStatusMessage,
  getResourceCheckoutErrorPresentation,
  RESOURCE_PAYMENT_PHASE,
} from './resourcePayment.js'

test('purchaseActivated true is CONSUMED regardless of status', () => {
  assert.equal(
    getResourcePaymentPhase({ purchaseActivated: true, status: 'pending' }),
    RESOURCE_PAYMENT_PHASE.CONSUMED,
  )
})

test('status "consumed" is CONSUMED', () => {
  assert.equal(getResourcePaymentPhase({ status: 'consumed' }), RESOURCE_PAYMENT_PHASE.CONSUMED)
})

test('reconciliationRequired is RECONCILIATION', () => {
  assert.equal(
    getResourcePaymentPhase({ status: 'verified', reconciliationRequired: true }),
    RESOURCE_PAYMENT_PHASE.RECONCILIATION,
  )
})

test('status "failed" is FAILED', () => {
  assert.equal(getResourcePaymentPhase({ status: 'failed' }), RESOURCE_PAYMENT_PHASE.FAILED)
})

test('status "abandoned" is FAILED', () => {
  assert.equal(getResourcePaymentPhase({ status: 'abandoned' }), RESOURCE_PAYMENT_PHASE.FAILED)
})

test('status "pending" is PENDING', () => {
  assert.equal(getResourcePaymentPhase({ status: 'pending' }), RESOURCE_PAYMENT_PHASE.PENDING)
})

test('a clean "verified" status not yet consumed is never treated as success', () => {
  assert.equal(getResourcePaymentPhase({ status: 'verified' }), RESOURCE_PAYMENT_PHASE.PENDING)
})

test('no result at all is PENDING', () => {
  assert.equal(getResourcePaymentPhase(undefined), RESOURCE_PAYMENT_PHASE.PENDING)
})

test('pending message before timeout', () => {
  assert.equal(getResourcePendingStatusMessage({ status: 'pending' }, false), 'Confirming your payment…')
})

test('pending message reflects a temporary verification outage', () => {
  assert.equal(
    getResourcePendingStatusMessage({ reason: 'verification_unavailable' }, false),
    "We're still confirming your payment.",
  )
})

test('timeout message overrides the reason once auto-polling gives up', () => {
  assert.equal(
    getResourcePendingStatusMessage({ reason: 'verification_unavailable' }, true),
    'Your payment is still being confirmed. You can check again shortly.',
  )
})

test('checkout error presentation never leaks raw provider/backend codes', () => {
  assert.equal(
    getResourceCheckoutErrorPresentation('currency_not_supported'),
    "This resource isn't available for online payment in its current currency yet.",
  )
  assert.equal(
    getResourceCheckoutErrorPresentation('resource_not_payable'),
    "This resource isn't available for purchase right now.",
  )
  assert.equal(getResourceCheckoutErrorPresentation('not_premium'), "This resource isn't available for purchase.")
  assert.equal(
    getResourceCheckoutErrorPresentation('paystack_disabled'),
    "We couldn't start secure checkout right now. Please try again shortly.",
  )
  assert.equal(
    getResourceCheckoutErrorPresentation('some_unknown_future_code'),
    "We couldn't start secure checkout right now. Please try again shortly.",
  )
})
