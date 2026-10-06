// Pure, dependency-free helpers for the Paystack Circle checkout/callback
// UX (Module 4). Kept out of the page components specifically so this
// state-mapping logic stays easy to read and exercise in isolation — see
// each page's own comment for why: the backend's GET
// /circle/payments/<reference> response (app/api/v1/circle.py's
// CirclePaymentStatusResource) is the ONLY source of truth for whether a
// payment succeeded. Nothing here infers success from anything else.

// Mirrors the backend's nonterminal CircleSubscription statuses (see
// app/models/circle.py's CIRCLE_SUBSCRIPTION_CURRENT_STATUSES) — used only
// to classify what a Circle plan's CTA should offer, never to decide
// entitlement itself (that remains /circle/me's hasAccess boolean).
const CURRENT_SUBSCRIPTION_STATUSES = ['pending', 'active', 'past_due']

// Mirrors backend/app/services/circle_payments.py's
// _classify_membership_action() using only the data already available from
// GET /circle/me — this never substitutes for that backend check (Module 2
// re-validates everything server-side at checkout time), it only lets the
// UI show the right call-to-action instead of a surprising rejection after
// a click. Returns one of:
//   'new'                   — no current subscription; a fresh purchase.
//   'renew'                 — current subscription is for THIS plan, with
//                             a real expiry; early renewal / lapsed-payment
//                             restore.
//   'blocked_pending'       — a pending (manual-review) subscription exists.
//   'blocked_different_plan'— current subscription is for a different plan.
//   'blocked_non_expiring'  — current subscription has no period end.
export function getMembershipAction(membership, plan) {
  const subscription = membership?.subscription
  if (!subscription || !CURRENT_SUBSCRIPTION_STATUSES.includes(subscription.status)) {
    return 'new'
  }
  if (subscription.status === 'pending') return 'blocked_pending'
  if (subscription.plan?.slug !== plan.slug) return 'blocked_different_plan'
  if (!subscription.currentPeriodEnd) return 'blocked_non_expiring'
  return 'renew'
}

// Maps Module 2's stable checkout-initialization error codes (see
// app/services/circle_payments.py's ensure_paystack_configured/
// ensure_plan_payable/_raise_for_blocked_action) to safe, non-technical
// copy — never the raw backend/provider error text. `showAssistance` tells
// the caller whether to surface the existing assisted-enrollment fallback;
// `non_expiring_membership` deliberately does not, per the approved design
// ("do not offer another payment automatically" — assisted enrollment's
// own copy is about REQUESTING membership, which doesn't fit here either).
export function getCheckoutErrorPresentation(code) {
  switch (code) {
    case 'paystack_disabled':
    case 'paystack_not_configured':
    case 'payment_initialization_failed':
      return {
        message: "We couldn't start a secure checkout right now. Please try again shortly.",
        showAssistance: true,
      }
    case 'plan_not_active':
    case 'plan_not_payable':
      return {
        message: 'This plan is no longer available for online payment. Please choose another plan or contact us.',
        showAssistance: true,
      }
    case 'currency_not_supported':
      return {
        message: "This plan's currency isn't available for online payment yet. Please request assistance below and our team will help.",
        showAssistance: true,
      }
    case 'membership_pending_review':
      return {
        message: 'Your WSF Circle membership has a pending manual review. Contact us to complete it before purchasing a new period.',
        showAssistance: true,
      }
    case 'different_plan_active':
      return {
        message: "You're currently on another WSF Circle plan. Automated plan switching isn't available yet — request assistance and our team will help.",
        showAssistance: true,
      }
    case 'non_expiring_membership':
      return {
        message: "Your WSF Circle membership doesn't have an automatic expiry. Please contact us about your account.",
        showAssistance: false,
      }
    default:
      return {
        message: "We couldn't start a secure checkout right now. Please try again shortly.",
        showAssistance: true,
      }
  }
}

// Collapses the backend's {status, membershipActivated,
// reconciliationRequired} triple (GET /circle/payments/<reference>) into
// the one of five UX phases the callback page actually renders. Order
// matters: membershipActivated/consumed is checked first since it's the
// one unambiguous "done" state.
export const CIRCLE_PAYMENT_PHASE = {
  PENDING: 'pending',
  CONSUMED: 'consumed',
  RECONCILIATION: 'reconciliation',
  FAILED: 'failed',
  CONFLICT: 'conflict',
}

export function getCirclePaymentPhase(result) {
  if (!result) return CIRCLE_PAYMENT_PHASE.PENDING
  if (result.membershipActivated || result.status === 'consumed') return CIRCLE_PAYMENT_PHASE.CONSUMED
  if (result.reconciliationRequired) return CIRCLE_PAYMENT_PHASE.RECONCILIATION
  if (result.status === 'failed' || result.status === 'abandoned') return CIRCLE_PAYMENT_PHASE.FAILED
  // `verified` with no reconciliation flag and not yet consumed is the
  // rare membership_conflict outcome (see consume_verified_circle_payment's
  // own docstring) — Paystack may genuinely have been charged, so this is
  // treated with the same caution as reconciliation, never as a failure.
  if (result.status === 'verified') return CIRCLE_PAYMENT_PHASE.CONFLICT
  // 'pending', or any other provider-processing state the backend hasn't
  // resolved yet.
  return CIRCLE_PAYMENT_PHASE.PENDING
}

// The exact "still working on it" copy depends on why the backend hasn't
// resolved this yet — a genuinely temporary verification outage gets
// slightly different wording than "still pending with Paystack" per the
// approved design, even though both keep polling.
export function getPendingStatusMessage(result, timedOut) {
  if (timedOut) {
    return 'Your payment is still being confirmed. You can check your membership status shortly.'
  }
  if (result?.reason === 'verification_unavailable') {
    return "We're still confirming your payment."
  }
  return 'Confirming your payment…'
}
