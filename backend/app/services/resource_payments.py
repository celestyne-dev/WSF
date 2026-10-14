"""Stage 1 of the premium-Resource Paystack integration: the security-
critical server-side core — initialize checkout, verify with Paystack,
and idempotently create the resulting ResourcePurchase entitlement. See
app/services/paystack.py (the thin Paystack API client, reused as-is —
nothing here duplicates its HTTP/HMAC logic) and app/models/resource.py's
ResourcePayment/ResourcePurchase for the schema this builds on.

This module deliberately mirrors app/services/circle_payments.py
property-for-property — same snapshot discipline, same idempotency
pattern, same webhook-recovery policy — because premium Resource
purchase and WSF Circle membership are commercially separate but share
the exact same payment-safety requirements. See that module's own
docstring for the full rationale behind each design choice reused here;
this docstring only calls out what's actually different for a one-time
purchase rather than a recurring membership period.

WHAT'S DIFFERENT FROM CIRCLE:

- A premium Resource purchase has no "renew"/"extend" concept — it's a
  single durable entitlement per (user, resource). Checkout eligibility
  is simply "does this user already hold an active ResourcePurchase for
  this Resource" (already_purchased) rather than Circle's richer
  new/renew/blocked_* classification.
- An active WSF Circle member gets premium Resource access for free via
  has_circle_access(user) (see app/services/resource_access.py) WITHOUT
  ever holding a ResourcePurchase — Circle access is temporary and
  membership-based, never converted into this module's durable
  entitlement. start_resource_checkout() below rejects a Circle member's
  checkout attempt (code "included_with_circle") before creating any
  ResourcePayment row or calling Paystack at all, which Circle's own
  checkout has no equivalent of — see that function's own comment.
- consume_verified_resource_payment() therefore has a simpler outcome
  vocabulary than consume_verified_circle_payment(): there is no
  "membership_conflict" — if a ResourcePurchase for this (user, resource)
  already exists by the time a payment is ready to consume (a legitimate
  idempotent replay, or a narrow race between two payments that somehow
  both got this far), this payment is simply attached to that one
  existing purchase and marked consumed; a brand-new purchase is created
  only when none exists yet. Either way, exactly one ResourcePurchase
  ever exists per (user, resource) — enforced in the database by
  ResourcePurchase's own unique (user_id, resource_id) index, not just in
  this module's own logic.

LOCKING: same two distinct mechanisms Circle uses, for the same two races.

1. Checkout initiation (start_resource_checkout) takes a Postgres
   transaction-scoped advisory lock keyed on (user_id, -resource_id) —
   `pg_advisory_xact_lock(user_id, -resource_id)` — held for the entire
   initiation, including the outbound Paystack call. The negated second
   key is deliberate: Circle's own checkout lock
   (app/services/circle_payments.py's start_circle_checkout) locks on
   (user_id, plan_id), and plan_id/resource_id are both ordinary positive
   serial primary keys from unrelated tables that could coincidentally
   be equal for the same user — negating resource_id guarantees this
   lock's key space can never collide with Circle's, since a plan_id is
   never negative. See start_circle_checkout's own docstring for why the
   lock is held across the network call rather than released beforehand.
2. Verification/consumption (consume_verified_resource_payment,
   _verify_with_provider_if_due) use ordinary row-level locking
   (`SELECT ... FOR UPDATE`) on the ResourcePayment row itself, exactly
   like Circle's identical pattern.

WEBHOOK RECOVERY: api/v1/webhooks.py's Paystack route is the ONLY caller
of _verify_with_provider_for_webhook/process_resource_webhook_charge_success
below, and only after it has already verified the delivery's HMAC
signature, confirmed the event is `charge.success`, and determined (by
DB lookup, never by reference-prefix alone) that this reference belongs
to a ResourcePayment rather than a CirclePayment. See that module's own
docstring for the full dispatch policy.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.resource import Resource, ResourcePayment, ResourcePurchase
from app.services.audit import log_action
from app.services.paystack import (
    PaystackAPIError,
    PaystackNotConfiguredError,
    generate_reference,
    initialize_transaction,
    verify_transaction,
)
from app.services.circle import has_circle_access
from app.services.resource_downloads import protected_file_exists
from app.utils.responses import ApiError

# A near-duplicate "Buy now" click within this window, for the same user
# and resource, reuses the still-usable pending checkout instead of
# starting a second Paystack transaction. Same window Circle uses — a
# double-click/retry guard, not a general-purpose cache.
_PENDING_REUSE_WINDOW = timedelta(minutes=10)

# How often a `pending` ResourcePayment's status may be re-checked
# against Paystack — bounds repeated browser refreshes/polling to far
# short of "every request hits Paystack". Same value Circle uses.
_VERIFY_THROTTLE = timedelta(seconds=5)

# Small, explicitly allowlisted subset of verify_transaction()'s result
# kept in ResourcePayment.provider_snapshot — see app/services/
# circle_payments.py's identical constant for why nothing broader is
# ever persisted, and why "customer_email" is deliberately excluded here
# too (only ever compared in memory, never written to storage).
_SNAPSHOT_FIELDS = ("status", "amount", "currency", "channel", "paid_at", "gateway_response")


def ensure_paystack_configured():
    """Same configuration-only check app/services/paystack.py's own
    _secret_key() performs right before actually calling Paystack — this
    one exists so a disabled/unconfigured integration fails with a clear,
    stable application error before any ResourcePayment row is created.
    """
    if not current_app.config.get("PAYSTACK_ENABLED"):
        raise ApiError("Online resource purchases aren't enabled yet.", 503, code="paystack_disabled")
    if not current_app.config.get("PAYSTACK_SECRET_KEY"):
        raise ApiError("Online resource purchases aren't configured yet.", 503, code="paystack_not_configured")


def ensure_resource_payable(resource):
    """Resource-side eligibility only — "already purchased" is checked
    separately by the caller (start_resource_checkout), since that's a
    user-specific fact, not a property of the Resource itself. No
    currency conversion is ever performed: a Resource priced outside
    PAYSTACK_ALLOWED_CURRENCIES is simply not payable online yet (see
    config.py's own docstring on that setting).
    """
    if resource.access_type != "premium":
        raise ApiError("This resource is not a premium purchase.", 422, code="not_premium")
    if not resource.is_publicly_visible():
        raise ApiError("This resource isn't currently available.", 404, code="not_found")
    if resource.price <= 0:
        raise ApiError("This resource cannot be purchased online.", 422, code="resource_not_payable")
    if not resource.protected_file_path or not protected_file_exists(resource.protected_file_path):
        raise ApiError(
            "This resource isn't ready for purchase yet. Please contact WSF.", 422, code="resource_not_payable"
        )
    allowed_currencies = {c.strip().upper() for c in (current_app.config.get("PAYSTACK_ALLOWED_CURRENCIES") or [])}
    if resource.currency.strip().upper() not in allowed_currencies:
        raise ApiError(
            "This resource's currency isn't enabled for online payment yet.", 422, code="currency_not_supported"
        )


def _already_purchased(user, resource):
    return (
        ResourcePurchase.query.filter_by(user_id=user.id, resource_id=resource.id, status="active").first()
        is not None
    )


def _build_callback_url():
    """Distinct from Circle's own /circle/checkout/callback — see spec
    section 12. No frontend route exists at this path yet (Stage 1 is
    backend-only); Paystack is still given this URL at initialization
    time since Stage 2 will add the matching frontend page before this
    checkout is ever exposed to a real user.
    """
    base = (current_app.config.get("FRONTEND_URL") or "").rstrip("/")
    return f"{base}/resources/checkout/callback"


def _find_reusable_pending_resource_payment(user, resource):
    """Within _PENDING_REUSE_WINDOW, for this exact user+resource: reuse
    the most recent `pending` row that actually has a usable
    authorization_url AND whose snapshotted amount/currency still match
    the resource's CURRENT price/currency. Mirrors app/services/
    circle_payments.py's _find_reusable_pending_payment exactly — see
    that function's own docstring for the full reasoning. Does not
    commit — the caller holds the advisory lock for the whole decision
    and commits once.
    """
    window_start = datetime.now(timezone.utc) - _PENDING_REUSE_WINDOW
    candidates = (
        ResourcePayment.query.filter(
            ResourcePayment.user_id == user.id,
            ResourcePayment.resource_id == resource.id,
            ResourcePayment.status == "pending",
            ResourcePayment.created_at >= window_start,
        )
        .order_by(ResourcePayment.created_at.desc())
        .all()
    )
    expected_amount_subunits = resource.price * 100
    expected_currency = resource.currency.strip().upper()
    reusable = None
    for candidate in candidates:
        if not candidate.authorization_url:
            candidate.status = "failed"
            continue
        matches_current_terms = (
            candidate.amount_subunits == expected_amount_subunits
            and candidate.currency.strip().upper() == expected_currency
        )
        if not matches_current_terms:
            candidate.status = "failed"
            continue
        if reusable is None:
            reusable = candidate
    return reusable


def start_resource_checkout(user, resource):
    """The one entry point for "Buy now" (not yet wired to any frontend —
    Stage 1 is backend-only). Takes only `user` (authenticated session)
    and `resource` (looked up server-side from the URL slug by the
    caller) — nothing about amount, currency, or whose account this is
    for ever comes from the request body; see ResourcePayment's own
    docstring for why those are always snapshotted from the database at
    this exact moment instead.

    Returns {"reference": str, "authorization_url": str}. Raises
    ApiError for every rejection path (resource ineligibility, already
    purchased, Paystack disabled/unconfigured, or a genuine Paystack
    initialize failure) — never silently returns a broken checkout.
    """
    ensure_paystack_configured()
    ensure_resource_payable(resource)

    if _already_purchased(user, resource):
        raise ApiError("You already own this resource.", 409, code="already_purchased")

    # An active WSF Circle member already has complimentary access to
    # every premium Resource (see app/services/resource_access.py's
    # check_resource_access) — checked AFTER already_purchased so a
    # purchaser-who-also-has-Circle still gets the (harmless, no-op)
    # already_purchased response rather than this one. Rejected here,
    # before any ResourcePayment row exists and before Paystack is ever
    # called, so a stale "Buy" button, a duplicate tab, or membership
    # becoming active while this page was open can never actually charge
    # a Circle member or create a payment row for them.
    if has_circle_access(user):
        raise ApiError(
            "This resource is included with your active WSF Circle membership.",
            409,
            code="included_with_circle",
        )

    # See module docstring: this advisory lock is held across the
    # Paystack call on purpose, not released beforehand. -resource.id
    # keeps this lock's key space disjoint from Circle's own
    # (user_id, plan_id) advisory lock.
    db.session.execute(
        text("SELECT pg_advisory_xact_lock(:user_id, :resource_key)"),
        {"user_id": user.id, "resource_key": -resource.id},
    )

    # Re-check under the lock: a concurrent request could have completed
    # a purchase for this exact user+resource between the unlocked check
    # above and acquiring the lock just now.
    if _already_purchased(user, resource):
        db.session.commit()
        raise ApiError("You already own this resource.", 409, code="already_purchased")

    reused = _find_reusable_pending_resource_payment(user, resource)
    if reused is not None:
        db.session.commit()
        log_action(
            user, "resource_payment.checkout_initialized", "ResourcePayment", reused.id,
            changes={"resourceSlug": resource.slug, "reused": True},
        )
        return {"reference": reused.reference, "authorization_url": reused.authorization_url}

    reference = generate_reference(prefix="wsfresource")
    amount_subunits = resource.price * 100
    customer_email = user.email.strip().lower()
    payment = ResourcePayment(
        reference=reference,
        user_id=user.id,
        resource_id=resource.id,
        amount_subunits=amount_subunits,
        currency=resource.currency,
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
            currency=resource.currency,
            callback_url=_build_callback_url(),
            metadata={"resource_id": resource.id, "user_id": user.id},
        )
    except (PaystackNotConfiguredError, PaystackAPIError) as exc:
        payment.status = "failed"
        db.session.commit()
        log_action(
            user, "resource_payment.initialization_failed", "ResourcePayment", payment.id,
            changes={"resourceSlug": resource.slug, "reason": str(exc)},
        )
        raise ApiError(
            "We couldn't start a secure checkout right now. Please try again shortly.",
            502, code="payment_initialization_failed",
        )

    if result.get("reference") != payment.reference:
        # Nothing has been verified as paid at this point — same
        # initialization-failure path Circle's start_circle_checkout
        # takes for this identical condition (see its own docstring).
        payment.status = "failed"
        db.session.commit()
        log_action(
            user, "resource_payment.initialization_failed", "ResourcePayment", payment.id,
            changes={"resourceSlug": resource.slug, "reason": "provider_reference_mismatch"},
        )
        raise ApiError(
            "We couldn't start a secure checkout right now. Please try again shortly.",
            502, code="payment_initialization_failed",
        )

    payment.authorization_url = result["authorization_url"]
    db.session.commit()
    log_action(
        user, "resource_payment.checkout_initialized", "ResourcePayment", payment.id,
        changes={"resourceSlug": resource.slug, "reused": False},
    )
    return {"reference": payment.reference, "authorization_url": payment.authorization_url}


def get_resource_payment_or_404(user, reference):
    """Same 404 regardless of whether `reference` doesn't exist at all or
    belongs to someone else — a probing request must never be able to
    tell those two cases apart. Mirrors app/services/circle_payments.py's
    get_circle_payment_or_404 exactly.
    """
    payment = ResourcePayment.query.filter_by(reference=reference).first()
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
    """Compares Paystack's verify response against ResourcePayment's own
    snapshots (never against Resource's current, possibly-since-edited
    fields). Same comparison rules as app/services/circle_payments.py's
    identical function: integer equality for amount, no floats anywhere;
    email compared case-insensitively after stripping; reference compared
    with exact, non-normalized string equality.
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
    from an already-fetched Paystack verify `result`. Identical mapping
    to app/services/circle_payments.py's function of the same name — see
    that module's docstring for the full success/abandoned/failed/pending
    interpretation. Does not commit, and does not touch
    last_verification_attempt_at — callers own both.

    Returns (reason, mismatches): `reason` is None (clean success),
    "reconciliation_required", "abandoned", "failed", or "pending".
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

    return "pending", []


def _verify_with_provider_if_due(payment):
    """Locks the ResourcePayment row, then — only if it's still `pending`
    and wasn't checked within _VERIFY_THROTTLE — calls Paystack's verify
    API exactly once. Mirrors app/services/circle_payments.py's identical
    function; see that module's docstring for why populate_existing() is
    required here, not optional.
    """
    locked = ResourcePayment.query.with_for_update().populate_existing().filter_by(id=payment.id).one()
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
            locked.user, "resource_payment.verification_unavailable", "ResourcePayment", locked.id,
            changes={"reason": str(exc)},
        )
        return locked, "verification_unavailable"

    reason, mismatches = _apply_provider_verify_result(locked, result, now)
    db.session.commit()

    if reason == "reconciliation_required":
        log_action(
            locked.user, "resource_payment.verification_mismatch", "ResourcePayment", locked.id,
            changes={"mismatches": sorted(mismatches)},
        )
        return locked, reason
    if reason is None:
        log_action(locked.user, "resource_payment.verification_succeeded", "ResourcePayment", locked.id)
        return locked, None
    if reason == "abandoned":
        log_action(locked.user, "resource_payment.verification_abandoned", "ResourcePayment", locked.id)
        return locked, reason
    if reason == "failed":
        log_action(locked.user, "resource_payment.verification_failed", "ResourcePayment", locked.id)
        return locked, reason
    return locked, reason  # "pending"


