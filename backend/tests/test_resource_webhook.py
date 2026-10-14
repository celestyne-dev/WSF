"""Stage 1 of the premium-Resource Paystack integration: the shared
webhook delivery handler (POST /api/v1/webhooks/paystack), extended to
dispatch to ResourcePayment processing. Every test here signs its own
raw request body with the exact same HMAC-SHA512 scheme Paystack uses
and posts it straight to the Flask test client — nothing makes a real
Paystack call. See app/api/v1/webhooks.py and app/services/
resource_payments.py's process_resource_webhook_charge_success. A
dedicated cross-dispatch test proves BOTH CirclePayment and
ResourcePayment references still route correctly through this one
shared endpoint — the existing Circle webhook test suite
(test_circle_webhooks.py) is otherwise unmodified and must keep passing.
"""
import hashlib
import hmac
import json
import uuid
from datetime import date
from unittest.mock import patch

import pytest

from tests.conftest import auth_headers

USER1 = {
    "email": "reswebhook-user1@example.com", "password": "supersecret1",
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


def _enable_paystack(app, secret=_WEBHOOK_SECRET, currencies=("KES",)):
    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = secret
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


def _count_purchases_for(app, user_id, resource_id):
    from app.models.resource import ResourcePurchase

    with app.app_context():
        return ResourcePurchase.query.filter_by(user_id=user_id, resource_id=resource_id).count()


def _count_audit(app, action, entity_id=None):
    from app.models.audit import AuditLog

    with app.app_context():
        query = AuditLog.query.filter_by(action=action)
        if entity_id is not None:
            query = query.filter_by(entity_id=str(entity_id))
        return query.count()


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
        "paid_at": "2026-10-14T12:00:00.000Z",
        "gateway_response": "Successful",
        "reference": payment.reference,
    }
    result.update(overrides)
    return result


