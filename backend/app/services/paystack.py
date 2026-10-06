"""Thin Paystack API client — transaction initialization and verification
only (see Module 1 of the approved Paystack Circle integration design).
No subscription/recurring-charge calls, no webhook processing — those are
explicitly out of scope here (webhook signature verification/handling is
reserved for a later module; see that module's own docstring once it
exists).

This module has no Flask-RESTful/HTTP-response awareness — it raises
PaystackError subclasses and lets callers translate those into whatever
API response shape they need, the same separation app/services/
user_admin.py's UserAdminError and app/services/search.py's
SearchValidationError use.

Nothing here makes an outbound request merely by being imported — every
request-making function calls `_secret_key()` first, which raises
PaystackNotConfiguredError if Paystack isn't enabled/configured, so the
app (and its test suite) can load this module freely with Paystack
disabled.

Module 3 adds one more thing this client is responsible for:
verify_webhook_signature() below, which authenticates an inbound
Paystack webhook delivery (HMAC-SHA512 over the exact raw request
body) — see that function's own docstring. It never makes an outbound
request itself; it is pure, stdlib-only signature verification, kept
here because it shares this module's one secret key and its "never
disclose the secret" discipline.
"""
import hashlib
import hmac
import secrets

import requests
from flask import current_app

# Fixed, not read from config/env: a configurable API host would let a
# misconfigured (or tampered) environment variable redirect every
# Paystack call to an arbitrary URL, carrying the secret key's
# Authorization header straight to it. Paystack's real API host never
# changes, so there is no legitimate reason to make it configurable.
PAYSTACK_API_BASE = "https://api.paystack.co"

# Conservative, fixed timeouts (connect, read) — Module 1 has no caller
# that should ever block indefinitely on a third-party API. A later
# module may decide requests-initializing endpoints need a different
# figure once real latency is observed; nothing here reads these from
# config, deliberately, to keep this module's behavior predictable in
# tests regardless of environment configuration.
_CONNECT_TIMEOUT = 5
_READ_TIMEOUT = 15

# Paystack documents transaction references as accepting only
# alphanumeric characters plus "-", ".", "=". Kept here (not duplicated
# ad hoc elsewhere) since it's exactly the charset generate_reference()
# below produces and the one later activation code must preserve.
REFERENCE_SAFE_CHARACTERS = "-.="


class PaystackError(Exception):
    """Base for every error this module raises. Never includes the
    secret key or raw request headers in its message — see the specific
    subclasses below for what each one does carry.
    """


class PaystackNotConfiguredError(PaystackError):
    """Raised when Paystack functionality is invoked while PAYSTACK_ENABLED
    is false or PAYSTACK_SECRET_KEY is unset — i.e. configuration, not a
    runtime/network problem. Callers should treat this as a 5xx "feature
    not available" condition, never surface it as if the customer's
    payment failed.
    """


class PaystackAPIError(PaystackError):
    """Raised for anything that went wrong actually talking to Paystack:
    a network/timeout failure, a non-success HTTP status, a malformed or
    unexpected JSON response shape. The message is always a safe, generic
    description (optionally including Paystack's own non-sensitive
    "message" field) — never the raw exception from `requests`, which
    could otherwise end up echoing request internals in a log or error
    response.
    """


def generate_reference(prefix="wsfcircle"):
    """A WSF-generated, globally-unique transaction reference, built from
    only the characters Paystack's reference field accepts (alphanumeric
    plus REFERENCE_SAFE_CHARACTERS). Called once per checkout attempt,
    before Paystack is ever contacted — this is the value stored as
    CirclePayment.reference and the one idempotency key the rest of the
    payment lifecycle keys off.
    """
    return f"{prefix}-{secrets.token_hex(16)}"


def _secret_key():
    config = current_app.config
    if not config.get("PAYSTACK_ENABLED"):
        raise PaystackNotConfiguredError("Paystack is not enabled (PAYSTACK_ENABLED is false).")
    secret = config.get("PAYSTACK_SECRET_KEY")
    if not secret:
        raise PaystackNotConfiguredError("PAYSTACK_SECRET_KEY is not configured.")
    return secret


