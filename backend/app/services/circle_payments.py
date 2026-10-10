"""Module 2 of the Paystack Circle integration: the security-critical
server-side core — initialize checkout, verify with Paystack, and
idempotently activate/extend Circle membership. See app/services/
paystack.py (Module 1's thin API client) and app/models/circle.py's
CirclePayment for the schema this builds on.

No webhook and no frontend exist yet (see api/v1/circle.py's own
docstring) — this module is deliberately structured so a future webhook
handler can call consume_verified_circle_payment() directly, without
duplicating any entitlement logic: that function is the ONE place a
verified CirclePayment is ever turned into Circle access.

LOCKING: two distinct mechanisms, used for two distinct races.

1. Checkout initiation (start_circle_checkout) takes a Postgres
   transaction-scoped advisory lock keyed on (user_id, plan_id) —
   `pg_advisory_xact_lock(user_id, plan_id)` — held for the *entire*
   initiation, including the outbound Paystack call. This is a
   deliberate, narrow exception to the usual "don't hold a lock across a
   network call" rule: releasing the lock before calling Paystack (the
   lighter option) was tried first and rejected, because it reopens
   exactly the race it exists to close — a second concurrent request can
   still land between "insert the local pending row" and "record the
   returned authorization_url", see a pending row with no usable URL
   yet, and initialize a second Paystack transaction anyway. The lock is
   scoped to one (user, plan) pair (never a table or a global lock), so
   it only ever serializes a user's own repeated clicks on the same
   plan, and it's bounded by Paystack's own request timeout
   (app/services/paystack.py's 15s read timeout) — not an open-ended
   hold. See start_circle_checkout()'s own docstring for the decision
   this trades off.

2. Verification/consumption (consume_verified_circle_payment,
   _verify_with_provider_if_due) use ordinary row-level locking
   (`SELECT ... FOR UPDATE`) on the CirclePayment row itself — the same
   pattern app/services/event_registrations.py already uses for
   capacity races — plus, when extending an existing subscription, the
   same lock on that CircleSubscription row. Lock order is always
   CirclePayment then CircleSubscription, consistently, across every
   call site here, so there is no path that could deadlock against
   itself.

WEBHOOK RECOVERY (Module 3): api/v1/webhooks.py's Paystack route is the
ONLY caller of _verify_with_provider_for_webhook/
process_circle_webhook_charge_success below, and only after it has
already verified the delivery's HMAC signature and confirmed the event
is `charge.success` — this module trusts that has already happened and
never re-derives it. That trust is exactly what lets this module do one
thing an ordinary request never may: reopen a `failed`/`abandoned`
CirclePayment (pending/processing-provider delays, a user who abandoned
checkout and completed it later, etc.) by running a fresh Paystack
Verify and, if it now says `success` with every invariant matching,
carrying it through to `verified` -> consumed via the exact same
consume_verified_circle_payment() used everywhere else. A mismatch on
that fresh verify still lands in the same verified+reconciliation_required
quarantine Module 2 established — recovery never bypasses invariant
checking, it only bypasses the "must start from `pending`" restriction
that protects ordinary user-facing polling from reopening settled
payments. An already-`verified`-but-flagged payment is deliberately
NOT re-verified or auto-cleared by a bare webhook redelivery alone (see
_verify_with_provider_for_webhook) — Module 3's conservative MVP
reconciliation policy.
"""
from datetime import datetime, timedelta, timezone

from dateutil.relativedelta import relativedelta
from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.circle import CirclePayment, CircleSubscription
from app.services.audit import log_action
from app.services.circle import get_current_subscription, validate_subscription_status_transition
from app.services.paystack import (
    PaystackAPIError,
    PaystackNotConfiguredError,
    generate_reference,
    initialize_transaction,
    verify_transaction,
)
from app.utils.responses import ApiError

# A near-duplicate "Pay securely" click within this window, for the same
# user and plan, reuses the still-usable pending checkout instead of
# starting a second Paystack transaction. Deliberately short — this is a
# double-click/retry guard, not a general-purpose cache.
_PENDING_REUSE_WINDOW = timedelta(minutes=10)

# How often a `pending` CirclePayment's status may be re-checked against
# Paystack. Bounds repeated browser refreshes/polling on the future
# callback page to something far short of "every request hits Paystack".
_VERIFY_THROTTLE = timedelta(seconds=5)