class TestResourceWebhookDispatch:
    def test_valid_signed_resource_charge_success_consumes_payment(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        payment_id, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")
        payment = _get_payment(app, reference)
        result = _success_result(payment)

        body = _charge_success_body(reference)
        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = _post_signed(client, body)
        assert resp.status_code == 200
        assert _count_purchases_for(app, user_id, resource_id) == 1
        assert _count_audit(app, "resource_payment.consumed", None) >= 1

    def test_duplicate_resource_webhook_delivery_safe(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")
        payment = _get_payment(app, reference)
        result = _success_result(payment)
        body = _charge_success_body(reference)

        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            first = _post_signed(client, body)
            second = _post_signed(client, body)
        assert first.status_code == 200
        assert second.status_code == 200
        assert _count_purchases_for(app, user_id, resource_id) == 1

    def test_unknown_resource_reference_safe(self, client, app):
        _enable_paystack(app)
        body = _charge_success_body(f"wsfresource-{uuid.uuid4().hex}")
        resp = _post_signed(client, body)
        assert resp.status_code == 200

    def test_bad_signature_rejected(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)
        body = _charge_success_body(reference)
        resp = _post_unsigned(client, body, "0" * 128)
        assert resp.status_code == 401
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_verify_mismatch_never_grants_purchase(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")
        payment = _get_payment(app, reference)
        result = _success_result(payment, amount=999999)  # amount mismatch
        body = _charge_success_body(reference)

        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = _post_signed(client, body)
        assert resp.status_code == 200
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_transient_verify_failure_returns_retryable_non_2xx(self, client, app, user1_token, protected_root):
        from app.services.paystack import PaystackAPIError

        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)
        body = _charge_success_body(reference)

        with patch("app.services.resource_payments.verify_transaction", side_effect=PaystackAPIError("boom")):
            resp = _post_signed(client, body)
        assert resp.status_code == 502
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_not_yet_confirmed_returns_503(self, client, app, user1_token, protected_root):
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _, reference = _make_payment(app, user_id, resource_id)
        payment = _get_payment(app, reference)
        result = _success_result(payment, status="pending")
        body = _charge_success_body(reference)

        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = _post_signed(client, body)
        assert resp.status_code == 503
        assert _count_purchases_for(app, user_id, resource_id) == 0

    def test_failed_recovery_only_through_trusted_webhook(self, client, app, user1_token, protected_root):
        """A `failed` ResourcePayment may be reopened by a trusted,
        signature-verified charge.success delivery (mirrors Circle's
        identical webhook-recovery policy) — never by an ordinary
        request.
        """
        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, reference = _make_payment(
            app, user_id, resource_id, amount_subunits=150000, currency="KES", status="failed",
        )
        payment = _get_payment(app, reference)
        result = _success_result(payment)
        body = _charge_success_body(reference)

        with patch("app.services.resource_payments.verify_transaction", return_value=result):
            resp = _post_signed(client, body)
        assert resp.status_code == 200
        assert _count_purchases_for(app, user_id, resource_id) == 1


class TestSharedWebhookDispatchBothDomains:
    """Proves the one Paystack webhook endpoint correctly routes a
    Circle reference to Circle processing and a Resource reference to
    Resource processing within the SAME test run — not just that each
    domain works in isolation (see the two single-domain suites above
    and the pre-existing test_circle_webhooks.py).
    """

    def _make_plan(self, app, **overrides):
        from app.extensions import db
        from app.models.circle import CirclePlan

        defaults = dict(
            slug=f"webhookdispatch-plan-{uuid.uuid4().hex[:10]}", name="WSF Circle Membership",
            billing_interval="monthly", price=1000, currency="KES", status="active",
        )
        defaults.update(overrides)
        with app.app_context():
            plan = CirclePlan(**defaults)
            db.session.add(plan)
            db.session.commit()
            return plan.id

    def _make_circle_payment(self, app, user_id, plan_id, **overrides):
        from app.extensions import db
        from app.models.circle import CirclePayment

        defaults = dict(
            reference=overrides.pop("reference", None) or f"wsfcircle-{uuid.uuid4().hex}",
            user_id=user_id, plan_id=plan_id, amount_subunits=100000, currency="KES",
            billing_interval="monthly", customer_email=USER1["email"], status="pending",
        )
        defaults.update(overrides)
        with app.app_context():
            payment = CirclePayment(**defaults)
            db.session.add(payment)
            db.session.commit()
            return payment.reference

    def test_circle_and_resource_references_each_route_correctly(self, client, app, user1_token, protected_root):
        from app.models.circle import CirclePayment

        _enable_paystack(app)
        user_id = _get_user_id(app, USER1["email"])

        plan_id = self._make_plan(app)
        circle_reference = self._make_circle_payment(app, user_id, plan_id, amount_subunits=100000, currency="KES")

        resource_id, _ = _make_premium_resource(app, protected_root, price=1500, currency="KES")
        _, resource_reference = _make_payment(app, user_id, resource_id, amount_subunits=150000, currency="KES")

        with app.app_context():
            circle_payment_row = CirclePayment.query.filter_by(reference=circle_reference).one()
        circle_result = {
            "status": "success", "amount": 100000, "currency": "KES", "customer_email": USER1["email"],
            "provider_transaction_id": "111", "channel": "card", "paid_at": "2026-10-14T12:00:00.000Z",
            "gateway_response": "Successful", "reference": circle_reference,
        }
        resource_payment_row = _get_payment(app, resource_reference)
        resource_result = _success_result(resource_payment_row)

        with patch("app.services.circle_payments.verify_transaction", return_value=circle_result):
            circle_resp = _post_signed(client, _charge_success_body(circle_reference))
        with patch("app.services.resource_payments.verify_transaction", return_value=resource_result):
            resource_resp = _post_signed(client, _charge_success_body(resource_reference))

        assert circle_resp.status_code == 200
        assert resource_resp.status_code == 200

        from app.services.circle import has_circle_access
        with app.app_context():
            from app.extensions import db
            from app.models.user import User

            user = db.session.get(User, user_id)
            assert has_circle_access(user) is True
        assert _count_purchases_for(app, user_id, resource_id) == 1
