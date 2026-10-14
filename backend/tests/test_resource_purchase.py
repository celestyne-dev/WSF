"""Stage 1 of the premium-Resource Paystack integration: ResourcePurchase/
ResourcePayment model invariants, premium access-type entitlement (see
app/services/resource_access.py's check_resource_access), premium publish
validation (app/api/v1/resources.py's _validate_publish), the protected-
download path once entitlement exists, and Resource deletion protection
for paid content. No checkout/Paystack call happens in this file — see
test_resource_checkout.py for that; this file is about the entitlement
and data-integrity layer underneath it.
"""
import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from tests.conftest import auth_headers

USER1 = {
    "email": "respurchase-user1@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Diallo", "country_code": "KE",
}
USER2 = {
    "email": "respurchase-user2@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "NG",
}
MANAGER_PAYLOAD = {
    "email": "respurchase-manager@example.com", "password": "supersecret1",
    "first_name": "Diana", "last_name": "Kioko", "country_code": "KE",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


def _register_with_role(client, app, payload, role_name):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        role = Role.query.filter_by(name=role_name).first()
        user.roles.append(role)
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user1_token(client):
    return _register(client, USER1)


@pytest.fixture()
def user2_token(client):
    return _register(client, USER2)


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "resources_manager")


@pytest.fixture()
def protected_root(app, tmp_path):
    root = tmp_path / "protected_media"
    root.mkdir()
    app.config["PROTECTED_MEDIA_ROOT"] = str(root)
    return root