# Small, explicitly allowlisted subset of app/services/paystack.py's
# verify_transaction() result kept in CirclePayment.provider_snapshot —
# see that module's own docstring for why nothing broader is ever
# persisted. "customer_email" is deliberately excluded even though
# verify_transaction() returns it: it's only ever compared in memory for
# the invariant check below, never written to storage, since the
# snapshot already carries the WSF-side expected email on the same row
# (CirclePayment.customer_email).
_SNAPSHOT_FIELDS = ("status", "amount", "currency", "channel", "paid_at", "gateway_response")

_MEMBERSHIP_ACTION_NEW = "new"
_MEMBERSHIP_ACTION_RENEW = "renew"
_MEMBERSHIP_BLOCKED_PENDING = "blocked_pending"
_MEMBERSHIP_BLOCKED_DIFFERENT_PLAN = "blocked_different_plan"
_MEMBERSHIP_BLOCKED_NON_EXPIRING = "blocked_non_expiring"


def _add_billing_interval(dt, billing_interval):
    """Calendar month/year arithmetic — never a fixed 30-day/365-day
    delta. relativedelta clamps an out-of-range day to the target
    month's last valid day on its own (Jan 31 + 1 month -> Feb 28, or
    Feb 29 in a leap year; Mar 31 + 1 month -> Apr 30), which is exactly
    the behavior Module 2's calendar-period requirement calls for.
    """
    if billing_interval == "yearly":
        return dt + relativedelta(years=1)
    return dt + relativedelta(months=1)


def ensure_paystack_configured():
    """Checked at checkout-initiation time, independent of the identical
    check app/services/paystack.py's own _secret_key() performs right
    before actually calling Paystack — this one exists so a disabled/
    unconfigured integration fails with a clear, stable application
    error before any CirclePayment row is even created.
    """
    if not current_app.config.get("PAYSTACK_ENABLED"):
        raise ApiError("Online WSF Circle payments aren't enabled yet.", 503, code="paystack_disabled")
    if not current_app.config.get("PAYSTACK_SECRET_KEY"):
        raise ApiError("Online WSF Circle payments aren't configured yet.", 503, code="paystack_not_configured")


def ensure_plan_payable(plan):
    """Plan-side eligibility only — membership-state eligibility is
    _classify_membership_action() below. No currency conversion is ever
    performed: a plan priced outside PAYSTACK_ALLOWED_CURRENCIES is
    simply not payable online yet (see config.py's own docstring on that
    setting).
    """
    if plan.status != "active":
        raise ApiError("This plan is not currently available.", 422, code="plan_not_active")
    if plan.price <= 0:
        raise ApiError("This plan cannot be purchased online.", 422, code="plan_not_payable")
    allowed_currencies = {c.strip().upper() for c in (current_app.config.get("PAYSTACK_ALLOWED_CURRENCIES") or [])}
    if plan.currency.strip().upper() not in allowed_currencies:
        raise ApiError("This plan's currency isn't enabled for online payment yet.", 422, code="currency_not_supported")


def _classify_membership_action(user, plan):
    """The one place checkout eligibility AND payment-consumption time
    both decide what a successful payment for `plan` should do to
    `user`'s membership — called twice (once to gate checkout, once
    again under lock at consumption time, since minutes/hours may have
    passed) so the two can never silently disagree.

    Returns (action, current_subscription_or_None):

    - no current (pending/active/past_due) subscription at all -> "new"
    - current active/past_due, same plan, has a real current_period_end
      -> "renew" (early renewal / lapsed-payment restore — past_due ->
      active is an existing legal transition, see app/services/
      circle.py's _ALLOWED_TRANSITIONS)
    - current status == "pending" -> "blocked_pending": this status
      means "awaiting manual/external confirmation" (see
      app/models/circle.py's own docstring) — some staff-driven process
      may already be in flight, so an automated Paystack payment must
      never silently resolve it instead.
    - current plan differs from the one being purchased ->
      "blocked_different_plan": no automated upgrade/downgrade in this
      MVP.
    - current active/past_due with no current_period_end ->
      "blocked_non_expiring": a null period end means non-expiring
      (manual/complimentary) access — automated checkout must never sell
      a second, redundant automatic period over it.
    """
    current = get_current_subscription(user)
    if current is None:
        return _MEMBERSHIP_ACTION_NEW, None
    if current.status == "pending":
        return _MEMBERSHIP_BLOCKED_PENDING, current
    if current.plan_id != plan.id:
        return _MEMBERSHIP_BLOCKED_DIFFERENT_PLAN, current
    if current.current_period_end is None:
        return _MEMBERSHIP_BLOCKED_NON_EXPIRING, current
    return _MEMBERSHIP_ACTION_RENEW, current


