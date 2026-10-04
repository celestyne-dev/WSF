"""Focused tests for WSF Circle — the provider-neutral premium membership
foundation. See app/models/circle.py (CirclePlan/CircleSubscription),
app/services/circle.py (the one entitlement rule), and
app/api/v1/circle.py (public plans, /circle/me, admin plan/subscription
management).
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

USER1 = {
    "email": "circle-user1@example.com", "password": "supersecret1",
    "first_name": "Amina", "last_name": "Diallo", "country_code": "KE",
}
USER2 = {
    "email": "circle-user2@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "NG",
}
MANAGER_PAYLOAD = {
    "email": "circle-manager@example.com", "password": "supersecret1",
    "first_name": "Diana", "last_name": "Kioko", "country_code": "KE",
}
ADMIN_PAYLOAD = {
    "email": "circle-admin@example.com", "password": "supersecret1",
    "first_name": "Site", "last_name": "Admin", "country_code": "US",
}
AUTHOR_PAYLOAD = {
    "email": "circle-author@example.com", "password": "supersecret1",
    "first_name": "A", "last_name": "Uthor", "country_code": "US",
}
EMPLOYER_PAYLOAD = {
    "email": "circle-employer@example.com", "password": "supersecret1",
    "first_name": "Em", "last_name": "Ployer", "country_code": "US",
}
NO_PERMISSION_PAYLOAD = {
    "email": "circle-nobody@example.com", "password": "supersecret1",
    "first_name": "No", "last_name": "Permission", "country_code": "US",
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
    return _register_with_role(client, app, MANAGER_PAYLOAD, "community_manager")


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


@pytest.fixture()
def author_token(client, app):
    return _register_with_role(client, app, AUTHOR_PAYLOAD, "author")


@pytest.fixture()
def employer_token(client, app):
    return _register_with_role(client, app, EMPLOYER_PAYLOAD, "employer")


@pytest.fixture()
def no_permission_token(client):
    return _register(client, NO_PERMISSION_PAYLOAD)


def _iso(dt):
    return dt.isoformat()


def _now():
    return datetime.now(timezone.utc)


def _plan_payload(**overrides):
    payload = {
        "name": "WSF Circle Membership",
        "billingInterval": "monthly",
        "price": 1000,
        "currency": "USD",
        "status": "active",
    }
    payload.update(overrides)
    return payload


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


def _get_user(app, email):
    from app.models.user import User

    with app.app_context():
        return User.query.filter_by(email=email).first()


def _make_subscription(app, user_email, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        user = _resolve_user(email=user_email)
        defaults = dict(user_id=user.id, plan_id=plan_id, status="active", source="manual")
        defaults.update(overrides)
        subscription = CircleSubscription(**defaults)
        db.session.add(subscription)
        db.session.commit()
        return subscription.id


def _resolve_user(email):
    from app.models.user import User

    return User.query.filter_by(email=email).first()


def _get_subscription(app, subscription_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        return db.session.get(CircleSubscription, subscription_id)


class TestPlans:
    # 1. admin with circle.manage can create plan
    def test_manager_can_create_plan(self, client, manager_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(), headers=auth_headers(manager_token))
        assert resp.status_code == 201
        assert resp.get_json()["data"]["status"] == "active"

    # 2. unauthorized user cannot create/edit plan
    def test_unauthorized_cannot_create_or_edit_plan(self, client, app, no_permission_token, manager_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(), headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

        _, slug = _make_plan(app)
        edit = client.patch(f"/api/v1/circle/plans/{slug}", json={"name": "Hacked"}, headers=auth_headers(no_permission_token))
        assert edit.status_code == 403

    # 3. active plans public
    def test_active_plans_are_public(self, app, client):
        _make_plan(app, status="active", name="Visible Plan")
        resp = client.get("/api/v1/circle/plans")
        assert resp.status_code == 200
        names = [p["name"] for p in resp.get_json()["data"]]
        assert "Visible Plan" in names

    # 4. draft plans hidden
    def test_draft_plans_hidden_from_public(self, app, client):
        _, slug = _make_plan(app, status="draft", name="Draft Plan")
        listing = client.get("/api/v1/circle/plans").get_json()["data"]
        assert "Draft Plan" not in [p["name"] for p in listing]
        detail = client.get(f"/api/v1/circle/plans/{slug}")
        assert detail.status_code == 404

    # 5. archived plans hidden
    def test_archived_plans_hidden_from_public(self, app, client):
        _, slug = _make_plan(app, status="archived", name="Archived Plan")
        listing = client.get("/api/v1/circle/plans").get_json()["data"]
        assert "Archived Plan" not in [p["name"] for p in listing]
        detail = client.get(f"/api/v1/circle/plans/{slug}")
        assert detail.status_code == 404

    # 6. invalid currency rejected
    @pytest.mark.parametrize("currency", ["us", "USDOLLAR", "U$D", "usd"])
    def test_invalid_currency_rejected(self, client, manager_token, currency):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(currency=currency), headers=auth_headers(manager_token))
        assert resp.status_code == 422

    # 7. negative price rejected
    def test_negative_price_rejected(self, client, manager_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(price=-10), headers=auth_headers(manager_token))
        assert resp.status_code == 422

    # 8. unsafe checkout URL rejected
    @pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,hi", "file:///etc/passwd"])
    def test_unsafe_checkout_url_rejected(self, client, manager_token, url):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(checkoutUrl=url), headers=auth_headers(manager_token))
        assert resp.status_code == 422

    # 9. referenced plan cannot be deleted
    def test_referenced_plan_cannot_be_deleted(self, client, app, manager_token, user1_token):
        plan_id, slug = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        resp = client.delete(f"/api/v1/circle/plans/{slug}", headers=auth_headers(manager_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "reference_conflict"

    # 10. plan archive preserves subscriptions
    def test_plan_archive_preserves_subscriptions(self, client, app, manager_token, user1_token):
        plan_id, slug = _make_plan(app)
        sub_id = _make_subscription(app, USER1["email"], plan_id, status="active")
        resp = client.patch(f"/api/v1/circle/plans/{slug}", json={"status": "archived"}, headers=auth_headers(manager_token))
        assert resp.status_code == 200
        subscription = _get_subscription(app, sub_id)
        assert subscription is not None
        assert subscription.plan_id == plan_id


class TestSubscriptionRecording:
    # 11. admin can record subscription for existing exact-email User
    def test_admin_can_record_subscription(self, client, app, manager_token, user1_token):
        plan_id, _ = _make_plan(app)
        resp = client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "status": "active", "source": "manual"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["status"] == "active"

    # 12. unknown User email rejected
    def test_unknown_email_rejected(self, client, app, manager_token):
        plan_id, _ = _make_plan(app)
        resp = client.post(
            "/api/v1/circle/subscriptions",
            json={"email": "nobody-here@example.com", "planId": plan_id, "source": "manual"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "no_matching_account"

    # 13. recording subscription does not create a User
    def test_recording_subscription_does_not_create_user(self, client, app, manager_token, user1_token):
        from app.models.user import User

        plan_id, _ = _make_plan(app)
        with app.app_context():
            before = User.query.count()
        client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "source": "manual"},
            headers=auth_headers(manager_token),
        )
        with app.app_context():
            assert User.query.count() == before

    # 14. recording subscription does not create a Community Member
    def test_recording_subscription_does_not_create_member(self, client, app, manager_token, user1_token):
        from app.models.community import Member

        plan_id, _ = _make_plan(app)
        client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "source": "manual"},
            headers=auth_headers(manager_token),
        )
        with app.app_context():
            assert Member.query.count() == 0

    # 15. recording subscription does not change Community membership_type
    def test_recording_subscription_does_not_change_membership_type(self, client, app, manager_token, user1_token):
        from app.extensions import db
        from app.models.community import Member

        plan_id, _ = _make_plan(app)
        user = _get_user(app, USER1["email"])
        with app.app_context():
            member = Member(
                first_name="Amina", last_name="Diallo", email=USER1["email"],
                user_id=user.id, status="active", membership_type="Premium Member",
            )
            db.session.add(member)
            db.session.commit()

        client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "status": "active", "source": "manual"},
            headers=auth_headers(manager_token),
        )
        with app.app_context():
            reloaded = Member.query.filter_by(email=USER1["email"]).first()
            assert reloaded.membership_type == "Premium Member"


class TestEntitlement:
    # 16. pending does not grant access
    def test_pending_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="pending")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 17. active subscription grants access
    def test_active_grants_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is True

    # 18. future starts_at does not grant access
    def test_future_starts_at_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active", starts_at=_now() + timedelta(days=5))
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 19. expired current_period_end does not grant access
    def test_expired_period_end_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active", current_period_end=_now() - timedelta(days=1))
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 20. past_due does not grant access
    def test_past_due_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="past_due")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 21. cancelled does not grant access
    def test_cancelled_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="cancelled")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 22. expired does not grant access
    def test_expired_status_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="expired")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 23. revoked does not grant access
    def test_revoked_no_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="revoked")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is False

    # 24. active + cancel_at_period_end + future period end still grants access
    def test_cancel_at_period_end_with_future_end_grants_access(self, app, user1_token):
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(
            app, USER1["email"], plan_id, status="active",
            cancel_at_period_end=True, current_period_end=_now() + timedelta(days=10),
        )
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert has_circle_access(user) is True

    # 25. inactive User account does not get access
    def test_inactive_account_no_access(self, app, user1_token):
        from app.extensions import db
        from app.services.circle import has_circle_access

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            user.is_active = False
            db.session.commit()
            assert has_circle_access(user) is False

    # 26. user cannot have two current subscriptions simultaneously
    def test_no_two_current_subscriptions(self, client, app, manager_token, user1_token):
        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="pending")
        resp = client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "status": "active", "source": "manual"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "current_subscription_exists"

    # 27. historical terminal subscriptions can coexist
    def test_historical_terminal_subscriptions_coexist(self, app, user1_token):
        from app.extensions import db
        from app.models.circle import CircleSubscription

        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="cancelled")
        _make_subscription(app, USER1["email"], plan_id, status="expired")
        with app.app_context():
            user = _resolve_user(USER1["email"])
            assert CircleSubscription.query.filter_by(user_id=user.id).count() == 2

    # 28. valid new cycle can be created after terminal prior subscription
    def test_new_cycle_after_terminal(self, client, app, manager_token, user1_token):
        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="cancelled")
        resp = client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "status": "pending", "source": "manual"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201

    # 29. invalid state transition rejected
    def test_invalid_state_transition_rejected(self, client, app, manager_token, user1_token):
        plan_id, _ = _make_plan(app)
        sub_id = _make_subscription(app, USER1["email"], plan_id, status="cancelled")
        resp = client.patch(
            f"/api/v1/circle/subscriptions/{sub_id}", json={"status": "active"}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_status_transition"

    # 30. provider/reference metadata stays admin-only (positively present in admin dump)
    def test_provider_metadata_visible_to_admin(self, client, app, manager_token, user1_token):
        plan_id, _ = _make_plan(app)
        sub_id = _make_subscription(
            app, USER1["email"], plan_id, status="active",
            provider="stripe-placeholder", provider_customer_id="cus_123",
            provider_subscription_id="sub_123", payment_reference="ref-123",
        )
        resp = client.get(f"/api/v1/circle/subscriptions/{sub_id}", headers=auth_headers(manager_token))
        data = resp.get_json()["data"]
        assert data["provider_customer_id"] == "cus_123"
        assert data["provider_subscription_id"] == "sub_123"
        assert data["payment_reference"] == "ref-123"


class TestOwnerApi:
    # 31. /circle/me is owner-scoped; 33. no membership returns hasAccess=false safely
    def test_circle_me_no_membership(self, client, user1_token):
        resp = client.get("/api/v1/circle/me", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["hasAccess"] is False
        assert data["subscription"] is None

    # 32. another User cannot see another subscription
    def test_circle_me_scoped_per_user(self, client, app, user1_token, user2_token):
        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")

        mine = client.get("/api/v1/circle/me", headers=auth_headers(user1_token)).get_json()["data"]
        assert mine["hasAccess"] is True

        hers = client.get("/api/v1/circle/me", headers=auth_headers(user2_token)).get_json()["data"]
        assert hers["hasAccess"] is False
        assert hers["subscription"] is None

    # 34. active owner response contains safe plan/status/date info
    def test_owner_response_active_contains_safe_info(self, client, app, user1_token):
        plan_id, slug = _make_plan(app, name="Owner View Plan")
        end = _now() + timedelta(days=30)
        _make_subscription(app, USER1["email"], plan_id, status="active", current_period_end=end)
        resp = client.get("/api/v1/circle/me", headers=auth_headers(user1_token))
        sub = resp.get_json()["data"]["subscription"]
        assert sub["status"] == "active"
        assert sub["plan"]["slug"] == slug
        assert sub["plan"]["name"] == "Owner View Plan"
        assert sub["currentPeriodEnd"] is not None

    # 35,36,37. owner response excludes provider customer/subscription ids and payment reference
    def test_owner_response_excludes_provider_internals(self, client, app, user1_token):
        plan_id, _ = _make_plan(app)
        _make_subscription(
            app, USER1["email"], plan_id, status="active",
            provider_customer_id="cus_secret", provider_subscription_id="sub_secret", payment_reference="ref_secret",
        )
        resp = client.get("/api/v1/circle/me", headers=auth_headers(user1_token))
        body = str(resp.get_json())
        assert "cus_secret" not in body
        assert "sub_secret" not in body
        assert "ref_secret" not in body


class TestCommunitySeparation:
    # 38. Community Member "Premium Member" does NOT grant Circle access
    def test_premium_member_designation_does_not_grant_access(self, client, app, user1_token):
        from app.extensions import db
        from app.models.community import Member
        from app.services.circle import has_circle_access

        user = _get_user(app, USER1["email"])
        with app.app_context():
            db.session.add(Member(
                first_name="Amina", last_name="Diallo", email=USER1["email"],
                user_id=user.id, status="active", membership_type="Premium Member",
            ))
            db.session.commit()
            reloaded_user = _resolve_user(USER1["email"])
            assert has_circle_access(reloaded_user) is False

    # 39,40. active Circle subscription never mutates or auto-creates Member
    def test_active_subscription_never_touches_member(self, client, app, manager_token, user1_token):
        from app.models.community import Member

        plan_id, _ = _make_plan(app)
        client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "status": "active", "source": "manual"},
            headers=auth_headers(manager_token),
        )
        with app.app_context():
            assert Member.query.count() == 0

    # 41. Circle cancellation does not change Community Member
    def test_cancellation_does_not_change_member(self, client, app, manager_token, user1_token):
        from app.extensions import db
        from app.models.community import Member

        user = _get_user(app, USER1["email"])
        plan_id, _ = _make_plan(app)
        sub_id = _make_subscription(app, USER1["email"], plan_id, status="active")
        with app.app_context():
            db.session.add(Member(
                first_name="Amina", last_name="Diallo", email=USER1["email"],
                user_id=user.id, status="active", membership_type="Community Member",
            ))
            db.session.commit()

        client.patch(f"/api/v1/circle/subscriptions/{sub_id}", json={"status": "cancelled"}, headers=auth_headers(manager_token))

        with app.app_context():
            member = Member.query.filter_by(email=USER1["email"]).first()
            assert member.status == "active"
            assert member.membership_type == "Community Member"


class TestProductOrderSeparation:
    # 42. Product purchase/order does not grant Circle entitlement
    def test_order_does_not_grant_circle_access(self, app, user1_token):
        from app.extensions import db
        from app.models.commerce import Order
        from app.services.circle import has_circle_access

        user = _get_user(app, USER1["email"])
        with app.app_context():
            db.session.add(Order(user_id=user.id, email=USER1["email"], total_amount=5000, payment_status="paid", order_status="completed"))
            db.session.commit()
            reloaded_user = _resolve_user(USER1["email"])
            assert has_circle_access(reloaded_user) is False

    # 43. Circle subscription creation does not create an Order
    def test_subscription_creation_does_not_create_order(self, client, app, manager_token, user1_token):
        from app.models.commerce import Order

        plan_id, _ = _make_plan(app)
        client.post(
            "/api/v1/circle/subscriptions",
            json={"email": USER1["email"], "planId": plan_id, "status": "active", "source": "manual"},
            headers=auth_headers(manager_token),
        )
        with app.app_context():
            assert Order.query.count() == 0

    # 44. Circle status change does not mutate an unrelated Order
    def test_status_change_does_not_mutate_order(self, client, app, manager_token, user1_token):
        from app.extensions import db
        from app.models.commerce import Order

        user = _get_user(app, USER1["email"])
        plan_id, _ = _make_plan(app)
        sub_id = _make_subscription(app, USER1["email"], plan_id, status="active")
        with app.app_context():
            order = Order(user_id=user.id, email=USER1["email"], total_amount=100, order_status="pending", payment_status="pending")
            db.session.add(order)
            db.session.commit()
            order_id = order.id

        client.patch(f"/api/v1/circle/subscriptions/{sub_id}", json={"status": "cancelled"}, headers=auth_headers(manager_token))

        with app.app_context():
            reloaded = db.session.get(Order, order_id)
            assert reloaded.order_status == "pending"
            assert reloaded.payment_status == "pending"


class TestAdminRbac:
    # 45. community_manager receives circle.manage
    def test_community_manager_has_circle_manage(self, client, app, manager_token):
        plan_id, _ = _make_plan(app)
        resp = client.post(
            "/api/v1/circle/subscriptions",
            json={"email": "nope@example.com", "planId": plan_id, "source": "manual"},
            headers=auth_headers(manager_token),
        )
        assert resp.status_code != 403  # reaches business logic (404 no_matching_account), not RBAC-denied

    # 46,47,48. ordinary member/author/employer do not receive circle.manage
    def test_ordinary_member_lacks_circle_manage(self, client, no_permission_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(), headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_author_lacks_circle_manage(self, client, author_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(), headers=auth_headers(author_token))
        assert resp.status_code == 403

    def test_employer_lacks_circle_manage(self, client, employer_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(), headers=auth_headers(employer_token))
        assert resp.status_code == 403

    # 49. admin has circle.manage
    def test_admin_has_circle_manage(self, client, admin_token):
        resp = client.post("/api/v1/circle/plans", json=_plan_payload(), headers=auth_headers(admin_token))
        assert resp.status_code == 201

    # 50. admin list/search/filter works
    def test_admin_list_search_filter(self, client, app, manager_token, user1_token, user2_token):
        plan_id, _ = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        _make_subscription(app, USER2["email"], plan_id, status="pending")

        all_rows = client.get("/api/v1/circle/subscriptions", headers=auth_headers(manager_token)).get_json()["data"]
        assert len(all_rows) == 2

        filtered = client.get("/api/v1/circle/subscriptions?status=pending", headers=auth_headers(manager_token)).get_json()["data"]
        assert len(filtered) == 1
        assert filtered[0]["status"] == "pending"

        searched = client.get(f"/api/v1/circle/subscriptions?q={USER1['email']}", headers=auth_headers(manager_token)).get_json()["data"]
        assert len(searched) == 1

    # 51. audit entries created for material subscription status changes
    def test_audit_entries_for_status_change(self, client, app, manager_token, user1_token):
        from app.models.audit import AuditLog

        plan_id, _ = _make_plan(app)
        sub_id = _make_subscription(app, USER1["email"], plan_id, status="pending")
        client.patch(f"/api/v1/circle/subscriptions/{sub_id}", json={"status": "active"}, headers=auth_headers(manager_token))
        with app.app_context():
            entries = AuditLog.query.filter_by(action="circle_subscription.status_change", entity_id=str(sub_id)).all()
            assert len(entries) == 1
            assert entries[0].changes == {"from": "pending", "to": "active"}


class TestAuth:
    # 52. inactive account owner endpoint rejected appropriately
    def test_inactive_account_owner_endpoint_rejected(self, client, app, user1_token):
        from app.extensions import db

        with app.app_context():
            user = _resolve_user(USER1["email"])
            user.is_active = False
            db.session.commit()
        resp = client.get("/api/v1/circle/me", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 53. must_change_password enforcement remains consistent
    def test_must_change_password_blocks_circle_me(self, client, app, user1_token):
        from app.extensions import db

        with app.app_context():
            user = _resolve_user(USER1["email"])
            user.must_change_password = True
            db.session.commit()
        resp = client.get("/api/v1/circle/me", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "password_change_required"


class TestRegressions:
    # 54. /community/me still works
    def test_community_me_still_works(self, client, user1_token):
        resp = client.get("/api/v1/community/me", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["joined"] is False

    # 55. account registration still does not create Member or Circle subscription
    def test_registration_does_not_create_member_or_subscription(self, client, app, user1_token):
        from app.models.circle import CircleSubscription
        from app.models.community import Member

        with app.app_context():
            assert Member.query.filter_by(email=USER1["email"]).first() is None
            user = _resolve_user(USER1["email"])
            assert CircleSubscription.query.filter_by(user_id=user.id).count() == 0

    # 56. My Community behavior remains intact
    def test_my_community_join_still_works(self, client, user1_token):
        resp = client.post("/api/v1/community/me/join", json={"consentGiven": True}, headers=auth_headers(user1_token))
        assert resp.status_code == 201
        assert resp.get_json()["data"]["status"] == "active"

    # 57. Saved remains intact
    def test_saved_items_still_works(self, client, user1_token):
        resp = client.get("/api/v1/saved", headers=auth_headers(user1_token))
        assert resp.status_code == 200

    # 58. Event registration remains intact
    def test_event_registrations_still_works(self, client, user1_token):
        resp = client.get("/api/v1/event-registrations/me", headers=auth_headers(user1_token))
        assert resp.status_code == 200

    # 59. Learning enrollment remains intact
    def test_learning_enrollments_still_works(self, client, user1_token):
        resp = client.get("/api/v1/learning-enrollments/me", headers=auth_headers(user1_token))
        assert resp.status_code == 200
