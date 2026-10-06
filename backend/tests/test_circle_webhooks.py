"""Module 3 of the Paystack Circle integration: the webhook delivery
handler (POST /api/v1/webhooks/paystack). Every test here signs its own
raw request body with the exact same HMAC-SHA512 scheme Paystack uses
and posts it straight to the Flask test client — nothing makes a real
Paystack call, and nothing uses a real secret key. See
app/api/v1/webhooks.py and app/services/circle_payments.py's
process_circle_webhook_charge_success for the implementation this
exercises.
"""
import hashlib
import hmac
import json
import threading
import uuid
from unittest.mock import patch

import pytest

from app.extensions import db
from tests.conftest import auth_headers

USER1 = {
    "email": "circlewebhook-user1@example.com", "password": "supersecret1",
    "first_name": "Folake", "last_name": "Adeyemi", "country_code": "NG",
}

_WEBHOOK_SECRET = "sk_test_webhooksecret"
_WEBHOOK_URL = "/api/v1/webhooks/paystack"


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user1_token(client):
    return _register(client, USER1)


def _get_user(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first()


def _enable_paystack(app, secret=_WEBHOOK_SECRET, currencies=("USD",)):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = secret
    app.config["PAYSTACK_ALLOWED_CURRENCIES"] = list(currencies)


def _make_plan(app, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePlan

    defaults = dict(
        slug=overrides.pop("slug", None) or f"plan-{uuid.uuid4().hex[:10]}",
        name="WSF Circle Membership",
        billing_interval="monthly",
        price=1000,
        currency="USD",
        status="active",
    )
    defaults.update(overrides)
    with app.app_context():
        plan = CirclePlan(**defaults)
        db.session.add(plan)
        db.session.commit()
        return plan.id, plan.slug


def _make_subscription(app, user_id, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    defaults = dict(user_id=user_id, plan_id=plan_id, status="active", source="manual")
    defaults.update(overrides)
    with app.app_context():
        subscription = CircleSubscription(**defaults)
        db.session.add(subscription)
        db.session.commit()
        return subscription.id


def _make_payment(app, user_id, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePayment

    defaults = dict(
        reference=overrides.pop("reference", None) or f"wsfcircle-{uuid.uuid4().hex}",
        user_id=user_id,
        plan_id=plan_id,
        amount_subunits=100000,
        currency="USD",
        billing_interval="monthly",
        customer_email=USER1["email"],
        status="pending",
    )
    defaults.update(overrides)
    with app.app_context():
        payment = CirclePayment(**defaults)
        db.session.add(payment)
        db.session.commit()
        return payment.id, payment.reference


def _get_payment(app, reference):
    from app.models.circle import CirclePayment

    with app.app_context():
        return CirclePayment.query.filter_by(reference=reference).first()


def _count_subscriptions(app, user_id):
    from app.models.circle import CircleSubscription

    with app.app_context():
        return CircleSubscription.query.filter_by(user_id=user_id).count()


def _count_payments_for_reference(app, reference):
    from app.models.circle import CirclePayment

    with app.app_context():
        return CirclePayment.query.filter_by(reference=reference).count()


def _count_audit(app, action, entity_id=None):
    from app.models.audit import AuditLog

    with app.app_context():
        query = AuditLog.query.filter_by(action=action)
        if entity_id is not None:
            query = query.filter_by(entity_id=str(entity_id))
        return query.count()


def _has_access(app, user_id):
    from app.models.user import User
    from app.services.circle import has_circle_access

    with app.app_context():
        from app.extensions import db

        user = db.session.get(User, user_id)
        return has_circle_access(user)


def _sign(secret, raw_body):
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha512).hexdigest()


def _charge_success_body(reference, **extra):
    data = {"reference": reference}
    data.update(extra)
    return json.dumps({"event": "charge.success", "data": data}).encode()


def _post_signed(client, body, secret=_WEBHOOK_SECRET):
    signature = _sign(secret, body)
    return client.post(_WEBHOOK_URL, data=body, headers={
        "Content-Type": "application/json", "x-paystack-signature": signature,
    })


def _post_unsigned(client, body, signature):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["x-paystack-signature"] = signature
    return client.post(_WEBHOOK_URL, data=body, headers=headers)


def _success_result(payment, **overrides):
    result = {
        "status": "success",
        "amount": payment.amount_subunits,
        "currency": payment.currency,
        "customer_email": payment.customer_email,
        "provider_transaction_id": "123456789",
        "channel": "card",
        "paid_at": "2026-10-05T12:00:00.000Z",
        "gateway_response": "Successful",
        "reference": payment.reference,
    }
    result.update(overrides)
    return result


class TestWebhookSignatureEnforcement:
    """Routing-level signature enforcement — the actual HMAC math is
    covered exhaustively in test_paystack_client.py; this class proves
    the Flask route wires it up correctly.
    """

    def test_valid_signature_with_unknown_reference_returns_200(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body("does-not-exist-anywhere")
        resp = _post_signed(client, body)
        assert resp.status_code == 200

    def test_missing_signature_rejected(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body("whatever")
        resp = _post_unsigned(client, body, None)
        assert resp.status_code == 401

    def test_invalid_signature_rejected(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body("whatever")
        resp = _post_unsigned(client, body, "0" * 128)
        assert resp.status_code == 401

    def test_signature_for_different_body_rejected(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body("ref-a")
        other_body = _charge_success_body("ref-b")
        signature_for_other_body = _sign(_WEBHOOK_SECRET, other_body)
        resp = _post_unsigned(client, body, signature_for_other_body)
        assert resp.status_code == 401

    def test_disabled_paystack_fails_safely(self, client, app):
        app.config["PAYSTACK_ENABLED"] = False
        app.config["PAYSTACK_SECRET_KEY"] = _WEBHOOK_SECRET
        body = _charge_success_body("whatever")
        signature = _sign(_WEBHOOK_SECRET, body)
        resp = client.post(_WEBHOOK_URL, data=body, headers={
            "Content-Type": "application/json", "x-paystack-signature": signature,
        })
        assert resp.status_code == 503

    def test_response_never_discloses_secret_or_signature(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body("whatever")
        resp = _post_unsigned(client, body, "wrong-signature-value")
        body_text = resp.get_data(as_text=True)
        assert _WEBHOOK_SECRET not in body_text
        assert "wrong-signature-value" not in body_text

    def test_unauthenticated_request_not_blocked_by_user_auth(self, client, app):
        """No user/session authentication is required or even checked —
        a correctly-signed request succeeds with zero Authorization
        header, proving this endpoint's only gate is the signature.
        """
        _enable_paystack(app)
        body = _charge_success_body("does-not-exist-either")
        resp = client.post(_WEBHOOK_URL, data=body, headers={
            "Content-Type": "application/json", "x-paystack-signature": _sign(_WEBHOOK_SECRET, body),
        })
        assert resp.status_code == 200


class TestWebhookRoutingAndPayloadValidation:
    def test_irrelevant_event_acknowledged_without_mutation(self, client, app):
        _enable_paystack(app)
        body = json.dumps({"event": "subscription.create", "data": {"reference": "whatever"}}).encode()
        resp = _post_signed(client, body)
        assert resp.status_code == 200

    def test_malformed_json_with_valid_signature(self, client, app):
        _enable_paystack(app)
        body = b"{not valid json"
        resp = _post_signed(client, body)
        assert resp.status_code == 200

    def test_charge_success_missing_reference_acknowledged_safely(self, client, app):
        _enable_paystack(app)
        body = json.dumps({"event": "charge.success", "data": {"amount": 100000}}).encode()
        resp = _post_signed(client, body)
        assert resp.status_code == 200

    def test_non_object_body_acknowledged_safely(self, client, app):
        _enable_paystack(app)
        body = json.dumps(["not", "an", "object"]).encode()
        resp = _post_signed(client, body)
        assert resp.status_code == 200


class TestWebhookUnknownReference:
    def test_unknown_reference_returns_200(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body("wsfcircle-" + uuid.uuid4().hex)
        resp = _post_signed(client, body)
        assert resp.status_code == 200

    def test_unknown_reference_creates_no_payment(self, client, app):
        _enable_paystack(app)
        reference = "wsfcircle-" + uuid.uuid4().hex
        _post_signed(client, _charge_success_body(reference))
        assert _count_payments_for_reference(app, reference) == 0

    def test_unknown_reference_creates_no_subscription(self, client, app):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, _register_and_get(client, app))
        reference = "wsfcircle-" + uuid.uuid4().hex
        _post_signed(client, _charge_success_body(reference, metadata={"plan_id": plan_id, "user_id": user.id}))
        assert _count_subscriptions(app, user.id) == 0

    def test_metadata_cannot_manufacture_user_or_plan_entitlement(self, client, app):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, _register_and_get(client, app))
        reference = "wsfcircle-" + uuid.uuid4().hex
        body = _charge_success_body(
            reference, amount=100000, metadata={"plan_id": plan_id, "user_id": user.id},
            customer={"email": user.email},
        )
        resp = _post_signed(client, body)
        assert resp.status_code == 200
        assert _count_subscriptions(app, user.id) == 0
        assert _has_access(app, user.id) is False


def _register_and_get(client, app):
    payload = dict(USER1, email=f"circlewebhook-{uuid.uuid4().hex[:8]}@example.com")
    client.post("/api/v1/auth/register", json=payload)
    return payload["email"]


class TestWebhookPendingPayment:
    def test_pending_payment_matched_consumes_new_membership(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD", billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1
        assert _has_access(app, user.id) is True

    def test_pending_payment_same_plan_renewal_extends_existing(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD", billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        from datetime import datetime, timedelta, timezone

        future_end = datetime.now(timezone.utc) + timedelta(days=5)
        subscription_id = _make_subscription(app, user.id, plan_id, status="active", current_period_end=future_end)
        payment_id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert stored.subscription_id == subscription_id
        assert _count_subscriptions(app, user.id) == 1

    def test_pending_payment_mismatch_reconciliation_required(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, amount=1)

        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "verified"
        assert stored.provider_snapshot["reconciliation_required"] is True
        assert _count_subscriptions(app, user.id) == 0

    def test_pending_payment_verify_still_pending_returns_non_2xx(self, client, app, user1_token):
        """A charge.success webhook whose fresh Verify call still
        reports `pending`/processing is an unresolved inconsistency, not
        a handled event — it must not be acknowledged as `consumed`,
        and the route must return non-2xx so Paystack retries later.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        still_pending = {
            "status": "pending", "amount": payment.amount_subunits, "currency": payment.currency,
            "customer_email": payment.customer_email, "reference": payment.reference,
        }

        with patch("app.services.circle_payments.verify_transaction", return_value=still_pending):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 503
        stored = _get_payment(app, reference)
        assert stored.status == "pending"
        assert _count_subscriptions(app, user.id) == 0

    def test_pending_inconsistent_verify_then_matching_retry_consumes_once(self, client, app, user1_token):
        """The same payment: first delivery's fresh Verify still says
        pending (non-2xx, nothing consumed); a later retry whose fresh
        Verify now says success follows the ordinary matched path and
        consumes exactly once.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)
        still_pending = {
            "status": "pending", "amount": payment.amount_subunits, "currency": payment.currency,
            "customer_email": payment.customer_email, "reference": payment.reference,
        }

        with patch("app.services.circle_payments.verify_transaction", return_value=still_pending):
            first = _post_signed(client, body)
        assert first.status_code != 200
        assert _get_payment(app, reference).status == "pending"
        assert _count_subscriptions(app, user.id) == 0

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            second = _post_signed(client, body)
        assert second.status_code == 200

        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1

    def test_webhook_amount_cannot_override_stored_amount(self, client, app, user1_token):
        """The webhook payload's own `data.amount` is never trusted —
        only the server-to-server Verify result matters, and that
        result is compared against CirclePayment's own snapshot.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference, amount=1))

        assert resp.status_code == 200
        assert _get_payment(app, reference).status == "consumed"

    def test_webhook_currency_cannot_override_stored_currency(self, client, app, user1_token):
        _enable_paystack(app, currencies=("USD", "NGN"))
        plan_id, slug = _make_plan(app, currency="USD")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, currency="USD", customer_email=user.email)
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference, currency="NGN"))

        assert resp.status_code == 200
        assert _get_payment(app, reference).status == "consumed"

    def test_webhook_email_cannot_override_stored_email(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference, customer={"email": "attacker@example.com"}))

        assert resp.status_code == 200
        assert _get_payment(app, reference).status == "consumed"


class TestWebhookReplay:
    def test_identical_webhook_delivered_twice_is_safe(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)) as mock_verify:
            first = _post_signed(client, body)
            second = _post_signed(client, body)

        assert first.status_code == 200
        assert second.status_code == 200
        assert mock_verify.call_count == 1
        assert _count_subscriptions(app, user.id) == 1
        subscription_id = _get_payment(app, reference).subscription_id
        assert _count_audit(app, "circle_payment.consumed_new_membership", subscription_id) == 1
        assert _count_audit(app, "circle_payment.webhook_replay") == 1

    def test_webhook_after_status_endpoint_already_consumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            status_resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
            assert status_resp.get_json()["data"]["status"] == "consumed"

            webhook_resp = _post_signed(client, _charge_success_body(reference))

        assert webhook_resp.status_code == 200
        assert _count_subscriptions(app, user.id) == 1

    def test_simultaneous_duplicate_webhooks_never_double_activate(self, app):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD", billing_interval="monthly")

        payload = dict(USER1, email="circlewebhook-race@example.com")
        with app.test_client() as setup_client:
            setup_client.post("/api/v1/auth/register", json=payload)
        user = _get_user(app, payload["email"])

        _id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)
        signature = _sign(_WEBHOOK_SECRET, body)

        results = {}

        def _deliver(name):
            with app.test_client() as thread_client:
                resp = thread_client.post(_WEBHOOK_URL, data=body, headers={
                    "Content-Type": "application/json", "x-paystack-signature": signature,
                })
                results[name] = resp.status_code

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            t1 = threading.Thread(target=_deliver, args=("a",))
            t2 = threading.Thread(target=_deliver, args=("b",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert results["a"] == 200
        assert results["b"] == 200
        assert _count_subscriptions(app, user.id) == 1

    def test_simultaneous_webhooks_deterministic_expired_status_race_still_returns_200(self, app):
        """Deterministically forces the exact interleaving that used to
        make this 503: thread A wins the row lock, flips the payment to
        `verified`, and commits — releasing the lock; thread B then
        acquires it, consumes the payment, and commits `consumed`. The
        bug was that A's own post-commit code read `locked.status` (an
        attribute SQLAlchemy's `expire_on_commit=True` had just marked
        stale) *after* B's commit landed, observing `consumed` instead
        of the `verified` outcome A itself had just established, and
        fell through to `not_yet_confirmed` (503).

        Unlike the test above — which relies on real OS thread
        scheduling to occasionally produce this interleaving — this test
        pins it down with a `threading.Event`-gated wrapper around
        `db.session.commit`, so the race is exercised every run rather
        than ~1-in-5. No production code is touched; only the ordering
        of two already-concurrent requests is pinned.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD", billing_interval="monthly")

        payload = dict(USER1, email="circlewebhook-race-deterministic@example.com")
        with app.test_client() as setup_client:
            setup_client.post("/api/v1/auth/register", json=payload)
        user = _get_user(app, payload["email"])

        _id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)
        signature = _sign(_WEBHOOK_SECRET, body)

        results = {}
        commit_count = {"n": 0}
        count_lock = threading.Lock()
        b_consumed = threading.Event()
        # scoped_session methods are defined on the class and dispatch to
        # whichever thread's Session is current when called — capturing
        # the unbound original here and invoking it as `original(self)`
        # inside the wrapper preserves that per-thread dispatch instead
        # of pinning every call to one thread's session.
        original_commit = type(db.session).commit

        def _wrapped_commit(self, *args, **kwargs):
            result = original_commit(self, *args, **kwargs)
            with count_lock:
                commit_count["n"] += 1
                n = commit_count["n"]
            if n == 1:
                # This is always the verify-and-flip-to-"verified" commit
                # inside _verify_with_provider_for_webhook — whichever
                # thread won the row lock first. The real commit above
                # already released that row lock, so the sibling thread's
                # blocked FOR UPDATE can now proceed; hold this thread
                # here until that sibling has fully consumed the payment
                # (commit #3: consume_verified_circle_payment's own
                # status="consumed" commit, then a second commit from
                # log_action's internal db.session.commit() for the
                # resulting audit entry), so this thread's post-commit
                # code runs exactly when the original bug required.
                assert b_consumed.wait(timeout=5), "sibling never reached its consume commit"
            elif n == 3:
                b_consumed.set()
            return result

        def _deliver(name):
            with app.test_client() as thread_client:
                resp = thread_client.post(_WEBHOOK_URL, data=body, headers={
                    "Content-Type": "application/json", "x-paystack-signature": signature,
                })
                results[name] = resp.status_code

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)), \
                patch.object(type(db.session), "commit", _wrapped_commit):
            t1 = threading.Thread(target=_deliver, args=("a",))
            t2 = threading.Thread(target=_deliver, args=("b",))
            t1.start()
            t2.start()
            t1.join(timeout=10)
            t2.join(timeout=10)

        assert not t1.is_alive() and not t2.is_alive(), "a worker thread never finished"
        # The two real correctness checks this test exists for — assert
        # these first so a regression fails here, clearly, rather than
        # on the commit-count sanity check below.
        assert results["a"] == 200
        assert results["b"] == 200
        assert _count_subscriptions(app, user.id) == 1
        payment = _get_payment(app, reference)
        assert payment.status == "consumed"
        assert _count_audit(app, "circle_payment.consumed_new_membership", payment.subscription_id) == 1
        # Sanity check that the synchronization point was actually
        # reached (not e.g. skipped because b_consumed was never waited
        # on) — at least the 3 commits consume_verified_circle_payment's
        # success path always produces (the fresh-verify commit, the
        # status="consumed" commit, and log_action's own commit for the
        # audit entry).
        assert commit_count["n"] >= 3


class TestWebhookFailedRecovery:
    def test_failed_payment_recovered_to_consumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="failed", customer_email=user.email)
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1
        assert _has_access(app, user.id) is True
        assert _count_audit(app, "circle_payment.webhook_recovered", payment_id) == 1

    def test_failed_payment_still_failing_verify_stays_unsuccessful(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="failed", customer_email=user.email)
        payment = _get_payment(app, reference)
        still_failed = {"status": "failed", "amount": payment.amount_subunits, "currency": payment.currency,
                         "customer_email": payment.customer_email, "reference": payment.reference}

        with patch("app.services.circle_payments.verify_transaction", return_value=still_failed):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 503
        assert _get_payment(app, reference).status == "failed"
        assert _count_subscriptions(app, user.id) == 0

    def test_failed_payment_retry_timing_consumes_exactly_once(self, client, app, user1_token):
        """First delivery's fresh Verify still says failed (non-2xx,
        remains failed); a later retry whose fresh Verify now returns
        success with every invariant matching follows failed -> verified
        -> consumed, activating membership exactly once.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="failed", customer_email=user.email)
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)
        still_failed = {"status": "failed", "amount": payment.amount_subunits, "currency": payment.currency,
                         "customer_email": payment.customer_email, "reference": payment.reference}

        with patch("app.services.circle_payments.verify_transaction", return_value=still_failed):
            first = _post_signed(client, body)
        assert first.status_code == 503
        assert _get_payment(app, reference).status == "failed"
        assert _count_subscriptions(app, user.id) == 0

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            second = _post_signed(client, body)
        assert second.status_code == 200

        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1
        assert _has_access(app, user.id) is True

    def test_failed_payment_recovery_mismatch_reconciliation_required(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="failed", customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, currency="NGN")

        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "verified"
        assert stored.provider_snapshot["reconciliation_required"] is True
        assert _count_subscriptions(app, user.id) == 0


class TestWebhookAbandonedRecovery:
    def test_abandoned_payment_recovered_to_consumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="abandoned", customer_email=user.email)
        payment = _get_payment(app, reference)

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1
        assert _has_access(app, user.id) is True
        assert _count_audit(app, "circle_payment.webhook_recovered", payment_id) == 1

    def test_abandoned_payment_still_abandoned_stays_unsuccessful(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="abandoned", customer_email=user.email)
        payment = _get_payment(app, reference)
        still_abandoned = {"status": "abandoned", "amount": payment.amount_subunits, "currency": payment.currency,
                            "customer_email": payment.customer_email, "reference": payment.reference}

        with patch("app.services.circle_payments.verify_transaction", return_value=still_abandoned):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 503
        assert _get_payment(app, reference).status == "abandoned"
        assert _count_subscriptions(app, user.id) == 0

    def test_abandoned_payment_retry_timing_consumes_exactly_once(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="abandoned", customer_email=user.email)
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)
        still_abandoned = {"status": "abandoned", "amount": payment.amount_subunits, "currency": payment.currency,
                            "customer_email": payment.customer_email, "reference": payment.reference}

        with patch("app.services.circle_payments.verify_transaction", return_value=still_abandoned):
            first = _post_signed(client, body)
        assert first.status_code == 503
        assert _get_payment(app, reference).status == "abandoned"
        assert _count_subscriptions(app, user.id) == 0

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            second = _post_signed(client, body)
        assert second.status_code == 200

        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1
        assert _has_access(app, user.id) is True


class TestWebhookCleanVerifiedCrashRecovery:
    """CirclePayment.status == "verified" with no reconciliation flag
    exists partly for crash safety between "Paystack confirmed success"
    and "membership actually activated" (see app/models/circle.py's own
    docstring on that status). A process/DB interruption in that window
    can leave a legitimate, already-matched payment sitting in exactly
    this state — a trusted webhook delivery must be able to resume and
    complete that interrupted activation without requiring a second
    Paystack Verify call, since the existing verified state already
    carries the authoritative evidence.
    """

    def test_clean_verified_payment_recovers_to_consumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, status="verified", customer_email=user.email,
            provider_snapshot={
                "status": "success", "amount": 100000, "currency": "USD",
                "channel": "card", "paid_at": "2026-10-05T12:00:00.000Z", "gateway_response": "Successful",
            },
        )

        with patch("app.services.circle_payments.verify_transaction") as mock_verify:
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        assert mock_verify.call_count == 0  # no fresh Verify needed — the existing verified state is authoritative
        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert stored.subscription_id is not None
        assert _count_subscriptions(app, user.id) == 1
        assert _has_access(app, user.id) is True

    def test_clean_verified_replay_does_not_double_extend(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, status="verified", customer_email=user.email,
            provider_snapshot={
                "status": "success", "amount": 100000, "currency": "USD",
                "channel": "card", "paid_at": "2026-10-05T12:00:00.000Z", "gateway_response": "Successful",
            },
        )
        body = _charge_success_body(reference)

        with patch("app.services.circle_payments.verify_transaction") as mock_verify:
            first = _post_signed(client, body)
            second = _post_signed(client, body)

        assert first.status_code == 200
        assert second.status_code == 200
        assert mock_verify.call_count == 0
        assert _count_subscriptions(app, user.id) == 1
        subscription_id = _get_payment(app, reference).subscription_id
        assert _count_audit(app, "circle_payment.consumed_new_membership", subscription_id) == 1


class TestWebhookAlreadyVerifiedReconciliation:
    def test_existing_reconciliation_flag_not_cleared_by_bare_redelivery(self, client, app, user1_token):
        """Module 3's conservative MVP policy (task spec section 13): a
        payment already sitting in verified+reconciliation_required is
        left exactly as-is by a further webhook delivery — no automatic
        re-verify, no automatic clearing, no activation.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, status="verified", customer_email=user.email,
            provider_snapshot={"status": "success", "reconciliation_required": True, "mismatches": ["amount"]},
        )

        with patch("app.services.circle_payments.verify_transaction") as mock_verify:
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 200
        assert mock_verify.call_count == 0
        stored = _get_payment(app, reference)
        assert stored.status == "verified"
        assert stored.provider_snapshot["reconciliation_required"] is True
        assert _count_subscriptions(app, user.id) == 0


class TestWebhookTransientFailure:
    def test_verify_timeout_returns_non_2xx_and_does_not_mutate(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)

        with patch("app.services.circle_payments.verify_transaction", side_effect=PaystackAPIError("timed out")):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 502
        stored = _get_payment(app, reference)
        assert stored.status == "pending"
        assert _count_subscriptions(app, user.id) == 0

    def test_provider_unavailable_on_failed_payment_does_not_mark_falsely(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="failed", customer_email=user.email)

        with patch("app.services.circle_payments.verify_transaction", side_effect=PaystackAPIError("network down")):
            resp = _post_signed(client, _charge_success_body(reference))

        assert resp.status_code == 502
        assert _get_payment(app, reference).status == "failed"

    def test_retry_after_transient_failure_succeeds_exactly_once(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        body = _charge_success_body(reference)

        with patch("app.services.circle_payments.verify_transaction", side_effect=PaystackAPIError("network down")):
            first = _post_signed(client, body)
        assert first.status_code == 502
        assert _get_payment(app, reference).status == "pending"

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            second = _post_signed(client, body)
        assert second.status_code == 200

        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert _count_subscriptions(app, user.id) == 1


class TestWebhookSecurityInvariants:
    def test_unsigned_fake_charge_success_cannot_activate(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)

        resp = _post_unsigned(client, _charge_success_body(reference), None)

        assert resp.status_code == 401
        assert _get_payment(app, reference).status == "pending"
        assert _count_subscriptions(app, user.id) == 0

    def test_invalid_signature_cannot_activate(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)

        resp = _post_unsigned(client, _charge_success_body(reference), "f" * 128)

        assert resp.status_code == 401
        assert _get_payment(app, reference).status == "pending"
        assert _count_subscriptions(app, user.id) == 0

    def test_webhook_metadata_cannot_switch_user_or_plan(self, client, app, user1_token):
        """The webhook payload's `data.metadata` is never read by this
        module at all — activation always uses the CirclePayment row's
        own `user_id`/`plan_id` (set at checkout-initialization time),
        never anything from the webhook body, however the attacker-
        controlled (or simply stale/wrong) metadata claims.
        """
        _enable_paystack(app)
        plan_a_id, slug_a = _make_plan(app, slug="plan-a")
        plan_b_id, slug_b = _make_plan(app, slug="plan-b")
        user_a = _get_user(app, USER1["email"])
        other = dict(USER1, email="circlewebhook-userb@example.com")
        client.post("/api/v1/auth/register", json=other)
        user_b = _get_user(app, other["email"])

        payment_id, reference = _make_payment(app, user_a.id, plan_a_id, customer_email=user_a.email)
        payment = _get_payment(app, reference)
        body = _charge_success_body(
            reference, metadata={"plan_id": plan_b_id, "user_id": user_b.id},
        )

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = _post_signed(client, body)

        assert resp.status_code == 200
        stored = _get_payment(app, reference)
        assert stored.status == "consumed"
        assert stored.plan_id == plan_a_id
        assert stored.user_id == user_a.id
        assert _count_subscriptions(app, user_a.id) == 1
        assert _count_subscriptions(app, user_b.id) == 0

    def test_checkout_and_status_ownership_unaffected_by_webhook_route(self, client, app, user1_token):
        """Sanity check that adding the webhook route didn't loosen the
        existing owner-only guard on GET /circle/payments/<reference>.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)

        other = dict(USER1, email="circlewebhook-other@example.com")
        client.post("/api/v1/auth/register", json=other)
        other_login = client.post(
            "/api/v1/auth/login", json={"email": other["email"], "password": other["password"]},
        )
        other_token = other_login.get_json()["data"]["access_token"]

        resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(other_token))
        assert resp.status_code == 404