def _raise_for_blocked_action(action):
    if action == _MEMBERSHIP_BLOCKED_PENDING:
        raise ApiError(
            "Your WSF Circle membership has a pending manual review. "
            "Contact us to complete it before purchasing a new period.",
            409, code="membership_pending_review",
        )
    if action == _MEMBERSHIP_BLOCKED_DIFFERENT_PLAN:
        raise ApiError(
            "You're currently on another Circle plan. Contact us if you'd like to "
            "change plans before your current period ends.",
            409, code="different_plan_active",
        )
    if action == _MEMBERSHIP_BLOCKED_NON_EXPIRING:
        raise ApiError(
            "Your WSF Circle membership doesn't have an automatic expiry. "
            "Contact us about your account before purchasing a new period.",
            409, code="non_expiring_membership",
        )


def _build_callback_url():
    base = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    return f"{base}/circle/checkout/callback"


def _find_reusable_pending_payment(user, plan):
    """Within _PENDING_REUSE_WINDOW, for this exact user+plan: reuse the
    most recent `pending` row that actually has a usable
    authorization_url AND whose snapshotted amount/currency/billing_interval
    still match the plan's CURRENT terms. A plan's price/currency/interval
    can change between when a pending checkout was created and now (e.g.
    a plan repriced from KES to USD) — reusing a stale checkout would
    hand the browser an authorization_url for terms that no longer match
    what the plan now charges, with nothing re-validating that at
    verification time (see _invariant_mismatches, which only ever
    compares against the PAYMENT's own snapshot, never the plan's
    current fields).

    Any other recent `pending` row — one with no usable
    authorization_url (its Paystack initialize call never completed,
    e.g. the process died between the local insert and the provider
    response), or one whose terms no longer match the plan — can never
    be returned, so it's marked `failed` here rather than ever being
    handed back as a checkout destination, and a fresh attempt proceeds
    normally. Does not commit — the caller holds the advisory lock for
    the whole decision (see module docstring) and commits once.
    """
    window_start = datetime.now(timezone.utc) - _PENDING_REUSE_WINDOW
    candidates = (
        CirclePayment.query.filter(
            CirclePayment.user_id == user.id,
            CirclePayment.plan_id == plan.id,
            CirclePayment.status == "pending",
            CirclePayment.created_at >= window_start,
        )
        .order_by(CirclePayment.created_at.desc())
        .all()
    )
    expected_amount_subunits = plan.price * 100
    expected_currency = plan.currency.strip().upper()
    reusable = None
    for candidate in candidates:
        if not candidate.authorization_url:
            candidate.status = "failed"
            continue
        matches_current_terms = (
            candidate.amount_subunits == expected_amount_subunits
            and candidate.currency.strip().upper() == expected_currency
            and candidate.billing_interval == plan.billing_interval
        )
        if not matches_current_terms:
            candidate.status = "failed"
            continue
        if reusable is None:
            reusable = candidate
    return reusable