def _verify_with_provider_for_webhook(payment):
    """Trusted-webhook-only verification/recovery entry point — identical
    policy to app/services/circle_payments.py's function of the same
    name; see that module's WEBHOOK RECOVERY docstring section for the
    full reasoning, including why callers must branch on the RETURNED
    `status`/`reason`, never on `locked.status` read again afterwards.

    Raises PaystackAPIError/PaystackNotConfiguredError straight through
    on a transient provider failure — nothing is mutated or committed on
    that path.
    """
    locked = ResourcePayment.query.with_for_update().populate_existing().filter_by(id=payment.id).one()
    prior_status = locked.status

    if prior_status == "consumed":
        return locked, "already_consumed", prior_status

    if prior_status == "verified":
        reason = "reconciliation_required" if _needs_reconciliation(locked) else None
        return locked, reason, prior_status

    now = datetime.now(timezone.utc)
    locked.last_verification_attempt_at = now
    result = verify_transaction(locked.reference)  # may raise — nothing committed yet, see docstring
    reason, mismatches = _apply_provider_verify_result(locked, result, now)
    status = locked.status
    db.session.commit()

    if reason == "reconciliation_required":
        log_action(
            None, "resource_payment.webhook_reconciliation", "ResourcePayment", locked.id,
            changes={"mismatches": sorted(mismatches), "priorStatus": prior_status},
        )
    elif reason is None and prior_status in ("failed", "abandoned"):
        log_action(
            None, "resource_payment.webhook_recovered", "ResourcePayment", locked.id,
            changes={"from": prior_status},
        )

    return locked, reason, status


