"""Module 2 of the Paystack Circle integration: payment verification
(GET /circle/payments/<reference>) and the idempotent activation core
(app/services/circle_payments.py's consume_verified_circle_payment).
Every test here mocks verify_transaction — nothing makes a real
Paystack call. No webhook, no frontend, no email exists yet.
"""
import threading
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from dateutil.relativedelta import relativedelta

from tests.conftest import auth_headers

USER1 = {
    "email": "circleactivate-user1@example.com", "password": "supersecret1",
    "first_name": "Chiamaka", "last_name": "Eze", "country_code": "KE",
}
USER2 = {
    "email": "circleactivate-user2@example.com", "password": "supersecret1",
    "first_name": "Diego", "last_name": "Martins", "country_code": "BR",
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


def _get_user(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first()


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


def _get_subscription(app, subscription_id):
    from app.models.circle import CircleSubscription

    with app.app_context():
        return CircleSubscription.query.get(subscription_id)


def _count_subscriptions(app, user_id):
    from app.models.circle import CircleSubscription

    with app.app_context():
        return CircleSubscription.query.filter_by(user_id=user_id).count()


def _count_audit(app, action, entity_id):
    from app.models.audit import AuditLog

    with app.app_context():
        return AuditLog.query.filter_by(action=action, entity_id=str(entity_id)).count()


def _success_result(payment_id_or_payment, **overrides):
    payment = payment_id_or_payment
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


class TestPaymentStatusOwnership:
    def test_payment_owner_may_query_status(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        _id, reference = _make_payment(app, user.id, plan_id, status="failed")
        resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["reference"] == reference

    def test_another_user_cannot_inspect_it(self, client, app, user1_token, user2_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        _id, reference = _make_payment(app, user.id, plan_id, status="failed")
        resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user2_token))
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "not_found"

    def test_unknown_reference_safe(self, client, app, user1_token):
        resp = client.get("/api/v1/circle/payments/does-not-exist", headers=auth_headers(user1_token))
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "not_found"


class TestProviderStatusMapping:
    def test_pending_provider_transaction_remains_pending(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        _id, reference = _make_payment(app, user.id, plan_id)
        with patch("app.services.circle_payments.verify_transaction", return_value={"status": "pending", "amount": 100000, "currency": "USD", "customer_email": user.email}):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "pending"
        assert _get_payment(app, reference).status == "pending"

    def test_abandoned_becomes_abandoned(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        _id, reference = _make_payment(app, user.id, plan_id)
        with patch("app.services.circle_payments.verify_transaction", return_value={"status": "abandoned", "amount": 100000, "currency": "USD", "customer_email": user.email}):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "abandoned"
        assert resp.get_json()["data"]["membershipActivated"] is False
        assert _get_payment(app, reference).status == "abandoned"

    def test_failed_becomes_failed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        _id, reference = _make_payment(app, user.id, plan_id)
        with patch("app.services.circle_payments.verify_transaction", return_value={"status": "failed", "amount": 100000, "currency": "USD", "customer_email": user.email}):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "failed"
        assert _get_payment(app, reference).status == "failed"

    def test_provider_verification_outage_does_not_falsely_mark_failed_or_consumed(self, client, app, user1_token):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        _id, reference = _make_payment(app, user.id, plan_id)
        with patch("app.services.circle_payments.verify_transaction", side_effect=PaystackAPIError("network down")):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "pending"
        assert resp.get_json()["data"]["reason"] == "verification_unavailable"
        assert _get_payment(app, reference).status == "pending"


class TestSuccessfulVerificationAndInvariants:
    def test_successful_matching_verification_proceeds(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD", billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)
        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        data = resp.get_json()["data"]
        assert data["status"] == "consumed"
        assert data["membershipActivated"] is True

        from app.services.circle import has_circle_access

        with app.app_context():
            from app.models.user import User

            fresh_user = User.query.get(user.id)
            assert has_circle_access(fresh_user) is True

    def test_amount_mismatch_leaves_payment_unconsumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, amount_subunits=100000, customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, amount=999)
        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        data = resp.get_json()["data"]
        assert data["status"] == "verified"
        assert data["membershipActivated"] is False
        assert data["reconciliationRequired"] is True
        assert _count_subscriptions(app, user.id) == 0

    def test_currency_mismatch_leaves_payment_unconsumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, currency="USD")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, currency="USD", customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, currency="NGN")
        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        data = resp.get_json()["data"]
        assert data["status"] == "verified"
        assert data["reconciliationRequired"] is True
        assert _count_subscriptions(app, user.id) == 0

    def test_email_mismatch_leaves_payment_unconsumed(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, customer_email="someone-else@example.com")
        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        data = resp.get_json()["data"]
        assert data["status"] == "verified"
        assert data["reconciliationRequired"] is True
        assert _count_subscriptions(app, user.id) == 0

    def test_reference_mismatch_leaves_payment_unconsumed(self, client, app, user1_token):
        """Paystack reporting success for a *different* reference than
        the one WSF asked it to verify may mean real money moved under
        that other reference — this must land in the same
        verified+reconciliation_required state as the other invariant
        mismatches, never a plain failure and never silent activation.
        """
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, reference="some-other-transaction-ref")
        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            resp = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        data = resp.get_json()["data"]
        assert data["status"] == "verified"
        assert data["membershipActivated"] is False
        assert data["reconciliationRequired"] is True
        assert _count_subscriptions(app, user.id) == 0

        stored = _get_payment(app, reference)
        assert "reference" in stored.provider_snapshot["mismatches"]

    def test_mismatch_state_suitable_for_manual_reconciliation(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        bad_result = _success_result(payment, amount=1)
        with patch("app.services.circle_payments.verify_transaction", return_value=bad_result):
            client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        stored = _get_payment(app, reference)
        assert stored.provider_snapshot["reconciliation_required"] is True
        assert "amount" in stored.provider_snapshot["mismatches"]
        # Only the allowlisted fields plus the mismatch markers — never a
        # raw/arbitrary provider payload.
        assert set(stored.provider_snapshot.keys()) <= {
            "status", "amount", "currency", "channel", "paid_at", "gateway_response",
            "reconciliation_required", "mismatches",
        }

    def test_repeated_verification_does_not_duplicate_membership(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        payment = _get_payment(app, reference)
        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)):
            client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
            second = client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert second.get_json()["data"]["status"] == "consumed"
        assert _count_subscriptions(app, user.id) == 1

    def test_recent_verification_attempt_does_not_hammer_provider(self, client, app, user1_token):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app)
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, customer_email=user.email)
        with patch(
            "app.services.circle_payments.verify_transaction",
            return_value={"status": "pending", "amount": 100000, "currency": "USD", "customer_email": user.email},
        ) as mock_verify:
            client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
            client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(user1_token))
        assert mock_verify.call_count == 1