def start_circle_checkout(user, plan):
    """The one entry point for "Pay securely". Deliberately takes only
    `user` (from the authenticated session) and `plan` (looked up
    server-side from the URL slug by the caller) — nothing about amount,
    currency, billing interval, or whose account this is for ever comes
    from the request body; see this module's docstring and
    app/models/circle.py's CirclePayment for why those are always
    snapshotted from the database at this exact moment instead.

    Returns {"reference": str, "authorization_url": str}. Raises
    ApiError for every rejection path (plan/membership ineligibility,
    Paystack disabled/unconfigured, or a genuine Paystack initialize
    failure) — never silently returns a broken checkout.
    """
    ensure_paystack_configured()
    ensure_plan_payable(plan)

    action, _current = _classify_membership_action(user, plan)
    if action != _MEMBERSHIP_ACTION_NEW:
        _raise_for_blocked_action(action)
    # action is now always "new" or "renew" — both may check out; a
    # "renew" payment extends the existing subscription once verified
    # (see consume_verified_circle_payment), it is never blocked here.

    # See module docstring: this advisory lock is held across the
    # Paystack call on purpose, not released beforehand.
    db.session.execute(text("SELECT pg_advisory_xact_lock(:user_id, :plan_id)"), {"user_id": user.id, "plan_id": plan.id})

    reused = _find_reusable_pending_payment(user, plan)
    if reused is not None:
        db.session.commit()
        log_action(
            user, "circle_payment.checkout_initialized", "CirclePayment", reused.id,
            changes={"planSlug": plan.slug, "reused": True},
        )
        return {"reference": reused.reference, "authorization_url": reused.authorization_url}

    reference = generate_reference()
    amount_subunits = plan.price * 100
    customer_email = user.email.strip().lower()
    payment = CirclePayment(
        reference=reference,
        user_id=user.id,
        plan_id=plan.id,
        amount_subunits=amount_subunits,
        currency=plan.currency,
        billing_interval=plan.billing_interval,
        customer_email=customer_email,
        status="pending",
    )
    db.session.add(payment)
    db.session.flush()  # assigns payment.id; transaction/lock stays open

    try:
        result = initialize_transaction(
            amount_subunits=amount_subunits,
            email=customer_email,
            reference=reference,
            currency=plan.currency,
            callback_url=_build_callback_url(),
            metadata={"plan_id": plan.id, "user_id": user.id},
        )
    except (PaystackNotConfiguredError, PaystackAPIError) as exc:
        payment.status = "failed"
        db.session.commit()
        log_action(
            user, "circle_payment.initialization_failed", "CirclePayment", payment.id,
            changes={"planSlug": plan.slug, "reason": str(exc)},
        )
        raise ApiError(
            "We couldn't start a secure checkout right now. Please try again shortly.",
            502, code="payment_initialization_failed",
        )

    if result.get("reference") != payment.reference:
        # Nothing has been verified as paid at this point — this is a
        # structurally different failure from a verify-time mismatch, so
        # it takes the existing initialization-failure path (local
        # payment marked failed, no membership, no reconciliation state)
        # rather than ever being treated as a possible real charge.
        payment.status = "failed"
        db.session.commit()
        log_action(
            user, "circle_payment.initialization_failed", "CirclePayment", payment.id,
            changes={"planSlug": plan.slug, "reason": "provider_reference_mismatch"},
        )
        raise ApiError(
            "We couldn't start a secure checkout right now. Please try again shortly.",
            502, code="payment_initialization_failed",
        )

    payment.authorization_url = result["authorization_url"]
    db.session.commit()
    log_action(
        user, "circle_payment.checkout_initialized", "CirclePayment", payment.id,
        changes={"planSlug": plan.slug, "reused": False},
    )
    return {"reference": payment.reference, "authorization_url": payment.authorization_url}


def get_circle_payment_or_404(user, reference):
    """Same 404 regardless of whether `reference` doesn't exist at all or
    belongs to someone else — a probing request must never be able to
    tell those two cases apart.
    """
    payment = CirclePayment.query.filter_by(reference=reference).first()
    if payment is None or payment.user_id != user.id:
        raise ApiError("Payment not found.", 404, code="not_found")
    return payment


