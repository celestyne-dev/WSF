"""Paystack webhook delivery handler — Module 3 of the Paystack Circle
integration. Server-to-server only: there is no user/session
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
/sitemap.xml, /robots.txt in app/__init__.py) that does only four
things — authenticate, parse, filter to the one supported event, hand
the reference to app/services/circle_payments.py's
process_circle_webhook_charge_success(). That function is the one that
calls straight into consume_verified_circle_payment() — the SAME
activation core Module 2's checkout/status endpoints use. Nothing here
ever duplicates entitlement logic.

No rate limit is applied to this route: app/extensions.py's Limiter has
default_limits=[], so a route is only ever limited by an explicit
@limiter.limit(...) decorator, and this one deliberately has none — a
limit here could drop legitimate Paystack retries. POST /circle/plans/
<slug>/checkout and GET /circle/payments/<reference> keep their own
existing limits untouched.

RESPONSE-CODE POLICY:

  200 — valid signature + an event other than charge.success; valid
        signature + charge.success naming a reference WSF never issued
        (logged, never created); an already-consumed replay; a
        successful verify+consume (including resuming a crash-
        interrupted clean `verified` payment — see
        process_circle_webhook_charge_success's own docstring) or
        verify+reconciliation outcome; a validly signed but unusable
        payload (not JSON, not an object, charge.success missing
        data.reference) — no retry could ever fix any of these, so
        there's nothing to gain by asking Paystack to retry.
  401 — missing, malformed, or incorrect x-paystack-signature. Never
        discloses which of the three it was.
  502 — a known payment, but fresh verification could NOT be performed
        successfully: Paystack API/network failure, timeout, or another
        provider-client exception — the Verify operation itself never
        completed. A transient failure, not an authoritative answer;
        Paystack's own webhook retry schedule is relied on to try again
        later.
  503 — EITHER of two distinct "temporary, try again later" cases,
        deliberately not 409 (this is not a request/resource conflict):
        (a) Paystack disabled/unconfigured server-side; or (b) fresh
        verification completed successfully, but Paystack Verify
        currently reports a non-success transaction state (pending/
        processing, failed, or abandoned) despite the signed
        charge.success webhook — see
        process_circle_webhook_charge_success's "not_yet_confirmed"
        outcome. Nothing is activated and nothing already failed/
        abandoned is reopened until a later retry's Verify actually
        agrees.
  409 — a database conflict during processing, which falls through to
        this app's existing global IntegrityError handler in
        app/utils/responses.py.
  (500 — any other unexpected internal failure during processing falls
        through to this app's existing global error handler, which
        already returns a safe, generic non-2xx body — nothing
        webhook-specific is needed here.)

No IP allowlisting is implemented or required here (see task spec:
"Do NOT make Paystack IP allowlisting mandatory in this module" — the
nginx/proxy source-IP forwarding setup hasn't been audited). HMAC
verification is this endpoint's one and only authentication mechanism.
"""
import json

from flask import Blueprint, request

from app.extensions import db
from app.services.audit import log_action
from app.services.circle_payments import process_circle_webhook_charge_success
from app.services.paystack import PaystackAPIError, PaystackNotConfiguredError, verify_webhook_signature

webhooks_bp = Blueprint("webhooks", __name__)

_SUPPORTED_EVENT = "charge.success"
# Defensive cap on what's ever written into an AuditLog.changes value
# for a reference taken from webhook input — references WSF itself
# generates are always far shorter than this; this only guards against
# an oversized value ever being logged verbatim.
_MAX_LOGGED_REFERENCE_LENGTH = 200


def _reply(message, status):
    return {"message": message}, status


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
        # dispute/transfer/invoice/...) is out of scope for Module 3 —
        # acknowledged, never mutated, and deliberately not audit-logged
        # (see module docstring: avoid noisy records for the routine
        # case of an event this module doesn't act on).
        return _reply("ok", 200)

    data = payload.get("data")
    reference = data.get("reference") if isinstance(data, dict) else None
    if not reference or not isinstance(reference, str):
        # Validly signed charge.success with no usable reference — not
        # something a retry could fix either.
        log_action(None, "circle_payment.webhook_invalid_payload", "CirclePayment", None, changes={"event": event})
        return _reply("ok", 200)

    safe_reference = reference[:_MAX_LOGGED_REFERENCE_LENGTH]

    try:
        result = process_circle_webhook_charge_success(reference)
    except (PaystackNotConfiguredError, PaystackAPIError) as exc:
        # A transient provider failure (or Paystack becoming disabled
        # mid-flight) — nothing has been falsely activated or falsely
        # marked failed; discard any uncommitted partial state from this
        # request and let Paystack's own retry schedule try again later.
        db.session.rollback()
        log_action(
            None, "circle_payment.webhook_verification_unavailable", "CirclePayment", None,
            changes={"reference": safe_reference, "reason": str(exc)},
        )
        return _reply("Verification temporarily unavailable.", 502)

    if result["outcome"] == "unknown_reference":
        # A correctly-signed charge.success naming a reference WSF never
        # issued isn't a WSF-side failure to retry — log it for
        # visibility and move on. Never create a CirclePayment/
        # CircleSubscription, never infer a user/plan from metadata.
        log_action(
            None, "circle_payment.webhook_unknown_reference", "CirclePayment", None,
            changes={"reference": safe_reference},
        )
        return _reply("ok", 200)

    if result["outcome"] == "not_yet_confirmed":
        # Paystack's webhook claims charge.success, but the fresh Verify
        # call just performed completed successfully and reported a
        # non-success state instead (pending/processing, failed, or
        # abandoned). WSF never acknowledges that inconsistency as
        # fully handled — nothing was activated, and nothing already
        # failed/abandoned was reopened — so this responds 503 (a
        # temporary condition, not a request conflict) and relies on
        # Paystack's own retry schedule; a later retry whose fresh
        # Verify does return "success" will consume normally.
        payment = result["payment"]
        log_action(
            None, "circle_payment.webhook_not_yet_confirmed", "CirclePayment",
            payment.id if payment else None, changes={"reference": safe_reference},
        )
        return _reply("Charge not yet independently confirmed. Please retry.", 503)

    return _reply("ok", 200)
