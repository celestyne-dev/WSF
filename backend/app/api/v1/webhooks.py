"""Paystack webhook delivery handler — Module 3 of the Paystack Circle
integration, extended (Stage 1 of the premium-Resource integration) to
dispatch the SAME delivery to either CirclePayment or ResourcePayment
processing. Server-to-server only: there is no user/session
authentication here, no CSRF exemption to carve out (this codebase has
no CSRF-protection middleware at all — confirmed by grep; Flask-WTF/
CSRFProtect is never installed), and browser CORS is irrelevant (CORS
is a browser-enforced mechanism; Paystack's server never sends an
Origin header a browser would, and nothing here reads one). Paystack
authenticates itself purely via HMAC-SHA512 over the exact raw request
body (see app/services/paystack.py's verify_webhook_signature) — that
signature check happens before a single byte of the body is ever
parsed as JSON, let alone trusted.

This route is deliberately thin: a plain Flask view (not a Flask-
RESTful Resource — there is exactly one endpoint here, matching this
app's existing precedent for single bare routes like /api/v1/health,
/sitemap.xml, /robots.txt in app/__init__.py) that authenticates,
parses, filters to the one supported event, and then DISPATCHES the
reference to whichever payment domain actually owns it:

  - a CirclePayment row with this reference exists -> app/services/
    circle_payments.py's process_circle_webhook_charge_success()
    (unchanged — see that module's own docstring).
  - otherwise a ResourcePayment row with this reference exists ->
    app/services/resource_payments.py's
    process_resource_webhook_charge_success() (Stage 1 of the premium
    Resource integration — mirrors Circle's processing property-for-
    property, see that module's own docstring).
  - neither exists -> the existing safe "unknown reference" outcome,
    exactly as before Resource payments existed.

Dispatch is decided by an actual database lookup in EACH table, never
by the reference's own prefix (wsfcircle.../wsfresource...) alone — a
prefix is only a naming convention (see app/services/paystack.py's
generate_reference()), not proof a payment row exists; trusting it
alone would let a crafted reference with the "right" prefix probe for
outcomes without a backing row. Both processing functions return the
exact same outcome vocabulary (unknown_reference/already_consumed/
reconciliation_required/consumed/not_yet_confirmed, modulo Circle's
extra membership_conflict case — see resource_payments.py's module
docstring for why that one has no Resource equivalent), so this route's
own response-code policy below applies identically to either payment
domain; only the audit action-name prefix and AuditLog entity_type
differ, picked once dispatch has already been decided.

No rate limit is applied to this route: app/extensions.py's Limiter has
default_limits=[], so a route is only ever limited by an explicit
@limiter.limit(...) decorator, and this one deliberately has none — a
limit here could drop legitimate Paystack retries. Every checkout/
status endpoint for either payment domain keeps its own existing limits
untouched.

RESPONSE-CODE POLICY (identical for either payment domain):

  200 — valid signature + an event other than charge.success; valid
        signature + charge.success naming a reference WSF never issued
        in either table (logged, never created); an already-consumed
        replay; a successful verify+consume (including resuming a
        crash-interrupted clean `verified` payment) or
        verify+reconciliation outcome; a validly signed but unusable
        payload (not JSON, not an object, charge.success missing
        data.reference) — no retry could ever fix any of these.
  401 — missing, malformed, or incorrect x-paystack-signature. Never
        discloses which of the three it was.
  502 — a known payment, but fresh verification could NOT be performed
        successfully: Paystack API/network failure, timeout, or another
        provider-client exception — the Verify operation itself never
        completed. Paystack's own webhook retry schedule is relied on.
  503 — EITHER (a) Paystack disabled/unconfigured server-side; or (b)
        fresh verification completed successfully, but Paystack Verify
        currently reports a non-success transaction state despite the
        signed charge.success webhook ("not_yet_confirmed"). Nothing is
        activated/purchased and nothing already failed/abandoned is
        reopened until a later retry's Verify actually agrees.
  409 — a database conflict during processing, falling through to this
        app's existing global IntegrityError handler.
  (500 — any other unexpected internal failure falls through to this
        app's existing global error handler.)

No IP allowlisting is implemented or required here. HMAC verification
is this endpoint's one and only authentication mechanism.
"""
import json

from flask import Blueprint, request

from app.extensions import db
from app.models.circle import CirclePayment
from app.models.resource import ResourcePayment
from app.services.audit import log_action
from app.services.circle_payments import process_circle_webhook_charge_success
from app.services.paystack import PaystackAPIError, PaystackNotConfiguredError, verify_webhook_signature
from app.services.resource_payments import process_resource_webhook_charge_success

webhooks_bp = Blueprint("webhooks", __name__)

_SUPPORTED_EVENT = "charge.success"
# Defensive cap on what's ever written into an AuditLog.changes value
# for a reference taken from webhook input — references WSF itself
# generates are always far shorter than this; this only guards against
# an oversized value ever being logged verbatim.
_MAX_LOGGED_REFERENCE_LENGTH = 200

# Per payment domain: (process function, audit action-name prefix,
# AuditLog entity_type). Looked up once dispatch has been decided by an
# actual database row match (see module docstring) — never by reference
# prefix alone.
_DOMAINS = {
    "circle": (process_circle_webhook_charge_success, "circle_payment", "CirclePayment"),
    "resource": (process_resource_webhook_charge_success, "resource_payment", "ResourcePayment"),
}


