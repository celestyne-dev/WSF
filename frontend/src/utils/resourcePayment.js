// Pure, dependency-free helpers for the Paystack premium-Resource
// checkout/callback UX (Stage 2). Kept out of the page components for
// the same reason as utils/circlePayment.js: the backend's GET
// /resources/payments/<reference> response (app/api/v1/resources.py's
// ResourcePaymentStatusResource) is the ONLY source of truth for whether
// a purchase succeeded. Nothing here invents entitlement client-side.

export const RESOURCE_PAYMENT_PHASE = {
  PENDING: 'pending',
  CONSUMED: 'consumed',
  RECONCILIATION: 'reconciliation',
  FAILED: 'failed',
}

// Collapses the backend's {status, purchaseActivated,
// reconciliationRequired} triple into the one of four UX phases the
// callback page actually renders. Order matters: purchaseActivated/
// consumed is checked first since it's the one unambiguous "done" state.
// Unlike Circle's renewal/plan-switch logic, a one-time Resource purchase
// has no further "conflict" classification (see
// app/services/resource_payments.py's consume_verified_resource_payment),
// so a clean `verified` status that hasn't been consumed yet is simply
// treated the same conservative way as a still-pending payment — never
// as success.
export function getResourcePaymentPhase(result) {
  if (!result) return RESOURCE_PAYMENT_PHASE.PENDING
  if (result.purchaseActivated || result.status === 'consumed') return RESOURCE_PAYMENT_PHASE.CONSUMED
  if (result.reconciliationRequired) return RESOURCE_PAYMENT_PHASE.RECONCILIATION
  if (result.status === 'failed' || result.status === 'abandoned') return RESOURCE_PAYMENT_PHASE.FAILED
  // 'pending', 'verified' (not yet consumed), or any other
  // provider-processing state the backend hasn't resolved yet.
  return RESOURCE_PAYMENT_PHASE.PENDING
}

// The exact "still working on it" copy depends on why the backend hasn't
// resolved this yet — mirrors utils/circlePayment.js's
// getPendingStatusMessage exactly, Resource-flavored.
export function getResourcePendingStatusMessage(result, timedOut) {
  if (timedOut) {
    return 'Your payment is still being confirmed. You can check again shortly.'
  }
  if (result?.reason === 'verification_unavailable') {
    return "We're still confirming your payment."
  }
  return 'Confirming your payment…'
}

// Maps Stage 1's stable checkout-initialization error codes (see
// app/services/resource_payments.py's ensure_paystack_configured/
// ensure_resource_payable) to safe, non-technical copy — never the raw
// backend/provider error text. `already_purchased` is deliberately NOT
// handled here: the caller re-evaluates access directly instead of
// showing any failure message at all (see ResourceDetailPage.jsx's
// handlePremiumCheckout — backend entitlement remains authoritative
// either way).
export function getResourceCheckoutErrorPresentation(code) {
  switch (code) {
    case 'currency_not_supported':
      return "This resource isn't available for online payment in its current currency yet."
    case 'resource_not_payable':
      return "This resource isn't available for purchase right now."
    case 'not_premium':
      return "This resource isn't available for purchase."
    case 'paystack_disabled':
    case 'paystack_not_configured':
    case 'payment_initialization_failed':
    default:
      return "We couldn't start secure checkout right now. Please try again shortly."
  }
}
