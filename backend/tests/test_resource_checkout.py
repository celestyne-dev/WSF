"""Stage 1 of the premium-Resource Paystack integration: checkout
initiation (POST /resources/<slug>/checkout) and owner payment status
(GET /resources/payments/<reference>). See app/services/
resource_payments.py. Every test here mocks initialize_transaction/
verify_transaction — nothing makes a real Paystack call. No webhook
tests here — see test_resource_webhook.py for those.
"""
import uuid
from datetime import date
from unittest.mock import patch

import pytest

from tests.conftest import auth_headers

USER1 = {
    "email": "rescheckout-user1@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Obi", "country_code": "NG",
}
USER2 = {
    "email": "rescheckout-user2@example.com", "password": "supersecret1",
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


@pytest.fixture()
def protected_root(app, tmp_path):
    root = tmp_path / "protected_media"
    root.mkdir()
    app.config["PROTECTED_MEDIA_ROOT"] = str(root)
    return root


def _get_user_id(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first().id


def _enable_paystack(app, currencies=("KES",)):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = "sk_test_dummy"
    app.config["PAYSTACK_ALLOWED_CURRENCIES"] = list(currencies)


def _slug(prefix="premium-resource"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _make_premium_resource(app, protected_root, filename=None, **overrides):
    from app.extensions import db
    from app.models.resource import Resource

    filename = filename or f"{uuid.uuid4().hex}.pdf"
    (protected_root / filename).write_bytes(b"%PDF-1.4 fake pdf body")
    defaults = dict(
        slug=overrides.pop("slug", None) or _slug(),
        name="Premium Career Workbook",
        access_type="premium",
        protected_file_path=filename,
        status="published",
        published_date=date.today(),
        description=[{"type": "paragraph", "text": "A premium workbook."}],
        price=1500,
        currency="KES",
    )
    defaults.update(overrides)
    with app.app_context():
        resource = Resource(**defaults)
        db.session.add(resource)
        db.session.commit()
        return resource.id, resource.slug


def _make_purchase(app, user_id, resource_id, **overrides):
    from app.extensions import db
    from app.models.resource import ResourcePurchase

    defaults = dict(user_id=user_id, resource_id=resource_id, status="active")
    defaults.update(overrides)
    with app.app_context():
        purchase = ResourcePurchase(**defaults)
        db.session.add(purchase)
        db.session.commit()
        return purchase.id


def _make_payment(app, user_id, resource_id, **overrides):
    from app.extensions import db
    from app.models.resource import ResourcePayment

    defaults = dict(
        reference=overrides.pop("reference", None) or f"wsfresource-{uuid.uuid4().hex}",
        user_id=user_id,
        resource_id=resource_id,
        amount_subunits=150000,
        currency="KES",
        customer_email=USER1["email"],
        status="pending",
    )
    defaults.update(overrides)
    with app.app_context():
        payment = ResourcePayment(**defaults)
        db.session.add(payment)
        db.session.commit()
        return payment.id, payment.reference


def _get_payment(app, reference):
    from app.models.resource import ResourcePayment

    with app.app_context():
        return ResourcePayment.query.filter_by(reference=reference).first()


def _count_payments_for(app, user_id, resource_id):
    from app.models.resource import ResourcePayment

    with app.app_context():
        return ResourcePayment.query.filter_by(user_id=user_id, resource_id=resource_id).count()


def _count_purchases_for(app, user_id, resource_id):
    from app.models.resource import ResourcePurchase

    with app.app_context():
        return ResourcePurchase.query.filter_by(user_id=user_id, resource_id=resource_id).count()


def _make_plan(app, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePlan

    defaults = dict(
        slug=f"circle-plan-{uuid.uuid4().hex[:10]}",
        name="WSF Circle Membership",
        billing_interval="monthly",
        price=1000,
        currency="KES",
        status="active",
    )
    defaults.update(overrides)
    with app.app_context():
        plan = CirclePlan(**defaults)
        db.session.add(plan)
        db.session.commit()
        return plan.id


def _make_circle_subscription(app, user_id, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    defaults = dict(user_id=user_id, plan_id=plan_id, status="active", source="manual")
    defaults.update(overrides)
    with app.app_context():
        sub = CircleSubscription(**defaults)
        db.session.add(sub)
        db.session.commit()
        return sub.id


_FAKE_INIT_RESULT = {"authorization_url": "https://checkout.paystack.com/abc123", "access_code": "abc123"}


def _mock_init(**kwargs):
    return dict(_FAKE_INIT_RESULT, reference=kwargs["reference"])


def _mock_init_wrong_reference(**kwargs):
    return dict(_FAKE_INIT_RESULT, reference=f"not-{kwargs['reference']}")


class TestCheckoutAuthAndEligibility:
    def test_requires_authentication(self, client, app, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        resp = client.post(f"/api/v1/resources/{slug}/checkout")
        assert resp.status_code == 401

    def test_valid_premium_resource_accepted(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["reference"]
        assert body["authorizationUrl"] == _FAKE_INIT_RESULT["authorization_url"]

    def test_forced_password_change_account_denied(self, client, app, user1_token, protected_root):
        from app.extensions import db
        from app.models.user import User

        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        with app.app_context():
            user = User.query.filter_by(email=USER1["email"]).first()
            user.must_change_password = True
            db.session.commit()

        resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "password_change_required"

    def test_inactive_account_denied(self, client, app, user1_token, protected_root):
        from app.extensions import db
        from app.models.user import User

        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        with app.app_context():
            user = User.query.filter_by(email=USER1["email"]).first()
            user.is_active = False
            db.session.commit()

        resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    def test_non_premium_resource_denied(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root, access_type="direct_download", price=0)
        resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "not_premium"

    def test_unpublished_premium_denied(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root, status="draft")
        resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 404

    def test_zero_priced_premium_denied(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root, price=0)
        resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "resource_not_payable"

    def test_unsupported_currency_denied(self, client, app, user1_token, protected_root):
        _enable_paystack(app, currencies=("USD",))
        _, slug = _make_premium_resource(app, protected_root, currency="KES")
        resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "currency_not_supported"

    def test_already_purchased_denied_without_paystack_initialize(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource_id)

        with patch("app.services.resource_payments.initialize_transaction") as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "already_purchased"
        mock_init.assert_not_called()

    def test_nonexistent_resource_404(self, client, app, user1_token):
        _enable_paystack(app)
        resp = client.post("/api/v1/resources/does-not-exist/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 404


class TestCheckoutCircleEligibility:
    """Follow-up business rule: an active WSF Circle member already has
    complimentary premium Resource access (see app/services/
    resource_access.py's check_resource_access) and must never be able
    to initialize — let alone complete — a Paystack checkout for one.
    See app/services/resource_payments.py's start_resource_checkout for
    the included_with_circle rejection this proves.
    """

    def test_active_circle_member_denied_without_paystack_initialize(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        _make_circle_subscription(app, user_id, plan_id, status="active")
        resource_id, slug = _make_premium_resource(app, protected_root)

        with patch("app.services.resource_payments.initialize_transaction") as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "included_with_circle"
        mock_init.assert_not_called()
        assert _count_payments_for(app, user_id, resource_id) == 0
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_purchased_and_active_circle_member_still_already_purchased(
        self, client, app, user1_token, protected_root
    ):
        """already_purchased is checked first — a purchaser who also has
        Circle gets the existing (harmless, no-op) already_purchased
        response, never included_with_circle.
        """
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        _make_circle_subscription(app, user_id, plan_id, status="active")
        resource_id, slug = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource_id)

        with patch("app.services.resource_payments.initialize_transaction") as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "already_purchased"
        mock_init.assert_not_called()

    def test_expired_circle_member_checkout_allowed_normally(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        _make_circle_subscription(app, user_id, plan_id, status="expired")
        _, slug = _make_premium_resource(app, protected_root)

        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        mock_init.assert_called_once()

    def test_non_circle_unpurchased_user_checkout_continues_normally(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)

        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        mock_init.assert_called_once()


class TestCheckoutSnapshotsAndRequestIsolation:
    def test_amount_is_resource_price_times_100(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        resource_id, slug = _make_premium_resource(app, protected_root, price=2500)
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        assert mock_init.call_args.kwargs["amount_subunits"] == 250000

    def test_email_comes_from_authenticated_user_never_request_body(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(
                f"/api/v1/resources/{slug}/checkout",
                json={"email": "attacker@evil.example", "amount": 1, "currency": "USD", "userId": 999999},
                headers=auth_headers(user1_token),
            )
        assert resp.status_code == 201
        assert mock_init.call_args.kwargs["email"] == USER1["email"].lower()
        assert mock_init.call_args.kwargs["amount_subunits"] != 1
        assert mock_init.call_args.kwargs["currency"] == "KES"

    def test_metadata_is_minimal_resource_and_user_id_only(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        resource_id, slug = _make_premium_resource(app, protected_root)
        user_id = _get_user_id(app, USER1["email"])
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        metadata = mock_init.call_args.kwargs["metadata"]
        assert metadata == {"resource_id": resource_id, "user_id": user_id}

    def test_callback_url_is_resource_specific(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert mock_init.call_args.kwargs["callback_url"].endswith("/resources/checkout/callback")

    def test_initialize_success_stores_snapshots(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init):
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        reference = resp.get_json()["data"]["reference"]
        payment = _get_payment(app, reference)
        assert payment.amount_subunits == 150000
        assert payment.currency == "KES"
        assert payment.customer_email == USER1["email"].lower()
        assert payment.status == "pending"
        assert payment.authorization_url == _FAKE_INIT_RESULT["authorization_url"]

    def test_provider_reference_mismatch_fails_safely(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        resource_id, slug = _make_premium_resource(app, protected_root)
        user_id = _get_user_id(app, USER1["email"])
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init_wrong_reference):
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 502
        assert _count_purchases_for(app, user_id, resource_id) == 0
        assert _count_payments_for(app, user_id, resource_id) == 1

        from app.models.resource import ResourcePayment
        with app.app_context():
            only_payment = ResourcePayment.query.filter_by(user_id=user_id, resource_id=resource_id).first()
            assert only_payment.status == "failed"

    def test_initialize_api_failure_fails_safely(self, client, app, user1_token, protected_root):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        resource_id, slug = _make_premium_resource(app, protected_root)
        user_id = _get_user_id(app, USER1["email"])
        with patch("app.services.resource_payments.initialize_transaction", side_effect=PaystackAPIError("boom")):
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 502
        assert _count_purchases_for(app, user_id, resource_id) == 0

        from app.models.resource import ResourcePayment
        with app.app_context():
            only_payment = ResourcePayment.query.filter_by(user_id=user_id, resource_id=resource_id).first()
            assert only_payment.status == "failed"


class TestCheckoutIdempotencyAndReuse:
    def test_concurrent_double_checkout_does_not_initialize_twice(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root)

        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp1 = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
            resp2 = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.get_json()["data"]["reference"] == resp2.get_json()["data"]["reference"]
        assert mock_init.call_count == 1
        assert _count_payments_for(app, user_id, resource_id) == 1

    def test_recent_valid_pending_checkout_is_reused(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, existing_reference = _make_payment(
            app, user_id, resource_id, amount_subunits=150000, currency="KES",
            authorization_url="https://checkout.paystack.com/same-terms",
        )
        with patch("app.services.resource_payments.initialize_transaction") as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        assert resp.get_json()["data"]["reference"] == existing_reference
        mock_init.assert_not_called()

    def test_stale_repriced_pending_checkout_is_not_reused(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _make_payment(
            app, user_id, resource_id, amount_subunits=100000, currency="KES",  # stale: old price
            authorization_url="https://checkout.paystack.com/old-price",
        )
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        mock_init.assert_called_once()
        assert _count_payments_for(app, user_id, resource_id) == 2

    def test_pending_with_no_authorization_url_is_not_reused(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES", authorization_url=None)
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init) as mock_init:
            resp = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
        assert resp.status_code == 201
        mock_init.assert_called_once()

    def test_different_users_each_get_their_own_checkout(self, client, app, user1_token, user2_token, protected_root):
        _enable_paystack(app)
        _, slug = _make_premium_resource(app, protected_root)
        with patch("app.services.resource_payments.initialize_transaction", side_effect=_mock_init):
            resp1 = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user1_token))
            resp2 = client.post(f"/api/v1/resources/{slug}/checkout", headers=auth_headers(user2_token))
        assert resp1.get_json()["data"]["reference"] != resp2.get_json()["data"]["reference"]


class TestPaymentStatusEndpoint:
    def test_requires_authentication(self, client, app, protected_root):
        _enable_paystack(app)
        resource_id, _ = _make_premium_resource(app, protected_root)
        resp = client.get("/api/v1/resources/payments/whatever")
        assert resp.status_code == 401

    def test_wrong_user_indistinguishable_from_missing_reference(self, client, app, user1_token, user2_token, protected_root):
        _enable_paystack(app)
        user1_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user1_id, resource_id)

        resp_wrong_user = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user2_token))
        resp_missing = client.get("/api/v1/resources/payments/totally-made-up", headers=auth_headers(user2_token))
        assert resp_wrong_user.status_code == resp_missing.status_code == 404
        assert resp_wrong_user.get_json()["error"]["code"] == resp_missing.get_json()["error"]["code"]

    def test_successful_verify_consumes_and_reports_resource_slug(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")

        result = {
            "status": "success", "amount": 150000, "currency": "KES",
            "customer_email": USER1["email"], "provider_transaction_id": "123456",
            "channel": "card", "paid_at": "2026-10-14T12:00:00.000Z",
            "gateway_response": "Successful", "reference": reference,
        }
        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["status"] == "consumed"
        assert body["purchaseActivated"] is True
        assert body["reconciliationRequired"] is False
        assert body["resourceSlug"] == slug
        assert _count_purchases_for(app, user_id, resource_id) == 1

    def test_amount_mismatch_triggers_reconciliation_not_purchase(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")

        result = {
            "status": "success", "amount": 999999, "currency": "KES",
            "customer_email": USER1["email"], "provider_transaction_id": "123456",
            "channel": "card", "paid_at": "2026-10-14T12:00:00.000Z",
            "gateway_response": "Successful", "reference": reference,
        }
        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        body = resp.get_json()["data"]
        assert body["reconciliationRequired"] is True
        assert body["purchaseActivated"] is False
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_currency_mismatch_triggers_reconciliation(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")

        result = {
            "status": "success", "amount": 150000, "currency": "USD",
            "customer_email": USER1["email"], "provider_transaction_id": "123456",
            "channel": "card", "paid_at": "2026-10-14T12:00:00.000Z",
            "gateway_response": "Successful", "reference": reference,
        }
        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["reconciliationRequired"] is True
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_email_mismatch_triggers_reconciliation(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")

        result = {
            "status": "success", "amount": 150000, "currency": "KES",
            "customer_email": "someone-else@example.com", "provider_transaction_id": "123456",
            "channel": "card", "paid_at": "2026-10-14T12:00:00.000Z",
            "gateway_response": "Successful", "reference": reference,
        }
        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["reconciliationRequired"] is True
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_reference_mismatch_triggers_reconciliation(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")

        result = {
            "status": "success", "amount": 150000, "currency": "KES",
            "customer_email": USER1["email"], "provider_transaction_id": "123456",
            "channel": "card", "paid_at": "2026-10-14T12:00:00.000Z",
            "gateway_response": "Successful", "reference": "a-totally-different-reference",
        }
        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["reconciliationRequired"] is True
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_failed_status(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)

        with patch("app.services.resource_payments.verify_transaction", return_value={"status": "failed", "amount": 150000, "currency": "KES", "customer_email": USER1["email"], "reference": reference, "provider_transaction_id": None, "channel": None, "paid_at": None, "gateway_response": "Declined"}):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "failed"
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_abandoned_status(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)

        with patch("app.services.resource_payments.verify_transaction", return_value={"status": "abandoned", "amount": 150000, "currency": "KES", "customer_email": USER1["email"], "reference": reference, "provider_transaction_id": None, "channel": None, "paid_at": None, "gateway_response": None}):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "abandoned"
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_pending_status_with_no_provider_response_yet(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)

        with patch("app.services.resource_payments.verify_transaction", return_value={"status": "pending", "amount": 150000, "currency": "KES", "customer_email": USER1["email"], "reference": reference, "provider_transaction_id": None, "channel": None, "paid_at": None, "gateway_response": None}):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.get_json()["data"]["status"] == "pending"
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_verify_failure_does_not_grant_purchase(self, client, app, user1_token, protected_root):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)

        with patch("app.services.resource_payments.verify_transaction", side_effect=PaystackAPIError("boom")):
            resp = client.get(f"/api/v1/resources/payments/{reference}", headers=auth_headers(user1_token))
        assert resp.status_code == 200  # safe degraded response, never a crash
        assert resp.get_json()["data"]["status"] == "pending"
        assert _count_purchases_for(app, user_id, resource_id) == 0


class TestConsumptionIdempotency:
    def test_clean_verified_payment_creates_exactly_one_purchase(self, app, user1_token, protected_root):
        from app.services.resource_payments import consume_verified_resource_payment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(
            app, user_id, resource_id, amount_subunits=150000, currency="KES", status="verified",
        )
        with app.app_context():
            result = consume_verified_resource_payment(reference)
            assert result["outcome"] == "consumed"
            assert result["payment"].purchase_id is not None
        assert _count_purchases_for(app, user_id, resource_id) == 1

    def test_replay_does_not_create_second_purchase(self, app, user1_token, protected_root):
        from app.services.resource_payments import consume_verified_resource_payment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(
            app, user_id, resource_id, amount_subunits=150000, currency="KES", status="verified",
        )
        with app.app_context():
            first = consume_verified_resource_payment(reference)
            second = consume_verified_resource_payment(reference)
        assert first["outcome"] == "consumed"
        assert second["outcome"] == "already_consumed"
        assert _count_purchases_for(app, user_id, resource_id) == 1

    def test_not_ready_for_pending_payment(self, app, user1_token, protected_root):
        from app.services.resource_payments import consume_verified_resource_payment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id, status="pending")
        with app.app_context():
            result = consume_verified_resource_payment(reference)
        assert result["outcome"] == "not_ready"
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_second_payment_for_already_purchased_resource_attaches_rather_than_duplicates(self, app, user1_token, protected_root):
        """A narrow race/legitimate-replay case: a purchase already exists
        by the time a second, separately-verified payment for the same
        (user, resource) reaches consumption. It must attach to the
        existing purchase, never create a second one — see
        app/services/resource_payments.py's _attach_or_create_purchase.
        """
        from app.services.resource_payments import consume_verified_resource_payment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _make_purchase(app, user_id, resource_id)
        _, reference = _make_payment(
            app, user_id, resource_id, amount_subunits=150000, currency="KES", status="verified",
        )
        with app.app_context():
            result = consume_verified_resource_payment(reference)
        assert result["outcome"] == "consumed"
        assert _count_purchases_for(app, user_id, resource_id) == 1