def process_resource_webhook_charge_success(reference):
    """THE one entry point api/v1/webhooks.py's Paystack route calls for
    an HMAC-verified `charge.success` event that a DB lookup has already
    matched to a ResourcePayment (never by reference-prefix alone — see
    that module's own docstring). Defers to the exact same
    consume_verified_resource_payment() every other entry point uses.

    Returns {"outcome": str, "payment": ResourcePayment | None} where
    outcome is one of: "unknown_reference", "already_consumed",
    "reconciliation_required", "consumed", "not_yet_confirmed" — the same
    vocabulary app/services/circle_payments.py's
    process_circle_webhook_charge_success returns (minus
    "membership_conflict", which has no equivalent for a one-time
    purchase — see module docstring).
    """
    payment = ResourcePayment.query.filter_by(reference=reference).one_or_none()
    if payment is None:
        return {"outcome": "unknown_reference", "payment": None}

    locked, reason, status = _verify_with_provider_for_webhook(payment)

    if reason == "already_consumed":
        log_action(None, "resource_payment.webhook_replay", "ResourcePayment", locked.id)
        return {"outcome": "already_consumed", "payment": locked}

    if status == "verified" and reason != "reconciliation_required":
        result = consume_verified_resource_payment(locked.reference, actor_user=None)
        return {"outcome": result["outcome"], "payment": result["payment"]}

    if status == "verified":
        return {"outcome": "reconciliation_required", "payment": locked}

    return {"outcome": "not_yet_confirmed", "payment": locked}