def _request(method, path, secret, json_body=None):
    """Shared request/response handling for every call this module
    makes. Never lets a `requests` exception, a non-2xx status, or a
    malformed body propagate as-is — always normalizes to PaystackAPIError
    with a safe message first.
    """
    url = f"{PAYSTACK_API_BASE}{path}"
    headers = {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"}
    try:
        response = requests.request(
            method,
            url,
            json=json_body,
            headers=headers,
            timeout=(_CONNECT_TIMEOUT, _READ_TIMEOUT),
        )
    except requests.Timeout as exc:
        raise PaystackAPIError("Timed out contacting Paystack.") from exc
    except requests.RequestException as exc:
        raise PaystackAPIError("Could not reach Paystack.") from exc

    try:
        body = response.json()
    except ValueError as exc:
        raise PaystackAPIError("Paystack returned a response that was not valid JSON.") from exc

    if not isinstance(body, dict):
        raise PaystackAPIError("Paystack returned an unexpected response shape.")

    if not response.ok or body.get("status") is False:
        # Paystack's own "message" field is safe, customer/developer-
        # facing text (e.g. "Invalid key") — never the secret, never raw
        # request/response internals.
        message = body.get("message") or f"Paystack request failed (HTTP {response.status_code})."
        raise PaystackAPIError(message)

    return body


def initialize_transaction(*, amount_subunits, email, reference, currency, callback_url, metadata=None):
    """Calls POST /transaction/initialize. `amount_subunits` must already
    be the integer subunit amount (e.g. plan.price * 100) — this function
    does no currency conversion or unit math itself. `metadata`, if given,
    must already be a small, sanitized dict (e.g. {"plan_id": ..., "user_id":
    ...}) — this function does not sanitize it further.

    Returns {"authorization_url", "access_code", "reference"} normalized
    from Paystack's response. Raises PaystackAPIError if any of those
    three fields is missing — a response missing authorization_url is
    useless to the checkout flow and must never be treated as success.
    """
    secret = _secret_key()
    payload = {
        "amount": amount_subunits,
        "email": email,
        "reference": reference,
        "currency": currency,
        "callback_url": callback_url,
    }
    if metadata:
        payload["metadata"] = metadata

    body = _request("POST", "/transaction/initialize", secret, json_body=payload)
    data = body.get("data")
    if not isinstance(data, dict):
        raise PaystackAPIError("Paystack initialize response was missing its data object.")

    authorization_url = data.get("authorization_url")
    access_code = data.get("access_code")
    returned_reference = data.get("reference")
    if not authorization_url or not returned_reference:
        raise PaystackAPIError("Paystack initialize response was missing required fields.")

    return {
        "authorization_url": authorization_url,
        "access_code": access_code,
        "reference": returned_reference,
    }


def verify_transaction(reference):
    """Calls GET /transaction/verify/{reference}. Returns a normalized
    dict: {"status", "amount", "currency", "customer_email",
    "provider_transaction_id", "channel", "paid_at", "gateway_response",
    "reference"}.

    The returned `reference` is Paystack's own reported value for this
    transaction, read from the response body — callers must never assume
    it equals the `reference` argument just because that's the value
    used to build the request URL; a mismatch here is this function's
    caller's problem to detect, not this function's to paper over.

    `status` is Paystack's own raw transaction status string (e.g.
    "success"/"failed"/"abandoned") — this function does not map it onto
    CirclePayment's status values; that normalization belongs to the
    activation logic that will consume this (a later module), which also
    owns deciding what counts as a match against a CirclePayment's
    snapshot fields. This function's job stops at "safely getting
    Paystack's own facts out of its response."

    `provider_transaction_id` is returned as a string (Paystack's `id` is
    documented as needing to accommodate unsigned 64-bit values).
    """
    secret = _secret_key()
    body = _request("GET", f"/transaction/verify/{reference}", secret)
    data = body.get("data")
    if not isinstance(data, dict):
        raise PaystackAPIError("Paystack verify response was missing its data object.")

    status = data.get("status")
    amount = data.get("amount")
    reference = data.get("reference")
    if status is None or amount is None or reference is None:
        raise PaystackAPIError("Paystack verify response was missing required fields.")

    customer = data.get("customer") if isinstance(data.get("customer"), dict) else {}
    transaction_id = data.get("id")

    return {
        "status": status,
        "amount": amount,
        "currency": data.get("currency"),
        "customer_email": customer.get("email"),
        "provider_transaction_id": str(transaction_id) if transaction_id is not None else None,
        "channel": data.get("channel"),
        "paid_at": data.get("paid_at"),
        "gateway_response": data.get("gateway_response"),
        # Paystack's own reported reference for this transaction — callers
        # must compare this against the locally-stored CirclePayment
        # reference rather than assuming it matches the value that was
        # requested via /transaction/verify/<reference>.
        "reference": reference,
    }


def verify_webhook_signature(raw_body, supplied_signature):
    """Authenticates an inbound Paystack webhook delivery: Paystack signs
    every webhook POST body with HMAC-SHA512, keyed by the same secret
    key used for API calls, hex-encoded, and sent in the
    `x-paystack-signature` header. This is the ONLY authentication a
    webhook delivery has — there is no user/session, no API key header,
    nothing else to check — so callers must verify this (and only trust
    the parsed JSON) before doing anything else with the request.

    `raw_body` must be the exact, unmodified request bytes — Paystack
    signs the literal bytes it sent, not a re-serialized/re-parsed copy,
    so a semantically-identical but byte-different JSON body (different
    key order, different whitespace) will legitimately fail to validate
    against a signature computed for the original bytes. Callers must
    read `raw_body` before ever calling something like get_json() that
    might normalize it, and must never build the comparison from a
    dict that was already parsed and re-dumped.

    Raises PaystackNotConfiguredError if Paystack isn't enabled/
    configured — the same "this is a configuration problem, not a
    signature problem" signal every other function in this module
    raises for the identical condition; callers must treat that case as
    a safe 5xx failure, never as "the signature was invalid" (which
    would incorrectly suggest a forged/corrupted delivery).

    Returns True only for an exact, constant-time match against a
    non-empty, string `supplied_signature` — False for anything else
    (header missing entirely, non-hex garbage, right shape but wrong
    value). Never raises for a merely-invalid signature, and never
    includes the expected signature or the secret key in its return
    value, in any exception message, or anywhere else a caller might
    end up logging it — a caller must log only the fact that
    verification failed, never what was expected or supplied.
    """
    secret = _secret_key()
    if not isinstance(supplied_signature, str) or not supplied_signature:
        return False
    if not isinstance(raw_body, bytes):
        return False
    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, supplied_signature.strip().lower())
