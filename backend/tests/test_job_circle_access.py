"""Focused tests for WSF Job Access Tiers + WSF Circle Gating — the new
`circle_only` Job.access_type (public/circle_only), the central
app/services/job_access.py eligibility rule, the safe-by-default
JobSchema, the public-safe serialization that stops application_url/
application_email/application_instructions from leaking anywhere outside
the editor view or the new POST /jobs/{slug}/access endpoint, and
dual-channel (URL + email) safety revalidation.

Circle entitlement itself is never re-derived here — every "should this
grant access" assertion traces back to app/services/circle.py's
has_circle_access(), exactly as production code does. jobs.create_own
ownership (an employer managing their own listing) is deliberately
preserved and tested as orthogonal to Circle.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "jobcircle-manager@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Nwosu", "country_code": "NG",
}
EMPLOYER_PAYLOAD = {
    "email": "jobcircle-employer@example.com", "password": "supersecret1",
    "first_name": "Wanjiru", "last_name": "Kariuki", "country_code": "KE",
}
OTHER_EMPLOYER_PAYLOAD = {
    "email": "jobcircle-employer-2@example.com", "password": "supersecret1",
    "first_name": "Second", "last_name": "Employer", "country_code": "US",
}
USER_A = {
    "email": "jobcircle-user-a@example.com", "password": "supersecret1",
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
        user_id = user.id
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"], user_id


@pytest.fixture()
def manager_token(client, app):
    token, _ = _register_with_role(client, app, MANAGER_PAYLOAD, "opportunities_manager")
    return token


@pytest.fixture()
def employer_token_and_id(client, app):
    return _register_with_role(client, app, EMPLOYER_PAYLOAD, "employer")


@pytest.fixture()
def employer_token(employer_token_and_id):
    return employer_token_and_id[0]


@pytest.fixture()
def other_employer_token_and_id(client, app):
    return _register_with_role(client, app, OTHER_EMPLOYER_PAYLOAD, "employer")


@pytest.fixture()
def other_employer_token(other_employer_token_and_id):
    return other_employer_token_and_id[0]


@pytest.fixture()
def user_a_token(client):
    return _register(client, USER_A)


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now():
    return datetime.now(timezone.utc)


def _make_job(app, **overrides):
    from app.extensions import db
    from app.models.opportunity import Job

    defaults = dict(
        title="Test Job",
        status="published",
        access_type="public",
        company_name="Test Co",
        application_url="https://example.com/apply",
        description=[{"type": "paragraph", "text": "About this role."}],
    )
    defaults.update(overrides)
    with app.app_context():
        job = Job(slug=_slug("job"), **defaults)
        db.session.add(job)
        db.session.commit()
        return job.id


def _job_slug(app, job_id):
    from app.extensions import db
    from app.models.opportunity import Job

    with app.app_context():
        return db.session.get(Job, job_id).slug


def _base_payload(**overrides):
    payload = {
        "title": "Senior Software Engineer",
        "companyName": "Baraza Ventures",
        "countryCode": "KE",
        "workMode": "Remote",
        "remoteScope": "worldwide",
        "employmentType": "Full-time",
        "careerLevel": "Senior",
        "description": [{"type": "paragraph", "text": "Join our engineering team."}],
        "applicationUrl": "https://example.com/apply/senior-engineer",
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
    assert _make_job(app, access_type="public") is not None


def test_2_circle_only_accepted(app):
    assert _make_job(app, access_type="circle_only") is not None


def test_3_invalid_access_type_rejected_by_db_constraint(app):
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models.opportunity import Job

    with app.app_context():
        job = Job(slug=_slug("job"), title="Bad", status="draft", company_name="Co", access_type="premium_tier")
        db.session.add(job)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_4_default_job_access_type_is_public(app):
    from app.extensions import db
    from app.models.opportunity import Job

    job_id = _make_job(app)
    with app.app_context():
        assert db.session.get(Job, job_id).access_type == "public"


# ===========================================================================
# 5-12: URL safety
# ===========================================================================


def test_5_https_application_url_accepted(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="https://example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_6_http_application_url_accepted(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="http://example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_7_javascript_url_rejected(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="javascript:alert(1)"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_8_data_url_rejected(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="data:text/html,<script>1</script>"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_9_file_url_rejected(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="file:///etc/passwd"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_10_ftp_url_rejected(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="ftp://example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_11_scheme_relative_url_rejected(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="//evil.example.com/apply"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_12_malformed_url_rejected(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(applicationUrl="not-a-url"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


# ===========================================================================
# 13-18: Email safety (write path)
# ===========================================================================


def test_13_valid_application_email_accepted(client, manager_token):
    resp = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl=None, applicationEmail="careers@example.com"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201


def test_14_invalid_application_email_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl=None, applicationEmail="not-an-email"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_15_both_url_and_email_accepted(client, manager_token):
    resp = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl="https://example.com/apply", applicationEmail="careers@example.com"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201


def test_16_neither_url_nor_email_blocks_publish(client, manager_token):
    resp = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl=None, applicationEmail=None, status="published"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_17_unsafe_url_alone_does_not_satisfy_application_channel(app):
    # Publish-time validation reuses the same channel-safety check as the
    # access endpoint — a stored-but-unsafe URL must not satisfy "at least
    # one application channel", confirmed directly against the service.
    from app.extensions import db
    from app.models.opportunity import Job
    from app.services.job_access import has_valid_application_channel

    job_id = _make_job(app, application_url="javascript:alert(1)", application_email=None, status="draft")
    with app.app_context():
        job = db.session.get(Job, job_id)
        assert has_valid_application_channel(job) is False


def test_18_draft_may_omit_application_channel(client, manager_token):
    resp = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl=None, applicationEmail=None, status="draft"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201


# ===========================================================================
# 19-32: Public serialization
# ===========================================================================


def test_19_public_list_does_not_expose_application_url(client, app):
    _make_job(app, access_type="public", title="List Safe Job")
    resp = client.get("/api/v1/jobs")
    body = str(resp.get_json())
    assert "application_url" not in body


def test_20_public_list_does_not_expose_application_email(client, app):
    _make_job(app, access_type="public", application_email="careers@example.com")
    resp = client.get("/api/v1/jobs")
    assert "careers@example.com" not in str(resp.get_json())


def test_21_public_list_does_not_expose_application_instructions(client, app):
    _make_job(app, access_type="public", application_instructions="Secret steps")
    resp = client.get("/api/v1/jobs")
    assert "Secret steps" not in str(resp.get_json())


def test_22_circle_only_list_does_not_expose_application_target(client, app):
    _make_job(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    resp = client.get("/api/v1/jobs")
    assert "circle-apply" not in str(resp.get_json())


def test_23_circle_only_detail_does_not_expose_application_url(client, app):
    job_id = _make_job(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert "circle-apply" not in str(resp.get_json())
    assert resp.get_json()["data"].get("application_url") is None


def test_24_circle_only_detail_does_not_expose_application_email(client, app):
    job_id = _make_job(app, access_type="circle_only", application_email="circle-careers@example.com")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert "circle-careers" not in str(resp.get_json())


def test_25_circle_only_detail_does_not_expose_application_instructions(client, app):
    job_id = _make_job(app, access_type="circle_only", application_instructions="Secret steps")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert "Secret steps" not in str(resp.get_json())


def test_26_anonymous_circle_detail_requires_circle_true(client, app):
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["requiresCircle"] is True


def test_27_anonymous_viewer_can_access_false(client, app):
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["viewerCanAccess"] is False


def test_28_active_circle_viewer_can_access_true(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_29_active_circle_viewer_detail_still_excludes_protected_fields(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", application_url="https://example.com/active-circle-detail",
        application_instructions="Active circle steps",
    )
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "active-circle-detail" not in serialized
    assert "Active circle steps" not in serialized
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_30_public_job_viewer_can_access_true(client, app):
    job_id = _make_job(app, access_type="public")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_31_public_detail_exposes_valid_channel_while_open(client, app):
    job_id = _make_job(app, access_type="public", application_url="https://example.com/open-apply")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["application_url"] == "https://example.com/open-apply"


def test_32_public_detail_exposes_email_channel_while_open(client, app):
    job_id = _make_job(app, access_type="public", application_url=None, application_email="apply@example.com")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["application_email"] == "apply@example.com"


# ===========================================================================
# 33-37: Editor / ownership serialization
# ===========================================================================


def test_33_manager_detail_retains_raw_application_url(client, app, manager_token):
    job_id = _make_job(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["application_url"] == "https://example.com/circle-apply"


def test_34_manager_detail_retains_application_email(client, app, manager_token):
    job_id = _make_job(app, access_type="circle_only", application_email="circle-careers@example.com")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["application_email"] == "circle-careers@example.com"


def test_35_manager_detail_retains_application_instructions(client, app, manager_token):
    job_id = _make_job(app, access_type="circle_only", application_instructions="Secret steps")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["application_instructions"] == "Secret steps"


def test_36_manager_draft_retains_application_fields(client, app, manager_token):
    job_id = _make_job(app, status="draft", access_type="circle_only", application_url="https://example.com/draft-apply")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["application_url"] == "https://example.com/draft-apply"


def test_37_owner_employer_sees_protected_fields_on_own_circle_only_job(client, app, employer_token_and_id):
    token, user_id = employer_token_and_id
    job_id = _make_job(
        app, access_type="circle_only", application_url="https://example.com/owner-apply",
        posted_by_id=user_id,
    )
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(token))
    assert resp.get_json()["data"]["application_url"] == "https://example.com/owner-apply"


# ===========================================================================
# 38-43: Ownership regression ("This is important")
# ===========================================================================


def test_38_owner_never_needs_circle_to_manage_own_job(client, app, employer_token_and_id):
    token, user_id = employer_token_and_id
    job_id = _make_job(app, access_type="circle_only", posted_by_id=user_id)
    slug = _job_slug(app, job_id)
    resp = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(accessType="circle_only", title="Owner Updated"),
        headers=auth_headers(token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["title"] == "Owner Updated"


def test_39_other_employer_cannot_edit_someone_elses_job(client, app, employer_token_and_id, other_employer_token):
    _, user_id = employer_token_and_id
    job_id = _make_job(app, posted_by_id=user_id)
    slug = _job_slug(app, job_id)
    resp = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(title="Hijacked"), headers=auth_headers(other_employer_token),
    )
    assert resp.status_code == 403


def test_40_other_employer_viewing_circle_only_job_gets_public_payload(client, app, employer_token_and_id, other_employer_token):
    _, user_id = employer_token_and_id
    job_id = _make_job(
        app, access_type="circle_only", application_url="https://example.com/owner-only", posted_by_id=user_id,
    )
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(other_employer_token))
    assert "owner-only" not in str(resp.get_json())


def test_41_employer_list_only_returns_own_jobs_with_editor_view(client, app, employer_token_and_id, other_employer_token):
    token, user_id = employer_token_and_id
    _make_job(app, posted_by_id=user_id, application_url="https://example.com/mine", title="Mine")
    resp = client.get("/api/v1/jobs", headers=auth_headers(token))
    items = resp.get_json()["data"]
    mine = next(i for i in items if i["title"] == "Mine")
    assert mine["application_url"] == "https://example.com/mine"


def test_42_employer_create_own_job_succeeds(client, employer_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(), headers=auth_headers(employer_token))
    assert resp.status_code == 201


def test_43_employer_delete_own_job_succeeds(client, app, employer_token_and_id):
    token, user_id = employer_token_and_id
    job_id = _make_job(app, posted_by_id=user_id)
    slug = _job_slug(app, job_id)
    resp = client.delete(f"/api/v1/jobs/{slug}", headers=auth_headers(token))
    assert resp.status_code == 200


# ===========================================================================
# 44-58: Circle access
# ===========================================================================


def test_44_anonymous_access_rejected(client, app):
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "account_required"


def test_45_ordinary_account_denied_circle_required(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_46_community_member_without_circle_denied(client, app, user_a_token):
    _make_member(app, USER_A["email"], membership_type="Community Member")
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_47_community_premium_member_without_circle_denied(client, app, user_a_token):
    _make_member(app, USER_A["email"], membership_type="Premium Member")
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


@pytest.mark.parametrize("status", ["pending", "past_due", "cancelled", "expired", "revoked"])
def test_48_to_52_nonactive_subscription_statuses_denied(client, app, user_a_token, status):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status=status)
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_53_active_future_starts_at_denied(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", starts_at=_now() + timedelta(days=5))
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_54_active_expired_current_period_end_denied(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", current_period_end=_now() - timedelta(days=1))
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_55_valid_active_circle_succeeds(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_56_cancel_at_period_end_future_end_succeeds(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(
        app, USER_A["email"], plan_id, status="active", cancel_at_period_end=True,
        current_period_end=_now() + timedelta(days=10),
    )
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_57_forced_password_change_denied(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


def test_58_inactive_account_denied(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.is_active = False
        db.session.commit()

    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "forbidden"


# ===========================================================================
# 59-70: Application payload / dual-channel safety
# ===========================================================================


def test_59_successful_access_returns_application_url(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", application_url="https://example.com/circle-apply")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["application_url"] == "https://example.com/circle-apply"


def test_60_successful_access_returns_application_email(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", application_url=None, application_email="circle@example.com")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["application_email"] == "circle@example.com"


def test_61_successful_access_returns_application_instructions(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", application_instructions="Email your CV directly.")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["application_instructions"] == "Email your CV directly."


def test_62_both_channels_returned_when_both_valid(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", application_url="https://example.com/both-apply",
        application_email="both@example.com",
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]
    assert data["application_url"] == "https://example.com/both-apply"
    assert data["application_email"] == "both@example.com"


def test_63_payload_contains_no_circle_provider_metadata(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "provider_customer_id" not in serialized
    assert "payment_reference" not in serialized


def test_64_unsafe_url_with_no_email_returns_unavailable(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", application_url="javascript:alert(1)", application_email=None)
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "application_unavailable"
    assert "alert" not in str(resp.get_json())


def test_65_unsafe_url_falls_back_to_valid_email(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", application_url="javascript:alert(1)", application_email="safe@example.com",
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["application_url"] is None
    assert data["application_email"] == "safe@example.com"


def test_66_invalid_email_falls_back_to_valid_url(app):
    from app.models.opportunity import Job
    from app.services.job_access import safe_application_channel

    job = Job(
        slug=_slug("job"), title="X", status="published", company_name="Co",
        application_url="https://example.com/fallback-apply", application_email="not-an-email",
    )
    channel = safe_application_channel(job)
    assert channel["url"] == "https://example.com/fallback-apply"
    assert channel["email"] is None


def test_67_both_channels_unsafe_returns_unavailable(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", application_url="javascript:alert(1)", application_email=None,
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "application_unavailable"


def test_68_no_channel_configured_returns_unavailable(client, app, manager_token, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", application_url=None, application_email=None)
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "application_unavailable"


def test_69_staff_can_still_edit_unsafe_legacy_value(client, app, manager_token):
    job_id = _make_job(app, access_type="circle_only", application_url="javascript:alert(1)")
    slug = _job_slug(app, job_id)
    detail = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert detail.get_json()["data"]["application_url"] == "javascript:alert(1)"

    update = client.put(
        f"/api/v1/jobs/{slug}",
        json=_base_payload(applicationUrl="https://example.com/fixed", accessType="circle_only", status="published"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["application_url"] == "https://example.com/fixed"


def test_70_public_detail_falls_back_to_email_when_url_unsafe(client, app):
    job_id = _make_job(
        app, access_type="public", application_url="javascript:alert(1)", application_email="legit@example.com",
    )
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    data = resp.get_json()["data"]
    assert data["application_url"] is None
    assert data["application_email"] == "legit@example.com"


# ===========================================================================
# 71-78: Closed / visibility
# ===========================================================================


def test_71_deadline_passed_application_closed(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", deadline=date.today() - timedelta(days=1))
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "application_closed"


def test_72_expiry_passed_application_closed(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", expiry_date=date.today() - timedelta(days=1))
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "application_closed"


def test_73_expired_status_not_discoverable_through_access_endpoint(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", status="expired")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_74_archived_status_not_discoverable_through_access_endpoint(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", status="archived")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_75_draft_not_discoverable_through_access_endpoint(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", status="draft")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_76_review_not_discoverable_through_access_endpoint(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only", status="review")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_77_future_scheduled_not_discoverable_through_access_endpoint(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", status="scheduled", published_date=date.today() + timedelta(days=5),
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 404


def test_78_past_scheduled_becomes_accessible(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", status="scheduled", published_date=date.today() - timedelta(days=1),
        application_url="https://example.com/now-live",
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["application_url"] == "https://example.com/now-live"


# ===========================================================================
# 79-82: Public job regression
# ===========================================================================


def test_79_public_job_remains_anonymously_visible(client, app):
    job_id = _make_job(app, access_type="public", title="Anon Visible")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["title"] == "Anon Visible"


def test_80_public_application_remains_anonymously_accessible(client, app):
    job_id = _make_job(app, access_type="public", application_url="https://example.com/apply-public")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["application_url"] == "https://example.com/apply-public"


def test_81_public_access_endpoint_works_anonymously(client, app):
    job_id = _make_job(app, access_type="public", application_url="https://example.com/apply-anon")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["application_url"] == "https://example.com/apply-anon"


def test_82_existing_listing_filter_behavior_intact(client, app):
    _make_job(app, access_type="public", employment_type="Full-time", title="FT Listing")
    _make_job(app, access_type="public", employment_type="Part-time", title="PT Listing")
    resp = client.get("/api/v1/jobs?employment_type=Full-time")
    titles = [j["title"] for j in resp.get_json()["data"]]
    assert titles == ["FT Listing"]


# ===========================================================================
# 83-86: Salary privacy
# ===========================================================================


def test_83_salary_hidden_when_not_visible_regardless_of_access_type(client, app):
    job_id = _make_job(app, access_type="public", salary_visible=False, salary_min=50000, salary_max=70000, currency="USD")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    data = resp.get_json()["data"]
    assert data["salary_min"] is None
    assert data["salary_max"] is None


def test_84_salary_hidden_for_circle_only_non_editor_even_with_access(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", salary_visible=False, salary_min=50000, salary_max=70000, currency="USD",
    )
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]
    assert data["salary_min"] is None


def test_85_salary_visible_for_editor_even_when_not_publicly_visible(client, app, manager_token):
    job_id = _make_job(app, salary_visible=False, salary_min=50000, salary_max=70000, currency="USD")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    data = resp.get_json()["data"]
    assert data["salary_min"] == 50000


def test_86_salary_shown_publicly_when_visible(client, app):
    job_id = _make_job(app, access_type="public", salary_visible=True, salary_min=50000, salary_max=70000, currency="USD")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}")
    assert resp.get_json()["data"]["salary_min"] == 50000


# ===========================================================================
# 87-92: Duplication
# ===========================================================================


def test_87_duplicate_preserves_access_type(client, app, manager_token):
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(manager_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["access_type"] == "circle_only"


def test_88_duplicate_preserves_public_access_type(client, app, manager_token):
    job_id = _make_job(app, access_type="public")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["access_type"] == "public"


def test_89_duplicate_sets_status_draft(client, app, manager_token):
    job_id = _make_job(app, status="published")
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["status"] == "draft"


def test_90_duplicate_resets_featured_and_sponsored(client, app, manager_token):
    job_id = _make_job(app, featured=True, sponsored=True)
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(manager_token))
    data = resp.get_json()["data"]
    assert data["featured"] is False
    assert data["sponsored"] is False


def test_91_duplicate_response_uses_editor_serializer(client, app, manager_token):
    job_id = _make_job(
        app, access_type="circle_only", application_url="https://example.com/dup-apply",
        application_email="dup@example.com",
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(manager_token))
    data = resp.get_json()["data"]
    assert data["application_url"] == "https://example.com/dup-apply"
    assert data["application_email"] == "dup@example.com"


def test_92_duplicate_by_owner_succeeds(client, app, employer_token_and_id):
    token, user_id = employer_token_and_id
    job_id = _make_job(app, posted_by_id=user_id)
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(token))
    assert resp.status_code == 201


# ===========================================================================
# 93-98: Saved Items
# ===========================================================================


def test_93_non_circle_account_can_save_circle_only_job(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only")
    resp = client.post(
        "/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200


def test_94_saved_circle_only_job_has_safe_metadata(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only", title="Saved Circle Job")
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    items = resp.get_json()["data"]["items"]
    assert items[0]["content"]["title"] == "Saved Circle Job"


def test_95_saved_response_never_leaks_application_url(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only", application_url="https://example.com/circle-secret")
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert "circle-secret" not in str(resp.get_json())


def test_96_saved_response_never_leaks_application_email(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only", application_email="circle-secret@example.com")
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token))
    resp = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert "circle-secret@example.com" not in str(resp.get_json())


def test_97_saving_does_not_grant_circle_access(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only")
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token))
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_98_unsaving_remains_unchanged(client, app, user_a_token):
    job_id = _make_job(app, access_type="circle_only")
    client.post("/api/v1/saved", json={"content_type": "job", "content_id": job_id}, headers=auth_headers(user_a_token))
    resp = client.delete(f"/api/v1/saved/job/{job_id}", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    listing = client.get("/api/v1/saved", headers=auth_headers(user_a_token))
    assert listing.get_json()["data"]["items"] == []


# ===========================================================================
# 99-105: Entitlement lifecycle / separation
# ===========================================================================


def test_99_access_endpoint_authoritative_even_if_viewer_hint_stale(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)

    detail = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(user_a_token))
    assert detail.get_json()["data"]["viewerCanAccess"] is True

    _expire_subscription(app, sub_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_100_circle_lapse_causes_next_access_to_fail(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    first = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert first.status_code == 200

    _expire_subscription(app, sub_id)
    second = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert second.status_code == 403


def test_101_circle_renewal_restores_access(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)

    _expire_subscription(app, sub_id)
    denied = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert denied.status_code == 403

    _reactivate_subscription(app, sub_id)
    restored = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert restored.status_code == 200


def test_102_no_persisted_job_entitlement_record_created(client, app, user_a_token):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)

    with app.app_context():
        before = CircleSubscription.query.count()

    client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        after = CircleSubscription.query.count()
    assert before == after


def test_103_access_does_not_create_community_member(client, app, user_a_token):
    from app.models.community import Member

    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert Member.query.count() == 0


def test_104_access_does_not_create_product_or_order(client, app, user_a_token):
    from app.models.commerce import Order, Product

    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert Product.query.count() == 0
        assert Order.query.count() == 0


def test_105_access_does_not_create_event_registration_or_learning_enrollment(client, app, user_a_token):
    from app.models.event_registration import EventRegistration
    from app.models.learning_enrollment import LearningEnrollment

    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(app, access_type="circle_only")
    slug = _job_slug(app, job_id)
    client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))

    with app.app_context():
        assert EventRegistration.query.count() == 0
        assert LearningEnrollment.query.count() == 0


# ===========================================================================
# 106-116: CMS / existing Job regression
# ===========================================================================


def test_106_create_update_public_job_works(client, manager_token):
    created = client.post("/api/v1/jobs", json=_base_payload(accessType="public"), headers=auth_headers(manager_token))
    assert created.status_code == 201
    slug = created.get_json()["data"]["slug"]
    updated = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(accessType="public", title="Updated Title"),
        headers=auth_headers(manager_token),
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["title"] == "Updated Title"


def test_107_create_update_circle_only_job_works(client, manager_token):
    created = client.post("/api/v1/jobs", json=_base_payload(accessType="circle_only"), headers=auth_headers(manager_token))
    assert created.status_code == 201
    assert created.get_json()["data"]["access_type"] == "circle_only"
    slug = created.get_json()["data"]["slug"]
    updated = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(accessType="circle_only", title="Updated Circle Title"),
        headers=auth_headers(manager_token),
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["title"] == "Updated Circle Title"


def test_108_structured_lists_preserved(client, manager_token):
    created = client.post(
        "/api/v1/jobs",
        json=_base_payload(
            responsibilities=["Lead the team"], requirements=["5+ years experience"],
            qualifications=["BSc"], skills=["Python"], benefits=["Health insurance"],
        ),
        headers=auth_headers(manager_token),
    )
    assert created.status_code == 201
    data = created.get_json()["data"]
    assert data["responsibilities"] == ["Lead the team"]
    assert data["skills"] == ["Python"]


def test_109_salary_validation_preserved(client, manager_token):
    resp = client.post(
        "/api/v1/jobs", json=_base_payload(salaryMin=90000, salaryMax=50000), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_110_deadline_expiry_validation_preserved(client, manager_token):
    resp = client.post(
        "/api/v1/jobs", json=_base_payload(deadline="2027-06-01", expiryDate="2027-01-01"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_111_employment_type_validation_preserved(client, manager_token):
    resp = client.post(
        "/api/v1/jobs", json=_base_payload(employmentType="Not-A-Real-Type"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_112_featured_sponsored_behavior_preserved(client, manager_token):
    created = client.post(
        "/api/v1/jobs", json=_base_payload(featured=True, sponsored=True, status="published"),
        headers=auth_headers(manager_token),
    )
    assert created.status_code == 201
    assert created.get_json()["data"]["featured"] is True
    assert created.get_json()["data"]["sponsored"] is True


def test_113_expired_excluded_from_public_listing_but_visible_to_manager(client, app, manager_token):
    job_id = _make_job(app, status="expired", title="Expired Role")
    resp_anon = client.get("/api/v1/jobs")
    assert "Expired Role" not in str(resp_anon.get_json())
    resp_mgr = client.get("/api/v1/jobs", headers=auth_headers(manager_token))
    assert any(j["title"] == "Expired Role" for j in resp_mgr.get_json()["data"])


def test_114_archived_status_marks_is_closed_for_manager(client, app, manager_token):
    job_id = _make_job(app, status="archived")
    slug = _job_slug(app, job_id)
    resp = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["is_closed"] is True


def test_115_city_field_persists(client, manager_token):
    created = client.post("/api/v1/jobs", json=_base_payload(city="Nairobi"), headers=auth_headers(manager_token))
    assert created.status_code == 201
    assert created.get_json()["data"]["city"] == "Nairobi"


def test_116_organization_relationship_preserved(client, manager_token, app):
    from app.extensions import db
    from app.models.people import Organization

    with app.app_context():
        org = Organization(name="Jobcircle Org", slug=_slug("org"), country_code="KE", status="published")
        db.session.add(org)
        db.session.commit()
        org_id = org.id

    created = client.post(
        "/api/v1/jobs", json=_base_payload(organizationId=org_id), headers=auth_headers(manager_token)
    )
    assert created.status_code == 201
    assert created.get_json()["data"]["organization"]["slug"].startswith("org-")


# ===========================================================================
# 117-124: JobSchema safe-by-default + editor re-attachment
# ===========================================================================


def test_117_generic_schema_dump_excludes_application_url_for_public(app):
    from app.schemas.opportunity import JobSchema

    job_id = _make_job(app, access_type="public", application_url="https://example.com/public-apply")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Job

        job = db.session.get(Job, job_id)
        dumped = JobSchema().dump(job)
    assert "application_url" not in dumped


def test_118_generic_schema_dump_excludes_application_email(app):
    from app.schemas.opportunity import JobSchema

    job_id = _make_job(app, access_type="public", application_email="careers@example.com")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Job

        job = db.session.get(Job, job_id)
        dumped = JobSchema().dump(job)
    assert "application_email" not in dumped


def test_119_generic_schema_dump_excludes_application_instructions(app):
    from app.schemas.opportunity import JobSchema

    job_id = _make_job(app, access_type="circle_only", application_instructions="Secret steps")
    with app.app_context():
        from app.extensions import db
        from app.models.opportunity import Job

        job = db.session.get(Job, job_id)
        dumped = JobSchema().dump(job)
    assert "application_instructions" not in dumped


def test_120_manager_list_response_contains_all_protected_fields(client, app, manager_token):
    _make_job(
        app, access_type="public", application_url="https://example.com/mgr-list-apply",
        application_email="mgr-list@example.com", application_instructions="Mgr list steps",
    )
    resp = client.get("/api/v1/jobs", headers=auth_headers(manager_token))
    body = resp.get_json()["data"]
    assert any(j.get("application_url") == "https://example.com/mgr-list-apply" for j in body)
    assert any(j.get("application_email") == "mgr-list@example.com" for j in body)
    assert any(j.get("application_instructions") == "Mgr list steps" for j in body)


def test_121_create_response_contains_all_protected_fields(client, manager_token):
    created = client.post(
        "/api/v1/jobs",
        json=_base_payload(
            applicationUrl="https://example.com/create-apply", applicationEmail="create@example.com",
            applicationInstructions="Create steps",
        ),
        headers=auth_headers(manager_token),
    )
    assert created.status_code == 201
    data = created.get_json()["data"]
    assert data["application_url"] == "https://example.com/create-apply"
    assert data["application_email"] == "create@example.com"
    assert data["application_instructions"] == "Create steps"


def test_122_update_response_contains_all_protected_fields(client, manager_token):
    created = client.post("/api/v1/jobs", json=_base_payload(), headers=auth_headers(manager_token))
    slug = created.get_json()["data"]["slug"]
    updated = client.put(
        f"/api/v1/jobs/{slug}",
        json=_base_payload(
            applicationUrl="https://example.com/update-apply", applicationEmail="update@example.com",
            applicationInstructions="Update steps",
        ),
        headers=auth_headers(manager_token),
    )
    assert updated.status_code == 200
    data = updated.get_json()["data"]
    assert data["application_url"] == "https://example.com/update-apply"
    assert data["application_email"] == "update@example.com"
    assert data["application_instructions"] == "Update steps"


def test_123_anonymous_public_list_contains_none_of_the_protected_fields(client, app):
    _make_job(
        app, access_type="public", application_url="https://example.com/anon-list",
        application_email="anon-list@example.com", application_instructions="Anon list steps",
    )
    resp = client.get("/api/v1/jobs")
    serialized = str(resp.get_json())
    assert "anon-list" not in serialized
    assert "Anon list steps" not in serialized


def test_124_post_access_for_active_circle_still_returns_all_protected_fields(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    job_id = _make_job(
        app, access_type="circle_only", application_url="https://example.com/access-endpoint-apply",
        application_email="access-endpoint@example.com", application_instructions="Access endpoint steps",
    )
    slug = _job_slug(app, job_id)
    resp = client.post(f"/api/v1/jobs/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["application_url"] == "https://example.com/access-endpoint-apply"
    assert data["application_email"] == "access-endpoint@example.com"
    assert data["application_instructions"] == "Access endpoint steps"


# ===========================================================================
# 125-126: ?access_type=circle_only list filter (Module 9 — WSF Circle
# Member Content Hub needs a way to ask the public list for only
# circle_only jobs, the same equality filter Resources/Learning already
# supported; this never changes entitlement, only which rows are returned).
# ===========================================================================


def test_125_access_type_filter_returns_only_circle_only_jobs(client, app):
    _make_job(app, access_type="public", title="Public Filter Job")
    circle_id = _make_job(app, access_type="circle_only", title="Circle Filter Job")
    resp = client.get("/api/v1/jobs?access_type=circle_only")
    items = resp.get_json()["data"]
    assert all(item["access_type"] == "circle_only" for item in items)
    assert any(item["id"] == circle_id for item in items)


def test_126_access_type_filter_still_excludes_application_target(client, app):
    _make_job(app, access_type="circle_only", application_url="https://example.com/filtered-circle-apply")
    resp = client.get("/api/v1/jobs?access_type=circle_only")
    assert "filtered-circle-apply" not in str(resp.get_json())