def _get_user(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first()


def _get_user_id(app, email):
    return _get_user(app, email).id


def _slug(prefix="premium-resource"):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _make_premium_resource(app, protected_root, filename=None, content=b"%PDF-1.4 fake pdf body", **overrides):
    """A published premium Resource whose real file is written to
    `protected_root` (never MEDIA_ROOT) — the exact shape
    _validate_publish() now requires for premium (see
    app/api/v1/resources.py). `price`/`currency` default to a real,
    payable commercial record.
    """
    from app.extensions import db
    from app.models.resource import Resource

    filename = filename or f"{uuid.uuid4().hex}.pdf"
    (protected_root / filename).write_bytes(content)
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


def _get_resource(app, resource_id):
    from app.extensions import db
    from app.models.resource import Resource

    with app.app_context():
        return db.session.get(Resource, resource_id)


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
        return payment.id


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


def _make_active_circle_subscription(app, user_id, plan_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        sub = CircleSubscription(user_id=user_id, plan_id=plan_id, status="active", source="manual")
        db.session.add(sub)
        db.session.commit()
        return sub.id


class TestResourcePurchaseModel:
    def test_create_minimal_purchase(self, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        purchase_id = _make_purchase(app, user_id, resource_id)

        from app.models.resource import ResourcePurchase

        with app.app_context():
            purchase = ResourcePurchase.query.get(purchase_id)
            assert purchase.status == "active"
            assert purchase.user_id == user_id
            assert purchase.resource_id == resource_id

    def test_one_active_purchase_per_user_resource_enforced(self, app, user1_token, protected_root):
        from app.extensions import db
        from app.models.resource import ResourcePurchase

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource_id)

        with app.app_context():
            dupe = ResourcePurchase(user_id=user_id, resource_id=resource_id, status="active")
            db.session.add(dupe)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_different_users_may_each_purchase_the_same_resource(self, app, user1_token, user2_token, protected_root):
        user1_id = _get_user_id(app, USER1["email"])
        user2_id = _get_user_id(app, USER2["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _make_purchase(app, user1_id, resource_id)
        _make_purchase(app, user2_id, resource_id)  # must not raise

    def test_same_user_may_purchase_different_resources(self, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource1_id, _ = _make_premium_resource(app, protected_root)
        resource2_id, _ = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource1_id)
        _make_purchase(app, user_id, resource2_id)  # must not raise


class TestResourcePaymentModel:
    def test_create_minimal_payment(self, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        payment_id = _make_payment(app, user_id, resource_id)

        from app.models.resource import ResourcePayment

        with app.app_context():
            payment = ResourcePayment.query.get(payment_id)
            assert payment.status == "pending"
            assert payment.provider == "paystack"
            assert payment.purchase_id is None

    def test_reference_uniqueness(self, app, user1_token, protected_root):
        from app.extensions import db
        from app.models.resource import ResourcePayment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        shared_reference = f"wsfresource-{uuid.uuid4().hex}"
        _make_payment(app, user_id, resource_id, reference=shared_reference)

        with app.app_context():
            dupe = ResourcePayment(
                reference=shared_reference, user_id=user_id, resource_id=resource_id,
                amount_subunits=150000, currency="KES", customer_email=USER1["email"], status="pending",
            )
            db.session.add(dupe)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_amount_must_be_positive(self, app, user1_token, protected_root):
        from app.extensions import db
        from app.models.resource import ResourcePayment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        with app.app_context():
            payment = ResourcePayment(
                reference=f"wsfresource-{uuid.uuid4().hex}", user_id=user_id, resource_id=resource_id,
                amount_subunits=0, currency="KES", customer_email=USER1["email"], status="pending",
            )
            db.session.add(payment)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_provider_transaction_id_uniqueness(self, app, user1_token, protected_root):
        from app.extensions import db
        from app.models.resource import ResourcePayment

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _make_payment(app, user_id, resource_id, provider_transaction_id="999111")

        with app.app_context():
            dupe = ResourcePayment(
                reference=f"wsfresource-{uuid.uuid4().hex}", user_id=user_id, resource_id=resource_id,
                amount_subunits=150000, currency="KES", customer_email=USER1["email"], status="pending",
                provider_transaction_id="999111",
            )
            db.session.add(dupe)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_multiple_null_provider_transaction_ids_allowed(self, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _make_payment(app, user_id, resource_id)
        _make_payment(app, user_id, resource_id)  # both NULL — must not raise


class TestPremiumAccessEntitlement:
    def test_anonymous_denied_account_required(self, client, protected_root, app):
        _, slug = _make_premium_resource(app, protected_root)
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "account_required"

    def test_signed_in_without_purchase_denied(self, client, app, user1_token, protected_root):
        _, slug = _make_premium_resource(app, protected_root)
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "purchase_required"

    def test_signed_in_with_purchase_allowed(self, client, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource_id)

        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert body["accessType"] == "premium"
        assert body["url"].startswith("/api/v1/resources/downloads/")

    def test_circle_membership_alone_does_not_unlock_premium(self, client, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        plan_id = _make_plan(app)
        _make_active_circle_subscription(app, user_id, plan_id)
        _, slug = _make_premium_resource(app, protected_root)

        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "purchase_required"

    def test_purchasing_premium_never_grants_circle(self, app, user1_token, protected_root):
        from app.services.circle import has_circle_access

        user_id = _get_user_id(app, USER1["email"])
        resource_id, _ = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource_id)

        with app.app_context():
            from app.extensions import db
            from app.models.user import User

            user = db.session.get(User, user_id)
            assert has_circle_access(user) is False

    def test_successful_access_issues_token_that_streams_protected_file(self, client, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        content = b"%PDF-1.4 the real premium workbook body"
        resource_id, slug = _make_premium_resource(app, protected_root, content=content)
        _make_purchase(app, user_id, resource_id)

        access_resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert access_resp.status_code == 200
        url = access_resp.get_json()["data"]["url"]

        download_resp = client.get(url)
        assert download_resp.status_code == 200
        assert download_resp.data == content

    def test_download_url_never_leaks_raw_protected_path(self, client, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        filename = f"{uuid.uuid4().hex}.pdf"
        resource_id, slug = _make_premium_resource(app, protected_root, filename=filename)
        _make_purchase(app, user_id, resource_id)

        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        url = resp.get_json()["data"]["url"]
        assert filename not in url
        assert str(protected_root) not in url

    def test_viewer_can_access_hint_reflects_purchase(self, client, app, user1_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root)

        no_purchase = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(user1_token))
        assert no_purchase.get_json()["data"]["viewerCanAccess"] is False

        _make_purchase(app, user_id, resource_id)

        with_purchase = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(user1_token))
        assert with_purchase.get_json()["data"]["viewerCanAccess"] is True


class TestPremiumPublishValidation:
    def test_published_premium_with_zero_price_rejected(self, app, manager_token, client, protected_root):
        filename = f"{uuid.uuid4().hex}.pdf"
        (protected_root / filename).write_bytes(b"%PDF-1.4 x")
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "Zero Price Premium",
                "accessType": "premium",
                "price": 0,
                "currency": "KES",
                "protectedFilePath": filename,
                "description": [{"type": "paragraph", "text": "Body."}],
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_published_premium_without_protected_file_rejected(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "No File Premium",
                "accessType": "premium",
                "price": 1000,
                "currency": "KES",
                "description": [{"type": "paragraph", "text": "Body."}],
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_published_premium_with_missing_protected_file_rejected(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "Missing File Premium",
                "accessType": "premium",
                "price": 1000,
                "currency": "KES",
                "protectedFilePath": "does-not-exist.pdf",
                "description": [{"type": "paragraph", "text": "Body."}],
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_valid_premium_resource_with_protected_file_can_publish(self, client, manager_token, protected_root):
        filename = f"{uuid.uuid4().hex}.pdf"
        (protected_root / filename).write_bytes(b"%PDF-1.4 x")
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "Valid Premium Resource",
                "accessType": "premium",
                "price": 1000,
                "currency": "KES",
                "protectedFilePath": filename,
                "description": [{"type": "paragraph", "text": "Body."}],
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201

    def test_premium_cannot_publish_with_only_file_url(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "File URL Premium",
                "accessType": "premium",
                "price": 1000,
                "currency": "KES",
                "fileUrl": "https://cdn.example.com/premium.pdf",
                "description": [{"type": "paragraph", "text": "Body."}],
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    def test_draft_premium_without_file_is_fine(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "Draft Premium",
                "accessType": "premium",
                "price": 1000,
                "currency": "KES",
                "status": "draft",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201


class TestResourceDeletionProtection:
    def test_resource_with_purchase_history_cannot_be_hard_deleted(self, client, app, user1_token, manager_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root)
        _make_purchase(app, user_id, resource_id)

        resp = client.delete(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "reference_conflict"

    def test_resource_with_only_payment_history_cannot_be_hard_deleted(self, client, app, user1_token, manager_token, protected_root):
        user_id = _get_user_id(app, USER1["email"])
        resource_id, slug = _make_premium_resource(app, protected_root)
        _make_payment(app, user_id, resource_id)  # no purchase yet — payment alone still protects it

        resp = client.delete(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "reference_conflict"

    def test_resource_without_any_commercial_history_can_be_deleted(self, client, app, manager_token, protected_root):
        _, slug = _make_premium_resource(app, protected_root)
        resp = client.delete(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
        assert resp.status_code == 200