class TestActivationCalendarMath:
    def test_monthly_month_end_clamping(self):
        from app.services.circle_payments import _add_billing_interval

        start = datetime(2027, 1, 31, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "monthly") == datetime(2027, 2, 28, tzinfo=timezone.utc)

    def test_monthly_leap_year_clamping(self):
        from app.services.circle_payments import _add_billing_interval

        start = datetime(2028, 1, 31, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "monthly") == datetime(2028, 2, 29, tzinfo=timezone.utc)

    def test_monthly_31_day_to_30_day_month(self):
        from app.services.circle_payments import _add_billing_interval

        start = datetime(2027, 3, 31, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "monthly") == datetime(2027, 4, 30, tzinfo=timezone.utc)

    def test_yearly_leap_day_start(self):
        from app.services.circle_payments import _add_billing_interval

        start = datetime(2028, 2, 29, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "yearly") == datetime(2029, 2, 28, tzinfo=timezone.utc)

    def test_yearly_ordinary_date(self):
        from app.services.circle_payments import _add_billing_interval

        start = datetime(2027, 6, 15, tzinfo=timezone.utc)
        assert _add_billing_interval(start, "yearly") == datetime(2028, 6, 15, tzinfo=timezone.utc)


class TestActivationNewAndRenewal:
    def test_new_membership_sets_active_subscription(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(
            app, user.id, plan_id, status="verified", customer_email=user.email,
            verified_at=datetime.now(timezone.utc),
        )
        with app.app_context():
            result = consume_verified_circle_payment(reference)
            assert result["outcome"] == "consumed"
            subscription = result["payment"].subscription
            assert subscription.status == "active"
            assert subscription.source == "external"
            assert subscription.provider == "paystack"
            assert subscription.payment_reference == reference

    def test_same_plan_renewal_extends_from_existing_future_end_date(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        old_starts_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        old_end = datetime(2026, 11, 30, tzinfo=timezone.utc)
        subscription_id = _make_subscription(
            app, user.id, plan_id, status="active", starts_at=old_starts_at,
            current_period_start=old_starts_at, current_period_end=old_end,
        )
        payment_id, reference = _make_payment(app, user.id, plan_id, status="verified", customer_email=user.email)

        with app.app_context():
            result = consume_verified_circle_payment(reference)
            assert result["outcome"] == "consumed"

        subscription = _get_subscription(app, subscription_id)
        assert subscription.current_period_end == old_end + relativedelta(months=1)
        assert subscription.starts_at == old_starts_at
        payment = _get_payment(app, reference)
        assert payment.subscription_id == subscription_id
        assert _count_subscriptions(app, user.id) == 1

    def test_renewal_does_not_reset_starts_at(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        old_starts_at = datetime(2025, 6, 1, tzinfo=timezone.utc)
        subscription_id = _make_subscription(
            app, user.id, plan_id, status="active", starts_at=old_starts_at,
            current_period_start=old_starts_at,
            current_period_end=datetime.now(timezone.utc) + timedelta(days=5),
        )
        payment_id, reference = _make_payment(app, user.id, plan_id, status="verified", customer_email=user.email)
        with app.app_context():
            consume_verified_circle_payment(reference)
        assert _get_subscription(app, subscription_id).starts_at == old_starts_at

    def test_repeated_consume_call_does_not_extend_twice(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        subscription_id = _make_subscription(
            app, user.id, plan_id, status="active",
            current_period_end=datetime.now(timezone.utc) + timedelta(days=5),
        )
        payment_id, reference = _make_payment(app, user.id, plan_id, status="verified", customer_email=user.email)

        with app.app_context():
            first = consume_verified_circle_payment(reference)
            assert first["outcome"] == "consumed"
            end_after_first = _get_subscription(app, subscription_id).current_period_end

            second = consume_verified_circle_payment(reference)
            assert second["outcome"] == "already_consumed"
            end_after_second = _get_subscription(app, subscription_id).current_period_end

        assert end_after_first == end_after_second

    def test_terminal_previous_membership_repurchase_creates_fresh_subscription(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        old_end = datetime.now(timezone.utc) - timedelta(days=30)
        old_subscription_id = _make_subscription(
            app, user.id, plan_id, status="expired", current_period_end=old_end,
        )
        payment_id, reference = _make_payment(app, user.id, plan_id, status="verified", customer_email=user.email)

        with app.app_context():
            result = consume_verified_circle_payment(reference)
            assert result["outcome"] == "consumed"

        old_subscription = _get_subscription(app, old_subscription_id)
        assert old_subscription.status == "expired"
        assert old_subscription.current_period_end == old_end

        payment = _get_payment(app, reference)
        assert payment.subscription_id != old_subscription_id
        new_subscription = _get_subscription(app, payment.subscription_id)
        assert new_subscription.status == "active"
        assert _count_subscriptions(app, user.id) == 2

    def test_different_plan_no_automated_mid_period_switch(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_a_id, slug_a = _make_plan(app, billing_interval="monthly")
        plan_b_id, slug_b = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        future_end = datetime.now(timezone.utc) + timedelta(days=20)
        subscription_id = _make_subscription(app, user.id, plan_a_id, status="active", current_period_end=future_end)
        payment_id, reference = _make_payment(app, user.id, plan_b_id, status="verified", customer_email=user.email)

        with app.app_context():
            result = consume_verified_circle_payment(reference)
            assert result["outcome"] == "membership_conflict"

        assert _get_payment(app, reference).status == "verified"
        assert _get_subscription(app, subscription_id).current_period_end == future_end
        assert _count_subscriptions(app, user.id) == 1


class TestActivationAtomicityAndIdempotency:
    def test_subscription_mutation_failure_does_not_falsely_consume_payment(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        # A conflicting current subscription already exists for this user
        # (a different plan) — forcing _classify_membership_action to
        # report "new" anyway (as if it raced with the row that was just
        # created) simulates the flush()-time IntegrityError this
        # invariant exists to guard against.
        other_plan_id, _ = _make_plan(app)
        conflicting_subscription_id = _make_subscription(app, user.id, other_plan_id, status="active")
        payment_id, reference = _make_payment(app, user.id, plan_id, status="verified", customer_email=user.email)

        with app.app_context(), patch(
            "app.services.circle_payments._classify_membership_action", return_value=("new", None)
        ):
            result = consume_verified_circle_payment(reference)
            assert result["outcome"] == "membership_conflict"

        payment = _get_payment(app, reference)
        assert payment.status == "verified"
        assert payment.subscription_id is None
        assert _count_subscriptions(app, user.id) == 1
        assert _get_subscription(app, conflicting_subscription_id).status == "active"

    def test_already_consumed_is_idempotent_no_op(self, client, app, user1_token):
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, slug = _make_plan(app, billing_interval="monthly")
        user = _get_user(app, USER1["email"])
        payment_id, reference = _make_payment(app, user.id, plan_id, status="verified", customer_email=user.email)

        with app.app_context():
            first = consume_verified_circle_payment(reference)
            subscription_id = first["payment"].subscription_id
            second = consume_verified_circle_payment(reference)

        assert first["outcome"] == "consumed"
        assert second["outcome"] == "already_consumed"
        assert second["payment"].subscription_id == subscription_id
        assert _count_audit(app, "circle_payment.consumed_new_membership", subscription_id) == 1


class TestConcurrentVerificationAndConsumption:
    def test_concurrent_status_requests_never_double_activate(self, app, client):
        _enable_paystack(app)
        plan_id, slug = _make_plan(app, price=1000, currency="USD", billing_interval="monthly")

        payload = dict(USER1, email="circleactivate-race@example.com")
        client.post("/api/v1/auth/register", json=payload)
        login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
        token = login.get_json()["data"]["access_token"]
        user = _get_user(app, payload["email"])

        _id, reference = _make_payment(
            app, user.id, plan_id, amount_subunits=100000, currency="USD", customer_email=user.email,
        )
        payment = _get_payment(app, reference)

        results = {}

        def _attempt(name):
            with app.test_client() as thread_client:
                resp = thread_client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(token))
                results[name] = resp.get_json()["data"]

        with patch("app.services.circle_payments.verify_transaction", return_value=_success_result(payment)) as mock_verify:
            t1 = threading.Thread(target=_attempt, args=("a",))
            t2 = threading.Thread(target=_attempt, args=("b",))
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        assert mock_verify.call_count == 1
        assert results["a"]["status"] == "consumed"
        assert results["b"]["status"] == "consumed"
        assert _count_subscriptions(app, user.id) == 1
        subscription = _get_payment(app, reference).subscription_id
        assert _count_audit(app, "circle_payment.consumed_new_membership", subscription) == 1
