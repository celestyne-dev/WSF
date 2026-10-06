"""Focused tests for secure Resource access + account/WSF Circle gating.
See app/models/resource.py (ACCESS_TYPES/is_publicly_visible),
app/services/resource_access.py (the one access_type rule evaluator),
app/services/circle.py (the one Circle entitlement rule, reused — never
re-derived), and app/api/v1/resources.py (public-safe serialization +
the one POST /access grant endpoint).
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

USER1 = {
    "email": "resaccess-user1@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Diallo", "country_code": "KE",
}
USER2 = {
    "email": "resaccess-user2@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "NG",
}
MANAGER_PAYLOAD = {
    "email": "resaccess-manager@example.com", "password": "supersecret1",
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


def _resolve_user(email):
    from app.models.user import User

    return User.query.filter_by(email=email).first()


def _get_user(app, email):
    with app.app_context():
        return _resolve_user(email)


def _now():
    return datetime.now(timezone.utc)


def _make_resource(app, **overrides):
    from app.extensions import db
    from app.models.resource import Resource

    defaults = dict(
        slug=overrides.pop("slug", None) or f"resource-{uuid.uuid4().hex[:10]}",
        name="Test Resource",
        access_type="direct_download",
        file_url="https://cdn.example.com/test-resource.pdf",
        status="published",
        published_date=date.today(),
        description=[{"type": "paragraph", "text": "Resource body."}],
        price=0,
        currency="USD",
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


def _make_plan(app, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePlan

    defaults = dict(
        slug=f"circle-plan-{uuid.uuid4().hex[:10]}",
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
        return plan.id


def _make_subscription(app, user_email, plan_id, **overrides):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        user = _resolve_user(user_email)
        defaults = dict(user_id=user.id, plan_id=plan_id, status="active", source="manual")
        defaults.update(overrides)
        subscription = CircleSubscription(**defaults)
        db.session.add(subscription)
        db.session.commit()
        return subscription.id


class TestPublicSerialization:
    # 1-2. anonymous list never exposes file_url/external_url
    def test_anonymous_list_excludes_raw_targets(self, app, client):
        _make_resource(app, access_type="external_link", file_url=None, external_url="https://example.com/off-site")
        listing = client.get("/api/v1/resources").get_json()["data"]
        for item in listing:
            assert "file_url" not in item and "fileUrl" not in item
            assert "external_url" not in item and "externalUrl" not in item

    # 3-4. anonymous detail never exposes file_url/external_url
    def test_anonymous_detail_excludes_raw_targets(self, app, client):
        _, slug = _make_resource(app, access_type="external_link", file_url=None, external_url="https://example.com/off-site")
        detail = client.get(f"/api/v1/resources/{slug}").get_json()["data"]
        assert "file_url" not in detail and "fileUrl" not in detail
        assert "external_url" not in detail and "externalUrl" not in detail

    # 5. ordinary authenticated account detail still excludes raw target
    def test_authenticated_ordinary_detail_excludes_raw_target(self, app, client, user1_token):
        _, slug = _make_resource(app)
        detail = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(user1_token)).get_json()["data"]
        assert "file_url" not in detail and "fileUrl" not in detail

    # 6. Circle member detail still excludes raw target
    def test_circle_member_detail_excludes_raw_target(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        _, slug = _make_resource(app, access_type="circle_only")
        detail = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(user1_token)).get_json()["data"]
        assert "file_url" not in detail and "fileUrl" not in detail

    # 7. resources.manage staff detail DOES retain target for editing
    def test_staff_detail_retains_raw_target(self, app, client, manager_token):
        _, slug = _make_resource(app)
        detail = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token)).get_json()["data"]
        assert detail["file_url"]


class TestVisibility:
    # 8. published resource access works
    def test_published_resource_access_works(self, app, client):
        _, slug = _make_resource(app, status="published")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 200

    # 9. scheduled with published_date today/past can be accessed
    def test_scheduled_past_date_accessible(self, app, client):
        _, slug = _make_resource(app, status="scheduled", published_date=date.today() - timedelta(days=1))
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 200

    # 10. future scheduled -> /access 404
    def test_future_scheduled_access_404(self, app, client):
        _, slug = _make_resource(app, status="scheduled", published_date=date.today() + timedelta(days=5))
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 404

    # 11. draft -> /access 404
    def test_draft_access_404(self, app, client):
        _, slug = _make_resource(app, status="draft")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 404

    # 12. review -> /access 404
    def test_review_access_404(self, app, client):
        _, slug = _make_resource(app, status="review")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 404

    # 13. archived -> /access 404
    def test_archived_access_404(self, app, client):
        _, slug = _make_resource(app, status="archived")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 404


class TestDirectDownload:
    # 14. anonymous direct_download succeeds
    def test_anonymous_direct_download_succeeds(self, app, client):
        _, slug = _make_resource(app, access_type="direct_download")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["url"]

    # 15. returned target comes only from /access
    def test_target_only_from_access(self, app, client):
        resource_id, slug = _make_resource(app, access_type="direct_download", file_url="https://cdn.example.com/only-here.pdf")
        detail = client.get(f"/api/v1/resources/{slug}").get_json()["data"]
        assert "fileUrl" not in detail
        access = client.post(f"/api/v1/resources/{slug}/access")
        assert access.get_json()["data"]["url"] == "https://cdn.example.com/only-here.pdf"

    # 16. successful direct access increments download_count
    def test_successful_access_increments_count(self, app, client):
        resource_id, slug = _make_resource(app)
        client.post(f"/api/v1/resources/{slug}/access")
        assert _get_resource(app, resource_id).download_count == 1

    # 17. missing target returns not_configured
    def test_missing_target_not_configured(self, app, client):
        _, slug = _make_resource(app, file_url=None, external_url=None)
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "not_configured"

    # 18. failed access does not increment count
    def test_failed_access_does_not_increment_count(self, app, client):
        resource_id, slug = _make_resource(app, file_url=None, external_url=None)
        client.post(f"/api/v1/resources/{slug}/access")
        assert _get_resource(app, resource_id).download_count == 0


class TestEmailGate:
    # 19. valid email gate succeeds
    def test_valid_email_gate_succeeds(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        resp = client.post(f"/api/v1/resources/{slug}/access", json={"email": "reader@example.com"})
        assert resp.status_code == 201
        assert resp.get_json()["data"]["url"]

    # 20. ResourceLead created
    def test_email_gate_creates_lead(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        client.post(f"/api/v1/resources/{slug}/access", json={"email": "leadcheck@example.com"})
        with app.app_context():
            from app.models.resource import ResourceLead

            assert ResourceLead.query.filter_by(email="leadcheck@example.com").first() is not None

    # 21. newsletter not subscribed without explicit consent
    def test_email_gate_no_consent_no_subscription(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        client.post(f"/api/v1/resources/{slug}/access", json={"email": "noconsent@example.com", "newsletterConsent": False})
        with app.app_context():
            from app.models.newsletter import NewsletterSubscriber

            assert NewsletterSubscriber.query.filter_by(email="noconsent@example.com").first() is None

    # 22. explicit consent still works
    def test_email_gate_explicit_consent_subscribes(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        client.post(f"/api/v1/resources/{slug}/access", json={"email": "consents@example.com", "newsletterConsent": True})
        with app.app_context():
            from app.models.newsletter import NewsletterSubscriber

            assert NewsletterSubscriber.query.filter_by(email="consents@example.com").first() is not None

    # 23. invalid email rejected
    def test_email_gate_invalid_email_rejected(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        resp = client.post(f"/api/v1/resources/{slug}/access", json={"email": "not-an-email"})
        assert resp.status_code == 422

    # 24. invalid gate does not increment download_count
    def test_email_gate_invalid_does_not_increment_count(self, app, client):
        resource_id, slug = _make_resource(app, access_type="email_gate")
        client.post(f"/api/v1/resources/{slug}/access", json={})
        assert _get_resource(app, resource_id).download_count == 0

    # 25. raw file target absent from initial detail response
    def test_email_gate_detail_excludes_target(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        detail = client.get(f"/api/v1/resources/{slug}").get_json()["data"]
        assert "fileUrl" not in detail
        assert detail["requiresEmail"] is True


class TestMemberOnly:
    # 26. anonymous -> 401 account_required
    def test_anonymous_member_only_rejected(self, app, client):
        _, slug = _make_resource(app, access_type="member_only")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "account_required"

    # 27. authenticated active User succeeds
    def test_authenticated_user_member_only_succeeds(self, app, client, user1_token):
        _, slug = _make_resource(app, access_type="member_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 200

    # 28. authenticated User does NOT need Community Member
    def test_member_only_does_not_require_community_member(self, app, client, user1_token):
        with app.app_context():
            from app.models.community import Member

            assert Member.query.filter_by(email=USER1["email"]).first() is None
        _, slug = _make_resource(app, access_type="member_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 200

    # 29. inactive User denied
    def test_inactive_user_member_only_denied(self, app, client, user1_token):
        with app.app_context():
            from app.extensions import db

            user = _resolve_user(USER1["email"])
            user.is_active = False
            db.session.commit()
        _, slug = _make_resource(app, access_type="member_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 30. must_change_password User denied with password_change_required
    def test_must_change_password_member_only_denied(self, app, client, user1_token):
        with app.app_context():
            from app.extensions import db

            user = _resolve_user(USER1["email"])
            user.must_change_password = True
            db.session.commit()
        _, slug = _make_resource(app, access_type="member_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "password_change_required"

    # 31. success increments count
    def test_member_only_success_increments_count(self, app, client, user1_token):
        resource_id, slug = _make_resource(app, access_type="member_only")
        client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert _get_resource(app, resource_id).download_count == 1

    # 32. denied attempt does not increment count
    def test_member_only_denied_does_not_increment_count(self, app, client):
        resource_id, slug = _make_resource(app, access_type="member_only")
        client.post(f"/api/v1/resources/{slug}/access")
        assert _get_resource(app, resource_id).download_count == 0


class TestCircleOnly:
    # 33. anonymous -> 401 account_required
    def test_anonymous_circle_only_rejected(self, app, client):
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "account_required"

    # 34. ordinary logged-in User -> 403 circle_required
    def test_ordinary_user_circle_only_rejected(self, app, client, user1_token):
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "circle_required"

    # 35. Community Member without Circle -> no access
    def test_community_member_without_circle_rejected(self, app, client, user1_token):
        with app.app_context():
            from app.extensions import db
            from app.models.community import Member

            user = _resolve_user(USER1["email"])
            member = Member(first_name="Amara", last_name="Diallo", email=USER1["email"], user_id=user.id, status="active")
            db.session.add(member)
            db.session.commit()
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "circle_required"

    # 36. Community membership_type "Premium Member" -> no Circle access
    def test_premium_member_designation_does_not_grant_circle(self, app, client, user1_token):
        with app.app_context():
            from app.extensions import db
            from app.models.community import Member

            user = _resolve_user(USER1["email"])
            member = Member(
                first_name="Amara", last_name="Diallo", email=USER1["email"], user_id=user.id,
                status="active", membership_type="Premium Member",
            )
            db.session.add(member)
            db.session.commit()
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "circle_required"

    # 37. pending Circle subscription -> no access
    def test_pending_circle_subscription_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="pending")
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 38. past_due -> no access
    def test_past_due_circle_subscription_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="past_due")
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 39. cancelled -> no access
    def test_cancelled_circle_subscription_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="cancelled")
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 40. expired -> no access
    def test_expired_circle_subscription_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="expired")
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 41. revoked -> no access
    def test_revoked_circle_subscription_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="revoked")
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 42. active but future starts_at -> no access
    def test_active_future_starts_at_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active", starts_at=_now() + timedelta(days=5))
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 43. active but expired period_end -> no access
    def test_active_expired_period_end_no_access(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active", current_period_end=_now() - timedelta(days=1))
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403

    # 44. valid active Circle subscription -> succeeds
    def test_active_circle_subscription_succeeds(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["url"]

    # 45. active cancel_at_period_end with future period end -> succeeds
    def test_cancel_at_period_end_with_future_end_succeeds(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(
            app, USER1["email"], plan_id, status="active",
            cancel_at_period_end=True, current_period_end=_now() + timedelta(days=10),
        )
        _, slug = _make_resource(app, access_type="circle_only")
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 200

    # 46. successful Circle access increments count
    def test_circle_success_increments_count(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        resource_id, slug = _make_resource(app, access_type="circle_only")
        client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert _get_resource(app, resource_id).download_count == 1

    # 47. denied Circle attempt does not increment count
    def test_circle_denied_does_not_increment_count(self, app, client, user1_token):
        resource_id, slug = _make_resource(app, access_type="circle_only")
        client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert _get_resource(app, resource_id).download_count == 0

    # 48. Circle access does not modify Community Member
    def test_circle_access_does_not_touch_member(self, app, client, user1_token):
        with app.app_context():
            from app.extensions import db
            from app.models.community import Member

            user = _resolve_user(USER1["email"])
            member = Member(
                first_name="Amara", last_name="Diallo", email=USER1["email"], user_id=user.id,
                status="active", membership_type="Community Member",
            )
            db.session.add(member)
            db.session.commit()
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        _, slug = _make_resource(app, access_type="circle_only")
        client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        with app.app_context():
            from app.models.community import Member

            reloaded = Member.query.filter_by(email=USER1["email"]).first()
            assert reloaded.membership_type == "Community Member"


class TestPremium:
    # 49. premium remains unavailable
    def test_premium_unavailable(self, app, client):
        _, slug = _make_resource(app, access_type="premium", price=4900)
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "premium_unavailable"

    # 50. active Circle subscription does NOT unlock premium resource
    def test_circle_subscription_does_not_unlock_premium(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        _, slug = _make_resource(app, access_type="premium", price=4900)
        resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user1_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "premium_unavailable"

    # 51. premium denial does not increment count
    def test_premium_denial_does_not_increment_count(self, app, client):
        resource_id, slug = _make_resource(app, access_type="premium", price=4900)
        client.post(f"/api/v1/resources/{slug}/access")
        assert _get_resource(app, resource_id).download_count == 0


class TestPublicListingAccessFilter:
    """Module 8 audit fix: the public listing's `free`/`access_type` query
    params must never let a circle_only resource masquerade as "Free" —
    it requires a paid WSF Circle membership, so it isn't genuinely free
    to a visitor who doesn't have one. See
    app/api/v1/resources.py:build_resource_list_query.
    """

    # "Free" excludes both premium AND circle_only.
    def test_free_filter_excludes_circle_only_and_premium(self, app, client):
        _, free_slug = _make_resource(app, access_type="direct_download")
        _, circle_slug = _make_resource(app, access_type="circle_only")
        _, premium_slug = _make_resource(app, access_type="premium", price=4900)
        resp = client.get("/api/v1/resources", query_string={"free": "true"})
        slugs = {item["slug"] for item in resp.get_json()["data"]}
        assert free_slug in slugs
        assert circle_slug not in slugs
        assert premium_slug not in slugs

    # "Premium" filter is unchanged — premium only, never circle_only.
    def test_premium_filter_still_excludes_circle_only(self, app, client):
        _, circle_slug = _make_resource(app, access_type="circle_only")
        _, premium_slug = _make_resource(app, access_type="premium", price=4900)
        resp = client.get("/api/v1/resources", query_string={"free": "false"})
        slugs = {item["slug"] for item in resp.get_json()["data"]}
        assert premium_slug in slugs
        assert circle_slug not in slugs

    # The listing's own correctly-labeled way to find WSF Circle
    # resources — already-generic ?access_type=... equality filtering,
    # confirmed here so the public "WSF Circle" filter bucket has a
    # covered, working query to rely on.
    def test_access_type_circle_only_filter_finds_circle_resources(self, app, client):
        _, circle_slug = _make_resource(app, access_type="circle_only")
        _, free_slug = _make_resource(app, access_type="direct_download")
        resp = client.get("/api/v1/resources", query_string={"access_type": "circle_only"})
        slugs = {item["slug"] for item in resp.get_json()["data"]}
        assert circle_slug in slugs
        assert free_slug not in slugs


class TestExternalLink:
    # 52. anonymous external link succeeds
    def test_anonymous_external_link_succeeds(self, app, client):
        _, slug = _make_resource(app, access_type="external_link", file_url=None, external_url="https://example.com/offsite")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 200
        assert resp.get_json()["data"]["url"] == "https://example.com/offsite"

    # 53. raw external URL absent from detail
    def test_external_link_detail_excludes_target(self, app, client):
        _, slug = _make_resource(app, access_type="external_link", file_url=None, external_url="https://example.com/offsite")
        detail = client.get(f"/api/v1/resources/{slug}").get_json()["data"]
        assert "externalUrl" not in detail and "external_url" not in detail
        assert detail["accessType"] == "external_link"

    # 54. target only returned from /access
    def test_external_link_target_only_from_access(self, app, client):
        _, slug = _make_resource(app, access_type="external_link", file_url=None, external_url="https://example.com/only-via-access")
        detail = client.get(f"/api/v1/resources/{slug}").get_json()["data"]
        assert "externalUrl" not in detail and "external_url" not in detail
        access = client.post(f"/api/v1/resources/{slug}/access")
        assert access.get_json()["data"]["url"] == "https://example.com/only-via-access"

    # 55. unsafe external scheme rejected (stored directly via ORM, bypassing
    # schema validation, to prove /access itself also refuses it)
    def test_external_link_unsafe_scheme_rejected_at_access(self, app, client):
        _, slug = _make_resource(app, access_type="external_link", file_url=None, external_url="javascript:alert(1)")
        resp = client.post(f"/api/v1/resources/{slug}/access")
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "not_configured"


class TestUrlSafety:
    def _payload(self, **overrides):
        payload = {
            "name": "URL Safety Resource",
            "description": [{"type": "paragraph", "text": "Body."}],
            "accessType": "direct_download",
            "fileUrl": "https://cdn.example.com/safe.pdf",
            "status": "published",
        }
        payload.update(overrides)
        return payload

    # 56. javascript: rejected
    def test_javascript_scheme_rejected(self, client, manager_token):
        resp = client.post("/api/v1/resources", json=self._payload(fileUrl="javascript:alert(1)"), headers=auth_headers(manager_token))
        assert resp.status_code == 422

    # 57. data: rejected
    def test_data_scheme_rejected(self, client, manager_token):
        resp = client.post("/api/v1/resources", json=self._payload(fileUrl="data:text/html,hi"), headers=auth_headers(manager_token))
        assert resp.status_code == 422

    # 58. file: rejected
    def test_file_scheme_rejected(self, client, manager_token):
        resp = client.post("/api/v1/resources", json=self._payload(fileUrl="file:///etc/passwd"), headers=auth_headers(manager_token))
        assert resp.status_code == 422

    # 59. allowed https target accepted
    def test_https_target_accepted(self, client, manager_token):
        resp = client.post("/api/v1/resources", json=self._payload(fileUrl="https://cdn.example.com/ok.pdf"), headers=auth_headers(manager_token))
        assert resp.status_code == 201

    # 60. allowed root-relative /media/ path accepted (this app's own
    # served-asset convention — see config.py's MEDIA_URL)
    def test_media_relative_path_accepted(self, client, manager_token):
        resp = client.post("/api/v1/resources", json=self._payload(fileUrl="/media/resources/sample.pdf"), headers=auth_headers(manager_token))
        assert resp.status_code == 201
        slug = resp.get_json()["data"]["slug"]
        access = client.post(f"/api/v1/resources/{slug}/access")
        assert access.status_code == 200
        assert access.get_json()["data"]["url"] == "/media/resources/sample.pdf"

    # 61. raw filesystem path never returned publicly, even if present in
    # the DB (e.g. legacy data saved before this validation existed) —
    # stored directly via ORM, bypassing schema validation on purpose.
    def test_filesystem_path_never_returned_publicly(self, app, client, manager_token):
        _, slug = _make_resource(app, file_url="/var/www/secret-uploads/file.pdf")
        detail = client.get(f"/api/v1/resources/{slug}").get_json()["data"]
        assert "fileUrl" not in detail and "file_url" not in detail
        access = client.post(f"/api/v1/resources/{slug}/access")
        assert access.status_code == 409
        assert access.get_json()["error"]["code"] == "not_configured"


class TestAdminEditor:
    # 62. admin can create circle_only resource
    def test_admin_can_create_circle_only(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "Circle Exclusive Guide",
                "description": [{"type": "paragraph", "text": "Body."}],
                "accessType": "circle_only",
                "fileUrl": "https://cdn.example.com/circle-guide.pdf",
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["access_type"] == "circle_only"

    # 63. admin can edit circle_only resource
    def test_admin_can_edit_circle_only(self, app, client, manager_token):
        _, slug = _make_resource(app, access_type="direct_download")
        resp = client.put(
            f"/api/v1/resources/{slug}",
            json={
                "name": "Now Circle Exclusive",
                "description": [{"type": "paragraph", "text": "Body."}],
                "accessType": "circle_only",
                "fileUrl": "https://cdn.example.com/now-circle.pdf",
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["access_type"] == "circle_only"

    # 64. published circle_only requires a configured target
    def test_published_circle_only_requires_target(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "No Target Circle Resource",
                "description": [{"type": "paragraph", "text": "Body."}],
                "accessType": "circle_only",
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422

    # 65. existing access types still validate (member_only also needs a target)
    def test_published_member_only_requires_target(self, client, manager_token):
        resp = client.post(
            "/api/v1/resources",
            json={
                "name": "No Target Member Resource",
                "description": [{"type": "paragraph", "text": "Body."}],
                "accessType": "member_only",
                "status": "published",
            },
            headers=auth_headers(manager_token),
        )
        assert resp.status_code == 422


class TestRegressions:
    # 66. direct_download still works
    def test_direct_download_regression(self, app, client):
        _, slug = _make_resource(app, access_type="direct_download")
        assert client.post(f"/api/v1/resources/{slug}/access").status_code == 200

    # 67. email_gate still works
    def test_email_gate_regression(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        resp = client.post(f"/api/v1/resources/{slug}/access", json={"email": "regress@example.com"})
        assert resp.status_code == 201

    # 68. Resource leads still work
    def test_resource_leads_regression(self, app, client):
        _, slug = _make_resource(app, access_type="email_gate")
        client.post(f"/api/v1/resources/{slug}/access", json={"email": "leads-regress@example.com"})
        with app.app_context():
            from app.models.resource import ResourceLead

            assert ResourceLead.query.filter_by(email="leads-regress@example.com").first() is not None

    # 69. Saved resource behavior still works
    def test_saved_resource_regression(self, app, client, user1_token):
        resource_id, slug = _make_resource(app)
        resp = client.post(
            "/api/v1/saved", json={"content_type": "resource", "content_id": resource_id}, headers=auth_headers(user1_token)
        )
        assert resp.status_code in (200, 201)

    # 70. Circle entitlement behavior still works (independent service)
    def test_circle_entitlement_regression(self, app, client, user1_token):
        plan_id = _make_plan(app)
        _make_subscription(app, USER1["email"], plan_id, status="active")
        resp = client.get("/api/v1/circle/me", headers=auth_headers(user1_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["hasAccess"] is True

    # 71. Product-linked resource behavior still works
    def test_product_linked_resource_regression(self, app, client, manager_token):
        resource_id, slug = _make_resource(app)
        with app.app_context():
            from app.extensions import db
            from app.models.commerce import Product
            from app.services.slugs import generate_unique_slug

            product = Product(name="Wraps the resource", resource_id=resource_id, price=0, currency="USD")
            product.slug = generate_unique_slug(Product, product.name)
            db.session.add(product)
            db.session.commit()
        delete_resp = client.delete(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
        assert delete_resp.status_code == 409

    # 72. public Resource listing/search/filter still works
    def test_public_listing_search_filter_regression(self, app, client):
        _make_resource(app, name="Findable Unique Resource Name")
        listing = client.get("/api/v1/resources", query_string={"q": "Findable Unique"}).get_json()["data"]
        assert any(r["name"] == "Findable Unique Resource Name" for r in listing)
