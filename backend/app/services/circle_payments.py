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
    authorization_url. Any other recent `pending` row is, by definition,
    one whose Paystack initialize call never completed (e.g. the process
    died between the local insert and the provider response) — it can
    never become usable, so it's marked `failed` here rather than ever
    being handed back as a checkout destination, and a fresh attempt
    proceeds normally. Does not commit — the caller holds the advisory
    lock for the whole decision (see module docstring) and commits once.
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
    reusable = None
    for candidate in candidates:
        if candidate.authorization_url and reusable is None:
            reusable = candidate
        elif not candidate.authorization_url:
            candidate.status = "failed"
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


def _verify_with_provider_if_due(payment):
    """Locks the CirclePayment row, then — only if it's still `pending`
    and wasn't checked within _VERIFY_THROTTLE — calls Paystack's verify
    API exactly once and interprets the result:

    - provider "success" + every invariant matches -> `verified`
      (matched); the caller may proceed straight to consumption.
    - provider "success" + any invariant mismatch -> `verified` too, but
      flagged reconciliation_required in provider_snapshot and logged
      prominently; NEVER proceeds to consumption (see
      consume_verified_circle_payment). Paystack may genuinely have
      collected money here — this state exists so staff can investigate
      a real charge safely, not so it quietly disappears as a "failure".
    - provider "abandoned"/"failed" -> the matching local terminal
      status.
    - anything else (Paystack's own transaction is still
      pending/processing) -> left untouched; only the throttle timestamp
      advances.
    - a network/config error talking to Paystack -> left untouched
      (`pending`); never mistaken for a real failure.

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

    provider_status = result.get("status")

    if provider_status == "success":
        mismatches = _invariant_mismatches(locked, result)
        locked.status = "verified"
        locked.verified_at = now
        locked.paid_at = _parse_provider_timestamp(result.get("paid_at"))
        locked.provider_transaction_id = result.get("provider_transaction_id")
        locked.provider_channel = result.get("channel")
        locked.provider_snapshot = _build_provider_snapshot(result, mismatches)
        db.session.commit()
        if mismatches:
            log_action(
                locked.user, "circle_payment.verification_mismatch", "CirclePayment", locked.id,
                changes={"mismatches": sorted(mismatches)},
            )
            return locked, "reconciliation_required"
        log_action(locked.user, "circle_payment.verification_succeeded", "CirclePayment", locked.id)
        return locked, None

    if provider_status == "abandoned":
        locked.status = "abandoned"
        db.session.commit()
        log_action(locked.user, "circle_payment.verification_abandoned", "CirclePayment", locked.id)
        return locked, "abandoned"

    if provider_status == "failed":
        locked.status = "failed"
        db.session.commit()
        log_action(locked.user, "circle_payment.verification_failed", "CirclePayment", locked.id)
        return locked, "failed"

    # Paystack's own transaction is still pending/processing — WSF's
    # status is left exactly as-is so a later GET can try again.
    db.session.commit()
    return locked, "pending"


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