def _reply(message, status):
    return {"message": message}, status


def _dispatch_domain(reference):
    """Decides which payment domain owns `reference`, by actual row
    existence in each table — never by the reference's own prefix alone
    (see module docstring). Returns a key into _DOMAINS, or None if
    neither table has a matching row.
    """
    if CirclePayment.query.filter_by(reference=reference).first() is not None:
        return "circle"
    if ResourcePayment.query.filter_by(reference=reference).first() is not None:
        return "resource"
    return None


@webhooks_bp.post("/paystack")
def paystack_webhook():
    # Read the exact raw bytes FIRST, before anything ever tries to
    # parse them as JSON — Paystack signs the literal bytes it sent, and
    # a signature must be checked against exactly those bytes, never a
    # re-serialized/normalized copy (see verify_webhook_signature's
    # docstring on why that distinction matters).
    raw_body = request.get_data(cache=True)
    supplied_signature = request.headers.get("x-paystack-signature")

    try:
        signature_valid = verify_webhook_signature(raw_body, supplied_signature)
    except PaystackNotConfiguredError:
        # A configuration problem, not a signature problem — must never
        # be reported as "invalid signature" (that would incorrectly
        # suggest a forged/corrupted delivery rather than "WSF isn't set
        # up for this yet").
        return _reply("Paystack is not configured.", 503)

    if not signature_valid:
        # One uniform response for every way a signature can fail
        # (missing header, malformed value, simply wrong) — never
        # discloses which.
        return _reply("Invalid signature.", 401)

    # Only now — signature already verified against the raw bytes above
    # — is the body ever parsed as JSON or trusted for anything.
    try:
        payload = json.loads(raw_body)
    except ValueError:
        # Validly signed but not valid JSON: no retry fixes a body that
        # was already signed this way, so there is nothing to gain by
        # asking Paystack to redeliver it.
        return _reply("ok", 200)

    if not isinstance(payload, dict):
        return _reply("ok", 200)

    event = payload.get("event")
    if event != _SUPPORTED_EVENT:
        # Any other validly-signed Paystack event (subscription/refund/
        # dispute/transfer/invoice/...) is out of scope — acknowledged,
        # never mutated, and deliberately not audit-logged (avoid noisy
        # records for the routine case of an event nothing here acts on).
        return _reply("ok", 200)

    data = payload.get("data")
    reference = data.get("reference") if isinstance(data, dict) else None
    if not reference or not isinstance(reference, str):
        # Validly signed charge.success with no usable reference — not
        # something a retry could fix either.
        log_action(None, "circle_payment.webhook_invalid_payload", "CirclePayment", None, changes={"event": event})
        return _reply("ok", 200)

    safe_reference = reference[:_MAX_LOGGED_REFERENCE_LENGTH]

    domain_key = _dispatch_domain(reference)
    if domain_key is None:
        # A correctly-signed charge.success naming a reference WSF never
        # issued in EITHER table isn't a WSF-side failure to retry — log
        # it for visibility and move on. Never create a CirclePayment/
        # CircleSubscription/ResourcePayment/ResourcePurchase, never
        # infer a user/plan/resource from webhook metadata.
        log_action(
            None, "circle_payment.webhook_unknown_reference", "CirclePayment", None,
            changes={"reference": safe_reference},
        )
        return _reply("ok", 200)

    process, action_prefix, entity_type = _DOMAINS[domain_key]

    try:
        result = process(reference)
    except (PaystackNotConfiguredError, PaystackAPIError) as exc:
        # A transient provider failure (or Paystack becoming disabled
        # mid-flight) — nothing has been falsely activated or falsely
        # marked failed; discard any uncommitted partial state from this
        # request and let Paystack's own retry schedule try again later.
        db.session.rollback()
        log_action(
            None, f"{action_prefix}.webhook_verification_unavailable", entity_type, None,
            changes={"reference": safe_reference, "reason": str(exc)},
        )
        return _reply("Verification temporarily unavailable.", 502)

    if result["outcome"] == "unknown_reference":
        # Defense in depth only — _dispatch_domain() already confirmed a
        # matching row exists moments ago; nothing in this app ever
        # deletes a payment row, so this branch is not expected to be
        # reachable in practice.
        log_action(
            None, f"{action_prefix}.webhook_unknown_reference", entity_type, None,
            changes={"reference": safe_reference},
        )
        return _reply("ok", 200)

    if result["outcome"] == "not_yet_confirmed":
        # Paystack's webhook claims charge.success, but the fresh Verify
        # call just performed completed successfully and reported a
        # non-success state instead (pending/processing, failed, or
        # abandoned). Never acknowledged as fully handled; the caller
        # must respond non-2xx so this delivery is retried once WSF can
        # independently confirm success.
        payment = result["payment"]
        log_action(
            None, f"{action_prefix}.webhook_not_yet_confirmed", entity_type,
            payment.id if payment else None, changes={"reference": safe_reference},
        )
        return _reply("Charge not yet independently confirmed. Please retry.", 503)

    return _reply("ok", 200)
