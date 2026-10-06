"""Focused tests for WSF Opportunity Access Tiers + WSF Circle Gating — the
new `circle_only` Opportunity.access_type (public/circle_only), the
central app/services/opportunity_access.py eligibility rule, the
public-safe serialization that stops application_url/application_instructions
from leaking anywhere outside the new POST /opportunities/{slug}/access
endpoint, and URL-safety revalidation.

Circle entitlement itself is never re-derived here — every "should this
grant access" assertion traces back to app/services/circle.py's
has_circle_access(), exactly as production code does.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "oppcircle-manager@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Nwosu", "country_code": "NG",
}
NO_PERMISSION_PAYLOAD = {
    "email": "oppcircle-nobody@example.com", "password": "supersecret1",
    "first_name": "No", "last_name": "Permission", "country_code": "US",
}
USER_A = {
    "email": "oppcircle-user-a@example.com", "password": "supersecret1",
    "first_name": "Amina", "last_name": "Diallo", "country_code": "SN",
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
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "opportunities_manager")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login", json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user_a_token(client):
    return _register(client, USER_A)


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now():
    return datetime.now(timezone.utc)


def _make_opportunity(app, **overrides):
    from app.extensions import db
    from app.models.opportunity import Opportunity

    defaults = dict(
        title="Test Opportunity",
        status="published",
        access_type="public",
        application_url="https://example.com/apply",
        organization_name="Test Org",
        description=[{"type": "paragraph", "text": "About this opportunity."}],
    )
    defaults.update(overrides)
    with app.app_context():
        opportunity = Opportunity(slug=_slug("opportunity"), **defaults)
        db.session.add(opportunity)
        db.session.commit()
        return opportunity.id


def _opportunity_slug(app, opportunity_id):
    from app.extensions import db
    from app.models.opportunity import Opportunity

    with app.app_context():
        return db.session.get(Opportunity, opportunity_id).slug


def _base_payload(**overrides):
    payload = {
        "title": "Rising Leaders Fellowship",
        "organizationName": "Foster Capital",
        "type": "Fellowship",
        "shortDescription": "A fellowship for women in mid-career roles.",
        "description": [{"type": "paragraph", "text": "A fellowship for women in mid-career roles."}],
        "applicationUrl": "https://example.com/apply/rising-leaders",
        "deadline": "2027-01-15",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def _make_plan(app, **overrides):
    from app.extensions import db
    from app.models.circle import CirclePlan

    defaults = dict(
        slug=overrides.pop("slug", None) or f"plan-{uuid.uuid4().hex[:10]}",
        name="WSF Circle Membership", billing_interval="monthly", price=1000, currency="USD", status="active",
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
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        defaults = dict(user_id=user.id, plan_id=plan_id, status="active", source="manual")
        defaults.update(overrides)
        subscription = CircleSubscription(**defaults)
        db.session.add(subscription)
        db.session.commit()
        return subscription.id


def _give_active_circle(app, email):
    plan_id = _make_plan(app)
    return _make_subscription(app, email, plan_id, status="active")


def _expire_subscription(app, subscription_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        sub = db.session.get(CircleSubscription, subscription_id)
        sub.status = "expired"
        db.session.commit()


def _reactivate_subscription(app, subscription_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        sub = db.session.get(CircleSubscription, subscription_id)
        sub.status = "active"
        sub.current_period_end = None
        db.session.commit()


def _make_member(app, email, membership_type="Community Member"):
    from app.extensions import db
    from app.models.community import Member
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        member = Member(
            first_name=user.first_name, last_name=user.last_name, email=email,
            status="active", membership_type=membership_type, consent_given=True, user_id=user.id,
        )
        db.session.add(member)
        db.session.commit()
        return member.id


# ===========================================================================
# 1-4: Model / input
# ===========================================================================


def test_1_public_access_type_accepted(app):
    assert _make_opportunity(app, access_type="public") is not None


def test_2_circle_only_accepted(app):
    assert _make_opportunity(app, access_type="circle_only") is not None


def test_3_invalid_access_type_rejected_by_db_constraint(app):
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models.opportunity import Opportunity

    with app.app_context():
        opportunity = Opportunity(slug=_slug("opportunity"), title="Bad", status="draft", access_type="premium_tier")
        db.session.add(opportunity)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_4_default_opportunity_access_type_is_public(app):
    from app.extensions import db
    from app.models.opportunity import Opportunity

    opportunity_id = _make_opportunity(app)
    with app.app_context():
        assert db.session.get(Opportunity, opportunity_id).access_type == "public"


# ===========================================================================
# 5-12: URL safety
# ===========================================================================


def test_5_https_application_url_accepted(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="https://example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_6_http_application_url_accepted(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="http://example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_7_javascript_url_rejected(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="javascript:alert(1)"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_8_data_url_rejected(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="data:text/html,<script>1</script>"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_9_file_url_rejected(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="file:///etc/passwd"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_10_ftp_url_rejected(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="ftp://example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_11_scheme_relative_url_rejected(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="//evil.example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_12_malformed_url_rejected(client, manager_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(applicationUrl="not-a-url"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


# ===========================================================================
# 13-25: Public serialization
# ===========================================================================


def test_13_public_list_does_not_expose_application_url(client, app):
    _make_opportunity(app, access_type="public", title="List Safe Opportunity")
    resp = client.get("/api/v1/opportunities")
    body = str(resp.get_json())
    assert "application_url" not in body


def test_14_public_list_does_not_expose_application_instructions(client, app):
    _make_opportunity(app, access_type="public", application_instructions="Secret steps")
    resp = client.get("/api/v1/opportunities")
    assert "Secret steps" not in str(resp.get_json())


def test_15_circle_only_list_does_not_expose_application_target(client, app):
    _make_opportunity(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    resp = client.get("/api/v1/opportunities")
    assert "circle-apply" not in str(resp.get_json())


def test_16_circle_only_detail_does_not_expose_application_url(client, app):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert "circle-apply" not in str(resp.get_json())
    assert resp.get_json()["data"].get("application_url") is None


def test_17_circle_only_detail_does_not_expose_application_instructions(client, app):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_instructions="Secret steps")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert "Secret steps" not in str(resp.get_json())


def test_18_anonymous_circle_detail_requires_circle_true(client, app):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert resp.get_json()["data"]["requiresCircle"] is True


def test_19_anonymous_viewer_can_access_false(client, app):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert resp.get_json()["data"]["viewerCanAccess"] is False


def test_20_active_circle_viewer_can_access_true(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_21_forced_password_change_circle_viewer_can_access_false(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["viewerCanAccess"] is False


def test_22_public_opportunity_viewer_can_access_true(client, app):
    opportunity_id = _make_opportunity(app, access_type="public")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_23_staff_detail_retains_raw_application_url(client, app, manager_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["application_url"] == "https://example.com/circle-apply"


def test_24_staff_detail_retains_application_instructions(client, app, manager_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_instructions="Secret steps")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["application_instructions"] == "Secret steps"


def test_25_staff_draft_retains_application_fields(client, app, manager_token):
    opportunity_id = _make_opportunity(
        app, status="draft", access_type="circle_only", application_url="https://example.com/draft-apply"
    )
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["application_url"] == "https://example.com/draft-apply"


# ===========================================================================
# 26-30: Public opportunity regression
# ===========================================================================


def test_26_public_opportunity_remains_anonymously_visible(client, app):
    opportunity_id = _make_opportunity(app, access_type="public", title="Anon Visible")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["title"] == "Anon Visible"


def test_27_public_application_remains_anonymously_accessible(client, app):
    opportunity_id = _make_opportunity(app, access_type="public", application_url="https://example.com/apply-public")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert resp.get_json()["data"]["application_url"] == "https://example.com/apply-public"


def test_28_public_application_instructions_available_while_open(client, app):
    opportunity_id = _make_opportunity(app, access_type="public", application_instructions="Submit your CV.")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    assert resp.get_json()["data"]["application_instructions"] == "Submit your CV."


def test_29_public_access_endpoint_works_anonymously(client, app):
    opportunity_id = _make_opportunity(app, access_type="public", application_url="https://example.com/apply-anon")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["application_url"] == "https://example.com/apply-anon"


def test_30_existing_listing_filter_behavior_intact(client, app):
    _make_opportunity(app, access_type="public", type="Grant", title="Grant Listing")
    _make_opportunity(app, access_type="public", type="Fellowship", title="Fellowship Listing")
    resp = client.get("/api/v1/opportunities?type=Grant")
    titles = [o["title"] for o in resp.get_json()["data"]]
    assert titles == ["Grant Listing"]


# ===========================================================================
# 31-45: Circle access
# ===========================================================================


def test_31_anonymous_access_rejected(client, app):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "account_required"


def test_32_ordinary_account_denied_circle_required(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_33_community_member_without_circle_denied(client, app, user_a_token):
    _make_member(app, USER_A["email"], membership_type="Community Member")
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_34_community_premium_member_without_circle_denied(client, app, user_a_token):
    _make_member(app, USER_A["email"], membership_type="Premium Member")
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


@pytest.mark.parametrize("status", ["pending", "past_due", "cancelled", "expired", "revoked"])
def test_35_to_39_nonactive_subscription_statuses_denied(client, app, user_a_token, status):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status=status)
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_40_active_future_starts_at_denied(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", starts_at=_now() + timedelta(days=5))
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_41_active_expired_current_period_end_denied(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", current_period_end=_now() - timedelta(days=1))
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_42_valid_active_circle_succeeds(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_43_cancel_at_period_end_future_end_succeeds(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(
        app, USER_A["email"], plan_id, status="active", cancel_at_period_end=True,
        current_period_end=_now() + timedelta(days=10),
    )
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_44_forced_password_change_denied(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


def test_45_inactive_account_denied(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.is_active = False
        db.session.commit()

    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "forbidden"


# ===========================================================================
# 46-50: Access payload
# ===========================================================================


def test_46_successful_access_returns_application_url(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["application_url"] == "https://example.com/circle-apply"


def test_47_successful_access_returns_application_instructions(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_instructions="Email your CV directly.")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["application_instructions"] == "Email your CV directly."


def test_48_payload_contains_no_circle_provider_metadata(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "provider_customer_id" not in serialized
    assert "payment_reference" not in serialized


def test_49_unsafe_legacy_url_revalidated_never_returned(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="javascript:alert(1)")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "application_unavailable"
    assert "alert" not in str(resp.get_json())


def test_50_staff_can_still_edit_unsafe_legacy_value(client, app, manager_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="javascript:alert(1)")
    slug = _opportunity_slug(app, opportunity_id)
    detail = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(manager_token))
    assert detail.get_json()["data"]["application_url"] == "javascript:alert(1)"

    update = client.put(
        f"/api/v1/opportunities/{slug}",
        json=_base_payload(applicationUrl="https://example.com/fixed", accessType="circle_only", status="published"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["application_url"] == "https://example.com/fixed"


# ===========================================================================
# 51-57: Closed / expired
# ===========================================================================


def test_51_deadline_passed_application_closed(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", deadline=date.today() - timedelta(days=1))
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "application_closed"


def test_52_expiry_passed_application_closed(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", expiry_date=date.today() - timedelta(days=1))
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "application_closed"


def test_53_closed_status_cannot_access_application(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", status="closed")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token), )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "application_closed"


def test_54_archived_cannot_access(client, app, manager_token, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", status="archived")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "application_closed"


def test_55_draft_cannot_access(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only", status="draft")
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_56_closed_published_metadata_stays_truthful(client, app, manager_token):
    opportunity_id = _make_opportunity(app, access_type="public", status="closed")
    slug = _opportunity_slug(app, opportunity_id)
    # Anonymous detail hides non-published statuses outright (pre-existing
    # behavior, unchanged by this module) — staff still sees the truthful
    # is_closed=True metadata.
    anon = client.get(f"/api/v1/opportunities/{slug}")
    assert anon.status_code == 404
    staff = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(manager_token))
    assert staff.get_json()["data"]["is_closed"] is True


def test_57_closed_response_never_leaks_target(client, app, manager_token, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(
        app, access_type="public", status="published", deadline=date.today() - timedelta(days=1),
        application_url="https://example.com/closed-apply",
    )
    slug = _opportunity_slug(app, opportunity_id)
    detail = client.get(f"/api/v1/opportunities/{slug}")
    assert "closed-apply" not in str(detail.get_json())
    access = client.post(f"/api/v1/opportunities/{slug}/access")
    assert access.status_code == 409
    assert "closed-apply" not in str(access.get_json())


# ===========================================================================
# 58-63: Saved Items
# ===========================================================================


def test_58_non_circle_account_can_save_circle_only_opportunity(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    resp = client.post(
        "/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200


def test_59_saved_circle_only_opportunity_has_safe_metadata(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only", title="Saved Circle Opp")
    client.post("/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    items = resp.get_json()["data"]["items"]
    assert items[0]["content"]["title"] == "Saved Circle Opp"


def test_60_saved_response_never_leaks_application_url(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="https://example.com/circle-secret")
    client.post("/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert "circle-secret" not in str(resp.get_json())


def test_61_saved_response_never_leaks_application_instructions(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only", application_instructions="Secret steps here")
    client.post("/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert "Secret steps here" not in str(resp.get_json())


def test_62_saving_does_not_grant_circle_access(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    client.post("/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token))
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_63_unsaving_remains_unchanged(client, app, user_a_token):
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    client.post("/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token))
    resp = client.delete(f"/api/v1/saved/opportunity/{opportunity_id}", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    listing = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert listing.get_json()["data"]["items"] == []


# ===========================================================================
# 64-69: Separation
# ===========================================================================


def test_64_access_does_not_create_community_member(client, app, user_a_token):
    from app.models.community import Member

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert Member.query.count() == 0


def test_65_access_does_not_alter_community_membership_type(client, app, user_a_token):
    from app.extensions import db
    from app.models.community import Member

    member_id = _make_member(app, USER_A["email"], membership_type="Community Member")
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        member = db.session.get(Member, member_id)
        assert member.membership_type == "Community Member"


def test_66_access_does_not_create_product(client, app, user_a_token):
    from app.models.commerce import Product

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert Product.query.count() == 0


def test_67_access_does_not_create_order(client, app, user_a_token):
    from app.models.commerce import Order

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert Order.query.count() == 0


def test_68_access_does_not_create_event_registration(client, app, user_a_token):
    from app.models.event_registration import EventRegistration

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert EventRegistration.query.count() == 0


def test_69_access_does_not_create_learning_enrollment(client, app, user_a_token):
    from app.models.learning_enrollment import LearningEnrollment

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert LearningEnrollment.query.count() == 0


# ===========================================================================
# 70-73: Privacy / authority
# ===========================================================================


def test_70_access_endpoint_authoritative_even_if_viewer_hint_stale(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)

    detail = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(user_a_token))
    assert detail.get_json()["data"]["viewerCanAccess"] is True

    _expire_subscription(app, sub_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_71_circle_lapse_causes_next_access_to_fail(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)
    first = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert first.status_code == 200

    _expire_subscription(app, sub_id)
    second = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert second.status_code == 403


def test_72_circle_renewal_restores_access(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)

    _expire_subscription(app, sub_id)
    denied = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert denied.status_code == 403

    _reactivate_subscription(app, sub_id)
    restored = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert restored.status_code == 200


def test_73_no_persisted_opportunity_entitlement_record_created(client, app, user_a_token):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(app, access_type="circle_only")
    slug = _opportunity_slug(app, opportunity_id)

    with app.app_context():
        before = CircleSubscription.query.count()

    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        after = CircleSubscription.query.count()
    assert before == after


# ===========================================================================
# 74-81: CMS regression
# ===========================================================================


def test_74_create_update_public_opportunity_works(client, manager_token):
    created = client.post("/api/v1/opportunities", json=_base_payload(accessType="public"), headers=auth_headers(manager_token))
    assert created.status_code == 201
    slug = created.get_json()["data"]["slug"]
    updated = client.put(
        f"/api/v1/opportunities/{slug}", json=_base_payload(accessType="public", title="Updated Title"),
        headers=auth_headers(manager_token),
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["title"] == "Updated Title"


def test_75_create_update_circle_only_opportunity_works(client, manager_token):
    created = client.post("/api/v1/opportunities", json=_base_payload(accessType="circle_only"), headers=auth_headers(manager_token))
    assert created.status_code == 201
    assert created.get_json()["data"]["access_type"] == "circle_only"
    slug = created.get_json()["data"]["slug"]
    updated = client.put(
        f"/api/v1/opportunities/{slug}", json=_base_payload(accessType="circle_only", title="Updated Circle Title"),
        headers=auth_headers(manager_token),
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["title"] == "Updated Circle Title"


def test_76_provider_relationship_preserved(client, manager_token):
    created = client.post(
        "/api/v1/opportunities", json=_base_payload(organizationName="Direct Provider Co"),
        headers=auth_headers(manager_token),
    )
    assert created.status_code == 201
    assert created.get_json()["data"]["organization_name"] == "Direct Provider Co"


def test_77_country_eligibility_preserved(client, manager_token):
    created = client.post(
        "/api/v1/opportunities", json=_base_payload(countriesEligible=["US", "KE"]), headers=auth_headers(manager_token)
    )
    assert created.status_code == 201
    assert {c["code"] for c in created.get_json()["data"]["countries_eligible"]} == {"US", "KE"}


def test_78_topics_preserved(client, manager_token, app):
    from app.extensions import db
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic.query.filter_by(slug="leadership-oppcircle").first()
        if topic is None:
            topic = Topic(name="Leadership Oppcircle", slug="leadership-oppcircle")
            db.session.add(topic)
            db.session.commit()

    created = client.post(
        "/api/v1/opportunities", json=_base_payload(topicSlugs=["leadership-oppcircle"]), headers=auth_headers(manager_token)
    )
    assert created.status_code == 201
    assert [t["slug"] for t in created.get_json()["data"]["topics"]] == ["leadership-oppcircle"]


def test_79_funding_validation_preserved(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities", json=_base_payload(fundingMin=50000, fundingMax=1000), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_80_deadline_expiry_validation_preserved(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities", json=_base_payload(deadline="2027-06-01", expiryDate="2027-01-01"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_81_sponsored_featured_behavior_preserved(client, manager_token):
    created = client.post(
        "/api/v1/opportunities", json=_base_payload(featured=True, sponsored=True, status="published"),
        headers=auth_headers(manager_token),
    )
    assert created.status_code == 201
    assert created.get_json()["data"]["featured"] is True
    assert created.get_json()["data"]["sponsored"] is True


# ===========================================================================
# 82-95: OpportunitySchema safe-by-default + staff re-attachment
# (security-hardening follow-up — generic schema must never leak the
# protected application fields; only _dump_opportunity_for_staff() may)
# ===========================================================================


def test_82_generic_schema_dump_excludes_application_url_for_public(app):
    from app.schemas.opportunity import OpportunitySchema

    opportunity_id = _make_opportunity(app, access_type="public", application_url="https://example.com/public-apply")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Opportunity

        opportunity = db.session.get(Opportunity, opportunity_id)
        dumped = OpportunitySchema().dump(opportunity)
    assert "application_url" not in dumped


def test_83_generic_schema_dump_excludes_application_instructions_for_public(app):
    from app.schemas.opportunity import OpportunitySchema

    opportunity_id = _make_opportunity(app, access_type="public", application_instructions="Submit your CV.")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Opportunity

        opportunity = db.session.get(Opportunity, opportunity_id)
        dumped = OpportunitySchema().dump(opportunity)
    assert "application_instructions" not in dumped


def test_84_generic_schema_dump_excludes_application_url_for_circle_only(app):
    from app.schemas.opportunity import OpportunitySchema

    opportunity_id = _make_opportunity(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Opportunity

        opportunity = db.session.get(Opportunity, opportunity_id)
        dumped = OpportunitySchema().dump(opportunity)
    assert "application_url" not in dumped


def test_85_generic_schema_dump_excludes_application_instructions_for_circle_only(app):
    from app.schemas.opportunity import OpportunitySchema

    opportunity_id = _make_opportunity(app, access_type="circle_only", application_instructions="Secret steps")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Opportunity

        opportunity = db.session.get(Opportunity, opportunity_id)
        dumped = OpportunitySchema().dump(opportunity)
    assert "application_instructions" not in dumped


def test_86_manager_list_response_contains_both_protected_fields(client, app, manager_token):
    _make_opportunity(app, access_type="public", application_url="https://example.com/mgr-list-apply", application_instructions="Mgr list steps")
    resp = client.get("/api/v1/opportunities", headers=auth_headers(manager_token))
    body = resp.get_json()["data"]
    assert any(o.get("application_url") == "https://example.com/mgr-list-apply" for o in body)
    assert any(o.get("application_instructions") == "Mgr list steps" for o in body)


def test_87_manager_detail_contains_both_protected_fields(client, app, manager_token):
    opportunity_id = _make_opportunity(
        app, access_type="circle_only", application_url="https://example.com/mgr-detail-apply",
        application_instructions="Mgr detail steps",
    )
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(manager_token))
    data = resp.get_json()["data"]
    assert data["application_url"] == "https://example.com/mgr-detail-apply"
    assert data["application_instructions"] == "Mgr detail steps"


def test_88_create_response_contains_both_protected_fields(client, manager_token):
    created = client.post(
        "/api/v1/opportunities",
        json=_base_payload(applicationUrl="https://example.com/create-apply", applicationInstructions="Create steps"),
        headers=auth_headers(manager_token),
    )
    assert created.status_code == 201
    data = created.get_json()["data"]
    assert data["application_url"] == "https://example.com/create-apply"
    assert data["application_instructions"] == "Create steps"


def test_89_update_response_contains_both_protected_fields(client, manager_token):
    created = client.post("/api/v1/opportunities", json=_base_payload(), headers=auth_headers(manager_token))
    slug = created.get_json()["data"]["slug"]
    updated = client.put(
        f"/api/v1/opportunities/{slug}",
        json=_base_payload(applicationUrl="https://example.com/update-apply", applicationInstructions="Update steps"),
        headers=auth_headers(manager_token),
    )
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["application_url"] == "https://example.com/update-apply"
    assert data["application_instructions"] == "Update steps"


def test_90_anonymous_public_list_contains_neither_protected_field(client, app):
    _make_opportunity(app, access_type="public", application_url="https://example.com/anon-list", application_instructions="Anon list steps")
    resp = client.get("/api/v1/opportunities")
    serialized = str(resp.get_json())
    assert "anon-list" not in serialized
    assert "Anon list steps" not in serialized


def test_91_anonymous_circle_only_detail_contains_neither_protected_field(client, app):
    opportunity_id = _make_opportunity(
        app, access_type="circle_only", application_url="https://example.com/anon-circle",
        application_instructions="Anon circle steps",
    )
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}")
    serialized = str(resp.get_json())
    assert "anon-circle" not in serialized
    assert "Anon circle steps" not in serialized


def test_92_active_circle_viewer_detail_still_excludes_protected_fields_for_circle_only(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(
        app, access_type="circle_only", application_url="https://example.com/active-circle-detail",
        application_instructions="Active circle steps",
    )
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.get(f"/api/v1/opportunities/{slug}", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "active-circle-detail" not in serialized
    assert "Active circle steps" not in serialized
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_93_post_access_for_active_circle_still_returns_both_protected_fields(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    opportunity_id = _make_opportunity(
        app, access_type="circle_only", application_url="https://example.com/access-endpoint-apply",
        application_instructions="Access endpoint steps",
    )
    slug = _opportunity_slug(app, opportunity_id)
    resp = client.post(f"/api/v1/opportunities/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["application_url"] == "https://example.com/access-endpoint-apply"
    assert data["application_instructions"] == "Access endpoint steps"


def test_94_saved_items_circle_only_still_contains_neither_protected_field(client, app, user_a_token):
    opportunity_id = _make_opportunity(
        app, access_type="circle_only", application_url="https://example.com/saved-circle",
        application_instructions="Saved circle steps",
    )
    client.post("/api/v1/saved", json={"content_type": "opportunity", "content_id": opportunity_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "saved-circle" not in serialized
    assert "Saved circle steps" not in serialized


def test_95_ordinary_public_apply_behavior_unchanged(client, app):
    opportunity_id = _make_opportunity(
        app, access_type="public", application_url="https://example.com/ordinary-apply",
        application_instructions="Ordinary apply steps",
    )
    slug = _opportunity_slug(app, opportunity_id)
    detail = client.get(f"/api/v1/opportunities/{slug}")
    data = detail.get_json()["data"]
    assert data["application_url"] == "https://example.com/ordinary-apply"
    assert data["application_instructions"] == "Ordinary apply steps"

    access = client.post(f"/api/v1/opportunities/{slug}/access")
    assert access.status_code == 200
    assert access.get_json()["data"]["application_url"] == "https://example.com/ordinary-apply"


# ===========================================================================
# 96-97: ?access_type=circle_only list filter (Module 9 — WSF Circle Member
# Content Hub needs a way to ask the public list for only circle_only
# opportunities, the same equality filter Resources/Learning already
# supported; this never changes entitlement, only which rows are returned).
# ===========================================================================


def test_96_access_type_filter_returns_only_circle_only_opportunities(client, app):
    _make_opportunity(app, access_type="public", title="Public Filter Opportunity")
    circle_id = _make_opportunity(app, access_type="circle_only", title="Circle Filter Opportunity")
    resp = client.get("/api/v1/opportunities?access_type=circle_only")
    items = resp.get_json()["data"]
    assert all(item["access_type"] == "circle_only" for item in items)
    assert any(item["id"] == circle_id for item in items)


def test_97_access_type_filter_still_excludes_application_target(client, app):
    _make_opportunity(app, access_type="circle_only", application_url="https://example.com/filtered-circle-apply")
    resp = client.get("/api/v1/opportunities?access_type=circle_only")
    assert "filtered-circle-apply" not in str(resp.get_json())