def _attach_or_create_purchase(payment, user, resource):
    """The one place a ResourcePurchase row is ever created for a
    verified ResourcePayment. If a purchase for this exact (user,
    resource) already exists — a legitimate idempotent replay, or a
    narrow race between two payments that both reached this point before
    either committed — this payment is attached to that SAME existing
    purchase rather than ever creating a second one; ResourcePurchase's
    own unique (user_id, resource_id) index is the final backstop against
    a race this function's own pre-check might still miss. Returns the
    ResourcePurchase (new or existing) — never raises for the "already
    exists" case, since that is never a conflict for a one-time purchase
    (see module docstring for why this has no Circle-style
    "membership_conflict" outcome).
    """
    existing = ResourcePurchase.query.filter_by(user_id=user.id, resource_id=resource.id).first()
    if existing is not None:
        return existing

    purchase = ResourcePurchase(
        user_id=user.id,
        resource_id=resource.id,
        payment_reference=payment.reference,
        status="active",
    )
    db.session.add(purchase)
    try:
        db.session.flush()
    except IntegrityError:
        # Another payment won the race and committed first — roll back
        # this insert attempt and attach to whichever purchase now exists
        # instead of ever creating a second one.
        db.session.rollback()
        return ResourcePurchase.query.filter_by(user_id=user.id, resource_id=resource.id).one()
    return purchase