def _parse_provider_timestamp(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _invariant_mismatches(payment, result):
    """Compares Paystack's verify response against CirclePayment's own
    snapshots (never against CirclePlan's current, possibly-since-edited
    fields — see that model's docstring). Integer equality for amount,
    no floats anywhere; email compared case-insensitively after
    stripping, per the approved invariant.
    """
    mismatches = []
    if result.get("amount") != payment.amount_subunits:
        mismatches.append("amount")
    provider_currency = (result.get("currency") or "").strip().upper()
    if provider_currency != payment.currency.strip().upper():
        mismatches.append("currency")
    provider_email = (result.get("customer_email") or "").strip().casefold()
    expected_email = payment.customer_email.strip().casefold()
    if not provider_email or provider_email != expected_email:
        mismatches.append("email")
    # Exact string comparison — deliberately NOT case-normalized, unlike
    # the email check above. References are opaque identifiers we
    # generated ourselves (see generate_reference()); a case difference
    # is itself a sign the provider reported a different transaction.
    if result.get("reference") != payment.reference:
        mismatches.append("reference")
    return mismatches


def _build_provider_snapshot(result, mismatches):
    snapshot = {field: result.get(field) for field in _SNAPSHOT_FIELDS}
    if mismatches:
        snapshot["reconciliation_required"] = True
        snapshot["mismatches"] = sorted(mismatches)
    return snapshot


def _needs_reconciliation(payment):
    return bool(payment.provider_snapshot and payment.provider_snapshot.get("reconciliation_required"))


def _apply_provider_verify_result(locked, result, now):
    """Mutates `locked`'s status/snapshot/verification fields in place
    from an already-fetched Paystack verify `result` — the exact
    success/abandoned/failed/pending interpretation Module 2
    established. Does not commit, and does not touch
    last_verification_attempt_at — callers own both, since the two
    callers below (throttled browser polling vs. trusted webhook
    recovery) manage that timestamp differently. Shared so this mapping
    is defined in exactly one place rather than risking the two callers
    drifting apart.

    Returns (reason, mismatches): `reason` is None (clean success),
    "reconciliation_required", "abandoned", "failed", or "pending" —
    the same vocabulary _verify_with_provider_if_due has always
    returned to its own callers.
    """
    provider_status = result.get("status")

    if provider_status == "success":
        mismatches = _invariant_mismatches(locked, result)
        locked.status = "verified"
        locked.verified_at = now
        locked.paid_at = _parse_provider_timestamp(result.get("paid_at"))
        locked.provider_transaction_id = result.get("provider_transaction_id")
        locked.provider_channel = result.get("channel")
        locked.provider_snapshot = _build_provider_snapshot(result, mismatches)
        return ("reconciliation_required" if mismatches else None), mismatches

    if provider_status == "abandoned":
        locked.status = "abandoned"
        return "abandoned", []

    if provider_status == "failed":
        locked.status = "failed"
        return "failed", []

    # Paystack's own transaction is still pending/processing — WSF's
    # status is left exactly as-is so a later check can try again.
    return "pending", []


def _verify_with_provider_if_due(payment):
    """Locks the CirclePayment row, then — only if it's still `pending`
    and wasn't checked within _VERIFY_THROTTLE — calls Paystack's verify
    API exactly once and interprets the result via
    _apply_provider_verify_result (see that function for the
    success/abandoned/failed/pending mapping).

    Returns (payment, reason) where `reason` is a short, stable string
    for the API response when the status itself doesn't say enough
    (None when nothing more needs saying).
    """
    # populate_existing() is required here, not optional: `payment` was
    # already loaded (unlocked) by the caller, so without it SQLAlchemy's
    # identity map would keep returning that stale, already-cached
    # object without overwriting its attributes from this query's row —
    # even though the row lock itself is correctly acquired, `.status`
    # would keep reading its old value in Python. See this module's own
    # concurrency test for the exact race this guards.
    locked = CirclePayment.query.with_for_update().populate_existing().filter_by(id=payment.id).one()
    if locked.status != "pending":
        return locked, None

    now = datetime.now(timezone.utc)
    if locked.last_verification_attempt_at and now - locked.last_verification_attempt_at < _VERIFY_THROTTLE:
        return locked, "verification_recently_attempted"

    locked.last_verification_attempt_at = now
    try:
        result = verify_transaction(locked.reference)
    except (PaystackNotConfiguredError, PaystackAPIError) as exc:
        db.session.commit()
        log_action(
            locked.user, "circle_payment.verification_unavailable", "CirclePayment", locked.id,
            changes={"reason": str(exc)},
        )
        return locked, "verification_unavailable"

    reason, mismatches = _apply_provider_verify_result(locked, result, now)
    db.session.commit()

    if reason == "reconciliation_required":
        log_action(
            locked.user, "circle_payment.verification_mismatch", "CirclePayment", locked.id,
            changes={"mismatches": sorted(mismatches)},
        )
        return locked, reason
    if reason is None:
        log_action(locked.user, "circle_payment.verification_succeeded", "CirclePayment", locked.id)
        return locked, None
    if reason == "abandoned":
        log_action(locked.user, "circle_payment.verification_abandoned", "CirclePayment", locked.id)
        return locked, reason
    if reason == "failed":
        log_action(locked.user, "circle_payment.verification_failed", "CirclePayment", locked.id)
        return locked, reason
    return locked, reason  # "pending"


def _verify_with_provider_for_webhook(payment):
    """Trusted-webhook-only verification/recovery entry point — see this
    module's WEBHOOK RECOVERY docstring section. The ONLY place a
    `failed`/`abandoned` CirclePayment may be reopened, and only because
    the caller (api/v1/webhooks.py, after HMAC verification) has already
    established this is a genuine, provider-authenticated `charge.success`
    delivery. Never call this from an ordinary user-facing endpoint, and
    never for any other event type.

    Unlike _verify_with_provider_if_due (`pending`-only, always
    throttled — browser polling), this accepts `pending`, `failed`, or
    `abandoned` local state and does not apply _VERIFY_THROTTLE: a
    webhook delivery isn't a loop a user can spam, and Paystack's own
    retry schedule already spaces deliveries out.

    `consumed` is a pure replay, returned untouched with no new Paystack
    call. An existing `verified`-but-reconciliation-flagged row is also
    left exactly as-is — Module 3's deliberately conservative MVP
    policy: a bare webhook redelivery alone never re-verifies or
    auto-clears an existing mismatch flag.

    Returns (locked_payment, reason, status). `reason` reuses
    _apply_provider_verify_result's vocabulary, plus "already_consumed".
    `status` is the CirclePayment's status as of the moment this call
    itself determined it — captured in a local variable rather than
    read back off `locked` after any commit this call makes. Flask-
    SQLAlchemy's default `expire_on_commit=True` marks every attribute
    on `locked` (including `.status`) as needing a fresh, unlocked
    reload the instant this function's own `db.session.commit()` below
    returns. On a genuinely simultaneous duplicate `charge.success`
    delivery, a concurrent sibling call can — in the gap between that
    commit and this function returning — race ahead, consume the
    payment, and commit `consumed` itself; a later bare `locked.status`
    read would then reload *that* value instead of the one this call
    just established, even though this call is the one reporting the
    result. Callers must branch on the returned `status`/`reason`, never
    on `locked.status`, for exactly this reason — see this module's own
    concurrency test.
    Raises PaystackAPIError/PaystackNotConfiguredError straight through
    on a transient provider failure — nothing is mutated or committed
    on that path, and the caller (the webhook route) must turn the
    exception into a non-2xx response so Paystack's own retry can safely
    try again later.
    """
    locked = CirclePayment.query.with_for_update().populate_existing().filter_by(id=payment.id).one()
    prior_status = locked.status

    if prior_status == "consumed":
        return locked, "already_consumed", prior_status

    if prior_status == "verified":
        # No commit happens on this branch, so `locked.status` is never
        # expired here — reading it again below would still be safe, but
        # returning the already-known value keeps this function's
        # contract uniform across all three branches.
        reason = "reconciliation_required" if _needs_reconciliation(locked) else None
        return locked, reason, prior_status

    # pending / failed / abandoned — all three are eligible for a fresh,
    # trusted verify; a webhook-authenticated charge.success is exactly
    # the condition that may reopen the latter two (see module docstring).
    now = datetime.now(timezone.utc)
    locked.last_verification_attempt_at = now
    result = verify_transaction(locked.reference)  # may raise — nothing committed yet, see docstring
    reason, mismatches = _apply_provider_verify_result(locked, result, now)
    # Captured BEFORE commit — see the "status" paragraph in this
    # function's own docstring for exactly why this must not be read
    # from `locked.status` after the commit below instead.
    status = locked.status
    db.session.commit()

    if reason == "reconciliation_required":
        log_action(
            None, "circle_payment.webhook_reconciliation", "CirclePayment", locked.id,
            changes={"mismatches": sorted(mismatches), "priorStatus": prior_status},
        )
    elif reason is None and prior_status in ("failed", "abandoned"):
        log_action(
            None, "circle_payment.webhook_recovered", "CirclePayment", locked.id,
            changes={"from": prior_status},
        )

    return locked, reason, status


def process_circle_webhook_charge_success(reference):
    """THE one entry point api/v1/webhooks.py's Paystack route calls for
    an HMAC-verified `charge.success` event — see this module's WEBHOOK
    RECOVERY docstring section for the full policy. Starts only once the
    caller has already confirmed the signature is valid, the event type
    is `charge.success`, and `reference` was read from the payload's
    `data.reference` — everything from "look up the matching
    CirclePayment" onward is this function's job, and it defers to the
    exact same consume_verified_circle_payment() every other entry point
    uses — never a second copy of activation logic.

    Returns {"outcome": str, "payment": CirclePayment | None} where
    outcome is one of:

    - "unknown_reference": no matching CirclePayment exists. Never
      creates one, never infers a user/plan from webhook metadata — a
      retry cannot manufacture a missing local WSF payment intent.
    - "already_consumed": a safe replay of an already-fully-processed
      payment — no new Paystack call, no new mutation.
    - "reconciliation_required": Paystack confirmed success (just now,
      or on a prior check) but at least one invariant doesn't match
      this CirclePayment's own snapshots — membership is never
      activated/extended from this state.
    - "membership_conflict": verified and unflagged, but the account's
      current membership state no longer matches what this payment was
      for (see consume_verified_circle_payment) — never activates.
    - "consumed": a new subscription was created, or an existing one
      was extended — exactly once, however many times this same
      webhook is ever redelivered.
    - "not_yet_confirmed": the event claims `charge.success`, but a
      fresh Paystack Verify call, performed just now, did NOT return
      "success" (it said pending/processing, failed, or abandoned
      instead). This is a genuine inconsistency between what Paystack's
      webhook claims and what Paystack's own Verify API currently
      confirms — WSF treats that inconsistency as not yet safely
      processable, never as "handled": the local payment is left in
      whatever status _apply_provider_verify_result just computed from
      that fresh Verify response (unchanged if it still says pending;
      failed/abandoned if Verify says so) and this outcome signals the
      caller to respond non-2xx so Paystack retries the delivery later.
      A later retry whose fresh Verify finally does return "success"
      follows the ordinary matched/reconciliation path above instead.

    Raises PaystackAPIError/PaystackNotConfiguredError straight through
    for a transient provider failure, and lets any database error
    propagate too — the caller must translate both into a non-2xx
    response so Paystack's own webhook retry schedule gets a chance to
    succeed later.
    """
    payment = CirclePayment.query.filter_by(reference=reference).one_or_none()
    if payment is None:
        return {"outcome": "unknown_reference", "payment": None}

    # Branch on the `status`/`reason` _verify_with_provider_for_webhook
    # itself determined — never re-read `locked.status` or re-call
    # _needs_reconciliation(locked) here. Either would, once that call's
    # own commit has run, trigger a fresh unlocked reload of `locked`'s
    # expired attributes that can observe a concurrent sibling webhook
    # delivery's LATER write (e.g. "consumed") instead of the outcome
    # this call is reporting. See _verify_with_provider_for_webhook's
    # own docstring and this module's concurrency test.
    locked, reason, status = _verify_with_provider_for_webhook(payment)

    if reason == "already_consumed":
        log_action(None, "circle_payment.webhook_replay", "CirclePayment", locked.id)
        return {"outcome": "already_consumed", "payment": locked}

    if status == "verified" and reason != "reconciliation_required":
        # Covers both: (a) Paystack's webhook-triggered fresh Verify
        # just confirmed success cleanly, and (b) crash-recovery — this
        # payment was already sitting in a clean `verified` state from
        # an earlier verification (browser poll or a prior webhook) that
        # never reached consumption (e.g. a process/DB interruption
        # between marking it verified and activating membership). A
        # trusted charge.success delivery is exactly the trigger that
        # should resume that interrupted activation; no second Paystack
        # call is needed since the existing verified state already
        # carries the authoritative evidence (see
        # _verify_with_provider_for_webhook's own docstring).
        # consume_verified_circle_payment is idempotent and re-locks the
        # row itself, so this is always safe to call unconditionally,
        # including on a replay that already consumed it.
        result = consume_verified_circle_payment(locked.reference, actor_user=None)
        return {"outcome": result["outcome"], "payment": result["payment"]}

    if status == "verified":
        # reason == "reconciliation_required" — flagged, either just now
        # or already before this delivery arrived (Module 3's
        # deliberately conservative MVP policy: a bare webhook
        # redelivery alone never re-verifies or auto-clears an existing
        # mismatch flag).
        return {"outcome": "reconciliation_required", "payment": locked}

    # pending / failed / abandoned at this point can only mean the fresh
    # Verify _verify_with_provider_for_webhook just performed did NOT
    # return "success" (a "success" result would have made `status`
    # "verified" above) — Paystack's webhook claims charge.success while
    # Paystack's own Verify API disagrees. Never acknowledged as fully
    # handled; the caller must respond non-2xx so this delivery is
    # retried once WSF can independently confirm success.
    return {"outcome": "not_yet_confirmed", "payment": locked}


def _create_new_subscription_for_payment(payment, user, plan):
    """Deliberately NOT a call to app/services/circle.py's
    create_subscription_for_user(): that helper commits internally,
    which would make it impossible to mark this CirclePayment `consumed`
    in the SAME transaction as the CircleSubscription insert — exactly
    the atomicity Module 2 requires ("if subscription creation fails,
    the payment must not become falsely consumed"). This mirrors that
    helper's own insert + the database's partial-unique-index-driven
    IntegrityError handling, just without its own intermediate commit,
    so the caller can fold both mutations into one final commit.
    """
    now = datetime.now(timezone.utc)
    subscription = CircleSubscription(
        user_id=user.id,
        plan_id=plan.id,
        status="active",
        source="external",
        provider="paystack",
        payment_reference=payment.reference,
        starts_at=now,
        current_period_start=now,
        current_period_end=_add_billing_interval(now, plan.billing_interval),
    )
    db.session.add(subscription)
    try:
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        return None, True
    return subscription, False


def _extend_subscription_for_payment(current, plan):
    """Early renewal / lapsed-payment restore: extends from
    max(current_period_end, now) by one calendar billing interval —
    never resets starts_at, never discards remaining access. Re-checks
    plan/status under the row lock since time may have passed since
    _classify_membership_action's own unlocked read.
    """
    # populate_existing() — see _verify_with_provider_if_due's identical
    # comment; `current` here was already loaded (unlocked) by
    # _classify_membership_action's own get_current_subscription() call.
    locked = CircleSubscription.query.with_for_update().populate_existing().filter_by(id=current.id).one()
    if locked.plan_id != plan.id or locked.status not in ("active", "past_due"):
        return None, True

    now = datetime.now(timezone.utc)
    base = locked.current_period_end if (locked.current_period_end and locked.current_period_end > now) else now
    locked.current_period_end = _add_billing_interval(base, plan.billing_interval)
    if locked.status == "past_due":
        validate_subscription_status_transition(locked.status, "active")
        locked.status = "active"
    return locked, False


def consume_verified_circle_payment(reference, actor_user=None):
    """THE one place a verified CirclePayment is turned into Circle
    access — the exact function a future webhook handler must call too,
    never a second copy of this logic. Transaction-safe and idempotent:
    locks the CirclePayment row first, so two simultaneous verification
    requests, a future webhook racing this module's own callback-poll
    path, a browser refresh, or a plain retry can never grant more than
    one membership period for one CirclePayment. `reference` remains the
    one idempotency key.

    Returns {"payment": CirclePayment, "outcome": str} where outcome is
    one of:

    - "already_consumed": no-op — this exact payment was consumed
      before; no second subscription, no duplicate audit/email side
      effects.
    - "not_ready": the payment isn't `verified` yet (still pending, or
      verified-but-flagged-for-reconciliation) — nothing is mutated.
    - "membership_conflict": the payment IS verified and unflagged, but
      the account's current membership state no longer matches what
      this payment was for (e.g. a different plan was activated in the
      meantime) — never activates/extends; the payment stays `verified`
      for manual reconciliation rather than silently granting the wrong
      entitlement.
    - "consumed": a new subscription was created, or an existing one was
      extended, and this CirclePayment now points at it.

    `actor_user` is who the resulting AuditLog entries are attributed to
    — the GET endpoint passes the payment's own owner (the only user who
    could have triggered this via Module 2's endpoints); a future
    webhook caller would have no HTTP user and should pass None, the
    same "system action" convention app/services/audit.py's log_action()
    already documents.
    """
    # populate_existing() — see _verify_with_provider_if_due's identical
    # comment. Defensive here too: this function may be called right
    # after this same session already loaded this exact row (from
    # get_payment_status's own flow), or independently (a future
    # webhook, a test) where some other code may have pre-loaded it.
    payment = CirclePayment.query.with_for_update().populate_existing().filter_by(reference=reference).one_or_none()
    if payment is None:
        raise ApiError("Unknown payment reference.", 404, code="not_found")

    if payment.status == "consumed":
        return {"payment": payment, "outcome": "already_consumed"}

    if payment.status != "verified" or _needs_reconciliation(payment):
        return {"payment": payment, "outcome": "not_ready"}

    user = payment.user
    plan = payment.plan
    action, current = _classify_membership_action(user, plan)

    conflict = True
    subscription = None
    if action == _MEMBERSHIP_ACTION_NEW:
        subscription, conflict = _create_new_subscription_for_payment(payment, user, plan)
    elif action == _MEMBERSHIP_ACTION_RENEW:
        subscription, conflict = _extend_subscription_for_payment(current, plan)

    if conflict:
        log_action(
            actor_user, "circle_payment.consumption_conflict", "CirclePayment", payment.id,
            changes={"reason": action},
        )
        return {"payment": payment, "outcome": "membership_conflict"}

    payment.subscription_id = subscription.id
    payment.status = "consumed"
    db.session.commit()

    event = (
        "circle_payment.consumed_new_membership" if action == _MEMBERSHIP_ACTION_NEW
        else "circle_payment.consumed_membership_extension"
    )
    log_action(actor_user, event, "CircleSubscription", subscription.id, changes={"paymentReference": payment.reference})
    return {"payment": payment, "outcome": "consumed"}


def get_payment_status(user, reference):
    """The one function GET /circle/payments/<reference> calls. Verifies
    with Paystack (throttled, see _verify_with_provider_if_due) only
    when the payment is still `pending`, then immediately consumes a
    freshly-matched verification within the same request — the browser
    never has to poll twice for an already-successful payment. Returns a
    small, normalized, safe dict — never a raw provider response.
    """
    payment = get_circle_payment_or_404(user, reference)
    reason = None

    if payment.status == "pending":
        payment, reason = _verify_with_provider_if_due(payment)

    if payment.status == "verified" and not _needs_reconciliation(payment):
        result = consume_verified_circle_payment(payment.reference, actor_user=user)
        payment = result["payment"]

    return {
        "reference": payment.reference,
        "status": payment.status,
        "membership_activated": payment.status == "consumed",
        "reconciliation_required": payment.status == "verified" and _needs_reconciliation(payment),
        "reason": reason,
    }
