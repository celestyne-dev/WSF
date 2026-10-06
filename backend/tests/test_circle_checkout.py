"""Module 2 of the Paystack Circle integration: checkout initiation
(POST /circle/plans/<slug>/checkout). See app/services/circle_payments.py.
Every test here mocks initialize_transaction — nothing makes a real
Paystack call. No webhook, no frontend, no email exists yet.
"""
import threading
import uuid
from unittest.mock import patch

import pytest

from tests.conftest import auth_headers

USER1 = {
    "email": "circlecheckout-user1@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Obi", "country_code": "NG",
}
USER2 = {
    "email": "circlecheckout-user2@example.com", "password": "supersecret1",
    "first_name": "Beatriz", "last_name": "Costa", "country_code": "BR",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user1_token(client):
    return _register(client, USER1)


@pytest.fixture()
def user2_token(client):
    return _register(client, USER2)


def _get_user_id(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first().id


def _enable_paystack(app, currencies=("USD",)):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = "sk_test_dummy"
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


def _count_payments_for(app, user_id, plan_id):
    from app.models.circle import CirclePayment

    with app.app_context():
        return CirclePayment.query.filter_by(user_id=user_id, plan_id=plan_id).count()


_FAKE_INIT_RESULT = {"authorization_url": "https://checkout.paystack.com/abc123", "access_code": "abc123"}


def _mock_init(**kwargs):
    # Real Paystack echoes back the same reference it was given to
    # initialize — the reference-matching invariant checks exactly this.
    return dict(_FAKE_INIT_RESULT, reference=kwargs["reference"])


def _mock_init_wrong_reference(**kwargs):
    return dict(_FAKE_INIT_RESULT, reference=f"not-{kwargs['reference']}")


class TestCheckoutAuthAndEligibility:
    def test_requires_authentication(self, client, app):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout")
        assert resp.status_code == 401

    def test_active_plan_accepted(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["reference"]
        assert body["authorizationUrl"] == _FAKE_INIT_RESULT["authorization_url"]

    def test_nonexistent_plan_rejected(self, client, app, user1_token):
        _enable_paystack(app)
        resp = client.post("/api/v1/circle/plans/no-such-plan/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 404

    def test_inactive_plan_rejected(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, status="draft")
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "plan_not_active"

    def test_zero_price_plan_rejected(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=0)
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "plan_not_payable"

    def test_unsupported_currency_rejected(self, client, app, user1_token):
        _enable_paystack(app, currencies=("KES",))
        plan_id, slug = _make_plan(app, currency="USD")
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "currency_not_supported"

    def test_paystack_disabled_rejected_safely(self, client, app, user1_token):
        app.config["PAYSTACK_ENABLED"] = False
        plan_id, slug = _make_plan(app)
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 503
        assert resp.get_json()["error"]["code"] == "paystack_disabled"

    def test_missing_secret_rejected_safely(self, client, app, user1_token):
        app.config["PAYSTACK_ENABLED"] = True
        app.config["PAYSTACK_SECRET_KEY"] = None
        plan_id, slug = _make_plan(app)
        resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 503
        assert resp.get_json()["error"]["code"] == "paystack_not_configured"


class TestCheckoutServerSideTerms:
    def test_amount_derives_from_db(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=2500, currency="USD")
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
            _, kwargs = mock_init.call_args
            assert kwargs["amount_subunits"] == 250000

    def test_currency_derives_from_db(self, client, app, user1_token):
        _enable_paystack(app, currencies=("USD", "KES"))
        plan_id, slug = _make_plan(app, currency="KES", price=1000)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
            _, kwargs = mock_init.call_args
            assert kwargs["currency"] == "KES"

    def test_interval_derives_from_db(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, billing_interval="yearly", price=9000)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        reference = resp.get_json()["data"]["reference"]
        payment = _get_payment(app, reference)
        assert payment.billing_interval == "yearly"

    def test_authenticated_email_snapshot_used(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
            _, kwargs = mock_init.call_args
            assert kwargs["email"] == USER1["email"].lower()

    def test_client_cannot_override_amount(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(
                f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token),
                json={"amount_subunits": 1, "amount": 1, "price": 1},
            )
            _, kwargs = mock_init.call_args
            assert kwargs["amount_subunits"] == 100000

    def test_client_cannot_override_currency(self, client, app, user1_token):
        _enable_paystack(app, currencies=("USD",))
        plan_id, slug = _make_plan(app, currency="USD")
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(
                f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token), json={"currency": "ZZZ"},
            )
            _, kwargs = mock_init.call_args
            assert kwargs["currency"] == "USD"

    def test_client_cannot_override_email_or_user(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(
                f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token),
                json={"email": "attacker@example.com", "user_id": 999999, "customer_email": "attacker@example.com"},
            )
            _, kwargs = mock_init.call_args
            assert kwargs["email"] == USER1["email"].lower()

    def test_wsf_reference_unique_per_checkout(self, client, app, user1_token, user2_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp1 = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
            resp2 = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user2_token))
        assert resp1.get_json()["data"]["reference"] != resp2.get_json()["data"]["reference"]

    def test_successful_initialization_stores_authorization_url(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        reference = resp.get_json()["data"]["reference"]
        payment = _get_payment(app, reference)
        assert payment.authorization_url == _FAKE_INIT_RESULT["authorization_url"]
        assert payment.status == "pending"


class TestCheckoutProviderFailure:
    def test_provider_failure_does_not_grant_membership(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=PaystackAPIError("boom")):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 502
        assert resp.get_json()["error"]["code"] == "payment_initialization_failed"

        from app.models.circle import CircleSubscription

        user_id = _get_user_id(app, USER1["email"])
        with app.app_context():
            assert CircleSubscription.query.filter_by(user_id=user_id).count() == 0

    def test_provider_failure_marks_payment_failed(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=PaystackAPIError("boom")):
            client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        user_id = _get_user_id(app, USER1["email"])
        from app.models.circle import CirclePayment

        with app.app_context():
            payment = CirclePayment.query.filter_by(user_id=user_id, plan_id=plan_id).first()
            assert payment.status == "failed"

    def test_provider_failure_allows_later_retry(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=PaystackAPIError("boom")):
            first = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert first.status_code == 502

        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            second = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert second.status_code == 201

    def test_provider_returns_different_reference_fails_initialization(self, client, app, user1_token):
        """If Paystack's initialize response reports a reference that
        doesn't match the one WSF generated and requested, the
        authorization URL being handed back can't be trusted to belong
        to WSF's own intended transaction — this must hard-fail exactly
        like any other initialization failure, never silently proceed
        and never create a reconciliation-required payment (nothing has
        been verified as paid yet at this point).
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init_wrong_reference):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 502
        assert resp.get_json()["error"]["code"] == "payment_initialization_failed"
        assert _FAKE_INIT_RESULT["authorization_url"] not in resp.get_data(as_text=True)

        user_id = _get_user_id(app, USER1["email"])
        from app.models.circle import CirclePayment, CircleSubscription

        with app.app_context():
            payment = CirclePayment.query.filter_by(user_id=user_id, plan_id=plan_id).first()
            assert payment.status == "failed"
            assert CircleSubscription.query.filter_by(user_id=user_id).count() == 0


class TestCheckoutDedupe:
    def test_recent_usable_pending_checkout_reused(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            first = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
            second = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert mock_init.call_count == 1
        assert first.get_json()["data"]["reference"] == second.get_json()["data"]["reference"]
        user_id = _get_user_id(app, USER1["email"])
        assert _count_payments_for(app, user_id, plan_id) == 1

    def test_stale_pending_checkout_without_url_not_reused(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        stale_id, stale_reference = _make_payment(app, user_id, plan_id, authorization_url=None, status="pending")

        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        assert resp.get_json()["data"]["reference"] != stale_reference

        stale = _get_payment(app, stale_reference)
        assert stale.status == "failed"

    def test_failed_abandoned_consumed_checkouts_not_reused(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        references = []
        for status in ("failed", "abandoned", "consumed"):
            _, ref = _make_payment(
                app, user_id, plan_id, status=status, authorization_url="https://checkout.paystack.com/old",
            )
            references.append(ref)

        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        assert mock_init.call_count == 1
        assert resp.get_json()["data"]["reference"] not in references


class TestCheckoutMembershipEligibility:
    def test_different_plan_active_member_blocked(self, client, app, user1_token):
        _enable_paystack(app)
        plan_a_id, slug_a = _make_plan(app)
        plan_b_id, slug_b = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        _make_subscription(app, user_id, plan_a_id, status="active", current_period_end=None)
        # give plan A a real period end so it's not caught by the
        # non-expiring rule instead — this test is specifically about
        # the different-plan rule.
        from app.extensions import db
        from app.models.circle import CircleSubscription
        from datetime import datetime, timedelta, timezone

        with app.app_context():
            sub = CircleSubscription.query.filter_by(user_id=user_id, plan_id=plan_a_id).first()
            sub.current_period_end = datetime.now(timezone.utc) + timedelta(days=20)
            db.session.commit()

        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/circle/plans/{slug_b}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "different_plan_active"
        mock_init.assert_not_called()
        assert _count_payments_for(app, user_id, plan_b_id) == 0

    def test_same_plan_active_member_allowed(self, client, app, user1_token):
        from datetime import datetime, timedelta, timezone

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        _make_subscription(
            app, user_id, plan_id, status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=20),
        )
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201

    def test_past_due_same_plan_allowed(self, client, app, user1_token):
        from datetime import datetime, timedelta, timezone

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        _make_subscription(
            app, user_id, plan_id, status="past_due",
            current_period_end=datetime.now(timezone.utc) - timedelta(days=2),
        )
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201

    def test_non_expiring_active_member_blocked(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        _make_subscription(app, user_id, plan_id, status="active", current_period_end=None)
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "non_expiring_membership"
        mock_init.assert_not_called()

    def test_pending_subscription_blocks_checkout(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        _make_subscription(app, user_id, plan_id, status="pending")
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "membership_pending_review"
        mock_init.assert_not_called()

    def test_terminal_historic_member_allowed_to_purchase(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user_id = _get_user_id(app, USER1["email"])
        _make_subscription(app, user_id, plan_id, status="expired")
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201


class TestCheckoutConcurrency:
    def test_concurrent_checkout_does_not_create_duplicate_payments(self, app, client):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        payload_a = dict(USER1, email="circlecheckout-race-a@example.com")
        payload_b = dict(USER1, email="circlecheckout-race-b@example.com")
        # Same *user*, two near-simultaneous clicks — register one account,
        # issue two tokens for it via two logins (both threads act as the
        # same user, which is the actual scenario this dedupe guards).
        client.post("/api/v1/auth/register", json=payload_a)
        login = client.post("/api/v1/auth/login", json={"email": payload_a["email"], "password": payload_a["password"]})
        token = login.get_json()["data"]["access_token"]
        user_id = _get_user_id(app, payload_a["email"])

        results = {}

        def _attempt(name):
            with app.test_client() as thread_client:
                resp = thread_client.post(f"/api/v1/circle/plans/{slug}/checkout", headers=auth_headers(token))
                results[name] = resp.get_json()["data"]["reference"]

        # Patched once, around both threads — unittest.mock.patch's own
        # enter/exit isn't thread-safe to apply concurrently from inside
        # each thread, so the mock is installed before either starts and
        # removed after both finish.
        with patch("app.services.circle_payments.initialize_transaction", side_effect=_mock_init):
            t1 = threading.Thread(target=_attempt, args=("a",))
            t2 = threading.Thread(target=_attempt, args=("b",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert results["a"] == results["b"]
        assert _count_payments_for(app, user_id, plan_id) == 1