def consume_verified_resource_payment(reference, actor_user=None):
    """THE one place a verified ResourcePayment is turned into premium
    Resource access — the exact function the webhook handler calls too,
    never a second copy of this logic. Transaction-safe and idempotent:
    locks the ResourcePayment row first, so two simultaneous verification
    requests, a webhook racing a browser's own status poll, or a plain
    retry can never create more than one ResourcePurchase for one
    ResourcePayment. `reference` remains the one idempotency key.

    Returns {"payment": ResourcePayment, "outcome": str} where outcome is
    one of:

    - "already_consumed": no-op — this exact payment was consumed
      before; no second purchase, no duplicate audit side effects.
    - "not_ready": the payment isn't `verified` yet (still pending, or
      verified-but-flagged-for-reconciliation) — nothing is mutated.
    - "consumed": a ResourcePurchase was created (or an existing one,
      from a legitimate idempotent replay/race, was attached instead —
      see _attach_or_create_purchase), and this ResourcePayment now
      points at it.
    """
    payment = ResourcePayment.query.with_for_update().populate_existing().filter_by(reference=reference).one_or_none()
    if payment is None:
        raise ApiError("Unknown payment reference.", 404, code="not_found")

    if payment.status == "consumed":
        return {"payment": payment, "outcome": "already_consumed"}

    if payment.status != "verified" or _needs_reconciliation(payment):
        return {"payment": payment, "outcome": "not_ready"}

    user = payment.user
    resource = payment.resource
    purchase = _attach_or_create_purchase(payment, user, resource)

    payment.purchase_id = purchase.id
    payment.status = "consumed"
    db.session.commit()

    log_action(
        actor_user, "resource_payment.consumed", "ResourcePurchase", purchase.id,
        changes={"paymentReference": payment.reference, "resourceSlug": resource.slug},
    )
    return {"payment": payment, "outcome": "consumed"}


def get_resource_payment_status(user, reference):
    """The one function GET /resources/payments/<reference> calls.
    Verifies with Paystack (throttled, see _verify_with_provider_if_due)
    only when the payment is still `pending`, then immediately consumes a
    freshly-matched verification within the same request. Returns a
    small, normalized, safe dict — never a raw provider response, never
    the customer email/provider transaction id/internal ids.
    """
    payment = get_resource_payment_or_404(user, reference)
    reason = None

    if payment.status == "pending":
        payment, reason = _verify_with_provider_if_due(payment)

    if payment.status == "verified" and not _needs_reconciliation(payment):
        result = consume_verified_resource_payment(payment.reference, actor_user=user)
        payment = result["payment"]

    resource = db.session.get(Resource, payment.resource_id)
    return {
        "reference": payment.reference,
        "status": payment.status,
        "purchase_activated": payment.status == "consumed",
        "reconciliation_required": payment.status == "verified" and _needs_reconciliation(payment),
        "reason": reason,
        "resource_slug": resource.slug if resource else None,
    }
