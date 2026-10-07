"""Focused tests for WSF Event Access Tiers + WSF Circle Gating — the new
`circle_only` Event.access_type (public/circle_only), the central
app/services/event_access.py eligibility rule, the Circle-gated
registration rules in app/services/event_registrations.py, and the
private virtual-link security fix (circle_only never trusts
virtual_link_public, even on a legacy/bad row).

Circle entitlement itself is never re-derived here — every "should this
grant access" assertion traces back to app/services/circle.py's
has_circle_access(), exactly as production code does.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

USER_A = {
    "email": "evtcircle-user-a@example.com", "password": "supersecret1",
    "first_name": "Amina", "last_name": "Diallo", "country_code": "SN",
}
USER_B = {
    "email": "evtcircle-user-b@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "KE",
}
MANAGER_PAYLOAD = {
    "email": "evtcircle-manager@example.com", "password": "supersecret1",
    "first_name": "Amara", "last_name": "Nwosu", "country_code": "NG",
}
NO_PERMISSION_PAYLOAD = {
    "email": "evtcircle-nobody@example.com", "password": "supersecret1",
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
def user_a_token(client):
    return _register(client, USER_A)


@pytest.fixture()
def user_b_token(client):
    return _register(client, USER_B)


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "events_manager")


@pytest.fixture()
def no_permission_token(client):
    return _register(client, NO_PERMISSION_PAYLOAD)


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _now():
    return datetime.now(timezone.utc)


def _make_event(app, **overrides):
    from app.extensions import db
    from app.models.opportunity import Event

    defaults = dict(
        title="Test Event",
        status="published",
        registration_required=True,
        registration_mode="wsf",
        date=date.today() + timedelta(days=10),
        format="virtual",
        access_type="public",
        virtual_link="https://meet.example.org/secret-room",
    )
    defaults.update(overrides)
    with app.app_context():
        event = Event(slug=_slug("event"), **defaults)
        db.session.add(event)
        db.session.commit()
        return event.id


def _event_slug(app, event_id):
    from app.extensions import db
    from app.models.opportunity import Event

    with app.app_context():
        return db.session.get(Event, event_id).slug


def _get_registration_row(app, event_id, user_email):
    from app.models.event_registration import EventRegistration
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=user_email).first()
        return EventRegistration.query.filter_by(event_id=event_id, user_id=user.id).first()


def _count_registrations(app, event_id=None):
    from app.models.event_registration import EventRegistration

    with app.app_context():
        q = EventRegistration.query
        if event_id is not None:
            q = q.filter_by(event_id=event_id)
        return q.count()


def _base_event_payload(**overrides):
    payload = {
        "title": "Circle Members Forum",
        "format": "virtual",
        "shortDescription": "A forum for WSF Circle members.",
        "description": [{"type": "paragraph", "text": "A forum for WSF Circle members."}],
        "date": "2027-03-10",
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
    event_id = _make_event(app, access_type="public")
    assert event_id is not None


def test_2_circle_only_accepted(app):
    event_id = _make_event(app, access_type="circle_only")
    assert event_id is not None


def test_3_invalid_access_type_rejected_by_db_constraint(app):
    from sqlalchemy.exc import IntegrityError

    from app.extensions import db
    from app.models.opportunity import Event

    with app.app_context():
        event = Event(
            slug=_slug("event"), title="Bad", status="draft", date=date.today() + timedelta(days=10),
            access_type="premium_tier",
        )
        db.session.add(event)
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_4_existing_default_event_is_public(app):
    from app.extensions import db
    from app.models.opportunity import Event

    event_id = _make_event(app)
    with app.app_context():
        event = db.session.get(Event, event_id)
        assert event.access_type == "public"


# ===========================================================================
# 5-12: Publish validation
# ===========================================================================


def test_5_public_external_event_still_publishes(client, manager_token):
    payload = _base_event_payload(
        status="published", registrationRequired=True, registrationMode="external",
        registrationUrl="https://example.com/register",
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_6_public_wsf_free_event_still_publishes(client, manager_token):
    payload = _base_event_payload(status="published", registrationRequired=True, registrationMode="wsf")
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_7_public_paid_external_event_still_publishes(client, manager_token):
    payload = _base_event_payload(
        status="published", registrationRequired=True, registrationMode="external",
        registrationUrl="https://example.com/register", ticketPrice=50, currency="USD",
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201


def test_8_circle_only_registration_not_required_rejected(client, manager_token):
    payload = _base_event_payload(status="published", accessType="circle_only", registrationRequired=False)
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422
    assert "Circle-only events must require registration." in resp.get_json()["error"]["message"]


def test_9_circle_only_external_mode_rejected(client, manager_token):
    payload = _base_event_payload(
        status="published", accessType="circle_only", registrationRequired=True, registrationMode="external",
        registrationUrl="https://example.com/register",
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422
    assert "Circle-only events must use WSF-managed registration." in resp.get_json()["error"]["message"]


def test_10_circle_only_paid_wsf_rejected(client, manager_token):
    # The pre-existing generic rule (schemas/opportunity.py's
    # validate_pricing: WSF-managed registration is free-events-only)
    # already catches this at schema-validation time — the circle_only
    # check in _validate_for_publish carries the same message as a
    # defense-in-depth backstop for events built incrementally (e.g. via
    # PATCH) that never passed through creation-time schema validation.
    payload = _base_event_payload(
        status="published", accessType="circle_only", registrationRequired=True, registrationMode="wsf",
        ticketPrice=10, currency="USD",
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422
    assert "Paid WSF-managed event registration is not available yet." in str(resp.get_json())


def test_11_circle_only_virtual_link_public_rejected(client, manager_token):
    payload = _base_event_payload(
        status="published", accessType="circle_only", registrationRequired=True, registrationMode="wsf",
        virtualLink="https://meet.example.org/room", virtualLinkPublic=True,
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422
    assert "cannot expose its virtual joining link publicly" in resp.get_json()["error"]["message"]


def test_12_valid_circle_only_configuration_publishes(client, manager_token):
    payload = _base_event_payload(
        status="published", accessType="circle_only", registrationRequired=True, registrationMode="wsf",
        virtualLink="https://meet.example.org/room", virtualLinkPublic=False,
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["access_type"] == "circle_only"


# ===========================================================================
# 12a-12d: Virtual-first Circle events need a private joining link
# ===========================================================================


def test_12a_circle_only_virtual_without_link_rejected(client, manager_token):
    payload = _base_event_payload(
        status="published", format="virtual", accessType="circle_only", registrationRequired=True,
        registrationMode="wsf", virtualLink=None,
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422
    assert "needs a private joining link" in resp.get_json()["error"]["message"]


def test_12b_circle_only_hybrid_without_link_rejected(client, manager_token):
    payload = _base_event_payload(
        status="published", format="hybrid", accessType="circle_only", registrationRequired=True,
        registrationMode="wsf", virtualLink=None,
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422
    assert "needs a private joining link" in resp.get_json()["error"]["message"]


def test_12c_circle_only_virtual_with_link_publishes(client, manager_token):
    payload = _base_event_payload(
        status="published", format="virtual", accessType="circle_only", registrationRequired=True,
        registrationMode="wsf", virtualLink="https://meet.example.org/circle-room", virtualLinkPublic=False,
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["format"] == "virtual"


def test_12d_circle_only_in_person_without_link_still_publishes(client, manager_token):
    # In-person events never need a virtual joining link.
    payload = _base_event_payload(
        status="published", format="in-person", accessType="circle_only", registrationRequired=True,
        registrationMode="wsf", virtualLink=None,
    )
    resp = client.post("/api/v1/events", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["format"] == "in-person"


# ===========================================================================
# 13-19: Public visibility
# ===========================================================================


def test_13_circle_only_event_remains_anonymously_visible(client, app):
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.status_code == 200
    assert resp.get_json()["data"]["title"] == "Test Event"


def test_14_circle_only_appears_in_public_list(client, app):
    _make_event(app, access_type="circle_only", title="Circle Listed Event")
    resp = client.get("/api/v1/events")
    titles = [e["title"] for e in resp.get_json()["data"]["items"] if "items" in resp.get_json()["data"]] if False else None
    body = resp.get_json()["data"]
    items = body["items"] if isinstance(body, dict) else body
    assert "Circle Listed Event" in [e["title"] for e in items]


def test_15_anonymous_payload_requires_circle_true(client, app):
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["requiresCircle"] is True


def test_16_anonymous_viewer_can_access_false(client, app):
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["viewerCanAccess"] is False


def test_17_active_circle_viewer_can_access_true(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["viewerCanAccess"] is True


def test_18_forced_password_change_circle_viewer_can_access_false(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["viewerCanAccess"] is False


def test_19_public_event_viewer_can_access_true(client, app):
    event_id = _make_event(app, access_type="public")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["viewerCanAccess"] is True


# ===========================================================================
# 20-37: Circle registration
# ===========================================================================


def test_20_anonymous_registration_rejected(client, app):
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id})
    assert resp.status_code == 401


def test_21_ordinary_account_denied_circle_required(client, app, user_a_token):
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_22_community_member_without_circle_denied(client, app, user_a_token):
    _make_member(app, USER_A["email"], membership_type="Community Member")
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_23_community_premium_member_without_circle_denied(client, app, user_a_token):
    # Regression: Community "Premium Member" membership_type must NEVER
    # be mistaken for WSF Circle entitlement.
    _make_member(app, USER_A["email"], membership_type="Premium Member")
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


@pytest.mark.parametrize("status", ["pending", "past_due", "cancelled", "expired", "revoked"])
def test_24_to_28_nonactive_subscription_statuses_denied(client, app, user_a_token, status):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status=status)
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_29_future_starts_at_denied(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", starts_at=_now() + timedelta(days=5))
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_30_expired_current_period_end_denied(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(app, USER_A["email"], plan_id, status="active", current_period_end=_now() - timedelta(days=1))
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_31_valid_active_circle_succeeds(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["registered"] is True


def test_32_cancel_at_period_end_future_end_succeeds(client, app, user_a_token):
    plan_id = _make_plan(app)
    _make_subscription(
        app, USER_A["email"], plan_id, status="active", cancel_at_period_end=True,
        current_period_end=_now() + timedelta(days=10),
    )
    event_id = _make_event(app, access_type="circle_only")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200


def test_33_denied_request_creates_no_registration(client, app, user_a_token):
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert _count_registrations(app, event_id) == 0


def test_34_denied_request_consumes_no_capacity(client, app, user_a_token):
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    from app.services.event_registrations import count_active_registrations

    with app.app_context():
        assert count_active_registrations(event_id) == 0


def test_35_denied_request_sends_no_email(client, app, user_a_token, monkeypatch):
    import app.api.v1.event_registrations as mod

    calls = []
    monkeypatch.setattr(mod, "send_email", lambda **kwargs: calls.append(1) or True)
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert len(calls) == 0


def test_36_successful_circle_registration_sends_confirmation_email(client, app, user_a_token, monkeypatch):
    import app.api.v1.event_registrations as mod

    calls = []
    monkeypatch.setattr(mod, "send_email", lambda **kwargs: calls.append(1) or True)
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert len(calls) == 1


def test_37_duplicate_registration_remains_idempotent(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    first = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    second = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert first.get_json()["data"]["registration"]["id"] == second.get_json()["data"]["registration"]["id"]
    assert _count_registrations(app, event_id) == 1


# ===========================================================================
# 38-41: Separation
# ===========================================================================


def test_38_circle_registration_does_not_change_community_member(client, app, user_a_token):
    member_id = _make_member(app, USER_A["email"], membership_type="Community Member")
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    from app.extensions import db
    from app.models.community import Member

    with app.app_context():
        member = db.session.get(Member, member_id)
        assert member.membership_type == "Community Member"
        assert member.status == "active"


def test_39_circle_registration_does_not_create_product(client, app, user_a_token):
    from app.models.commerce import Product

    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    with app.app_context():
        assert Product.query.count() == 0


def test_40_circle_registration_does_not_create_order(client, app, user_a_token):
    from app.models.commerce import Order

    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    with app.app_context():
        assert Order.query.count() == 0


def test_41_public_event_does_not_require_circle(client, app, user_a_token):
    event_id = _make_event(app, access_type="public")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200


# ===========================================================================
# 42-46: Cancel / re-register
# ===========================================================================


def test_42_lapsed_circle_user_can_cancel_existing_registration(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registration = _get_registration_row(app, event_id, USER_A["email"])

    _expire_subscription(app, sub_id)
    resp = client.post(f"/api/v1/event-registrations/{registration.id}/cancel", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["registration"]["status"] == "cancelled"


def test_43_cancelled_circle_registration_releases_capacity(client, app, user_a_token, user_b_token):
    _give_active_circle(app, USER_A["email"])
    _give_active_circle(app, USER_B["email"])
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registration = _get_registration_row(app, event_id, USER_A["email"])

    full = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token))
    assert full.status_code == 409
    assert full.get_json()["error"]["code"] == "capacity_full"

    client.post(f"/api/v1/event-registrations/{registration.id}/cancel", headers=auth_headers(user_a_token))
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token))
    assert resp.status_code == 200


def test_44_reregister_without_current_circle_denied(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registration = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{registration.id}/cancel", headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "circle_required"


def test_45_reregister_with_restored_circle_succeeds(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registration = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{registration.id}/cancel", headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    _reactivate_subscription(app, sub_id)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["registration"]["status"] == "registered"


def test_46_normal_capacity_window_rules_still_apply_after_entitlement_check(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", sold_out=True)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "sold_out"


# ===========================================================================
# 47-50: Lapse / history
# ===========================================================================


def test_47_circle_expiry_does_not_delete_registration(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    assert _get_registration_row(app, event_id, USER_A["email"]) is not None


def test_48_circle_expiry_does_not_auto_cancel_registration(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    row = _get_registration_row(app, event_id, USER_A["email"])
    assert row.status == "registered"


def test_49_lapsed_active_registration_still_consumes_capacity(client, app, user_a_token, user_b_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    _give_active_circle(app, USER_B["email"])
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "capacity_full"


def test_50_renewal_restores_event_access_automatically(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    slug = _event_slug(app, event_id)
    denied = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert denied.get_json()["data"]["viewerCanAccess"] is False

    _reactivate_subscription(app, sub_id)
    restored = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert restored.get_json()["data"]["viewerCanAccess"] is True


# ===========================================================================
# 51-61: Virtual link security
# ===========================================================================


def test_51_anonymous_circle_only_never_receives_virtual_link(client, app):
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["virtual_link"] is None


def test_52_circle_only_legacy_virtual_link_public_still_does_not_leak(client, app):
    # Defense-in-depth (spec section D) — even a historical/bad row with
    # virtual_link_public == True must not leak anonymously for
    # circle_only, bypassing publish validation entirely via direct ORM.
    event_id = _make_event(app, access_type="circle_only", virtual_link_public=True)
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["virtual_link"] is None


def test_53_circle_user_without_registration_gets_no_private_link(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] is None


def test_54_registered_active_circle_user_gets_private_virtual_link(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] == "https://meet.example.org/secret-room"


def test_55_registered_user_after_circle_expiry_gets_virtual_link_null(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] is None


def test_56_renewal_restores_virtual_link(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    _expire_subscription(app, sub_id)
    _reactivate_subscription(app, sub_id)
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] == "https://meet.example.org/secret-room"


def test_57_cancelled_registration_gets_no_link(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registration = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{registration.id}/cancel", headers=auth_headers(user_a_token))

    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] is None


def test_58_another_users_registration_gives_no_link(client, app, user_a_token, user_b_token):
    _give_active_circle(app, USER_A["email"])
    _give_active_circle(app, USER_B["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_b_token))
    assert resp.get_json()["data"]["virtual_link"] is None


def test_59_staff_events_manage_can_view_private_link(client, app, user_a_token, manager_token):
    event_id = _make_event(app, access_type="circle_only")
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(manager_token))
    assert resp.get_json()["data"]["virtual_link"] == "https://meet.example.org/secret-room"


def test_60_ordinary_public_event_virtual_link_public_still_works(client, app):
    event_id = _make_event(app, access_type="public", virtual_link_public=True)
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["virtual_link"] == "https://meet.example.org/secret-room"


def test_61_ordinary_public_private_link_still_requires_active_registration(client, app, user_a_token):
    event_id = _make_event(app, access_type="public", virtual_link_public=False)
    slug = _event_slug(app, event_id)
    anon = client.get(f"/api/v1/events/{slug}")
    assert anon.get_json()["data"]["virtual_link"] is None

    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registered = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert registered.get_json()["data"]["virtual_link"] == "https://meet.example.org/secret-room"


# ===========================================================================
# 62-67: Owner payload / My Events
# ===========================================================================


def test_62_public_registration_can_access_event_true(client, app, user_a_token):
    event_id = _make_event(app, access_type="public")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/event-registrations/check?event_id={event_id}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["registration"]["can_access_event"] is True


def test_63_active_circle_registration_can_access_event_true(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/event-registrations/check?event_id={event_id}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["registration"]["can_access_event"] is True


def test_64_lapsed_circle_registration_false_with_reason(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    _expire_subscription(app, sub_id)

    resp = client.get(f"/api/v1/event-registrations/check?event_id={event_id}", headers=auth_headers(user_a_token))
    data = resp.get_json()["data"]["registration"]
    assert data["can_access_event"] is False
    assert data["access_reason"] == "circle_required"


def test_65_lapsed_circle_registration_remains_returned_by_me(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    _expire_subscription(app, sub_id)

    resp = client.get("/api/v1/event-registrations/me", headers=auth_headers(user_a_token))
    rows = resp.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["status"] == "registered"
    assert rows[0]["can_access_event"] is False


def test_66_me_lapsed_circle_response_does_not_expose_private_virtual_link(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    _expire_subscription(app, sub_id)

    resp = client.get("/api/v1/event-registrations/me", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "secret-room" not in serialized


def test_67_owner_payload_no_circle_subscription_provider_metadata(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    resp = client.get(f"/api/v1/event-registrations/check?event_id={event_id}", headers=auth_headers(user_a_token))
    serialized = str(resp.get_json())
    assert "provider_customer_id" not in serialized
    assert "payment_reference" not in serialized


# ===========================================================================
# 68-71: Capacity
# ===========================================================================


def test_68_active_circle_registration_occupies_seat(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    from app.services.event_registrations import count_active_registrations

    with app.app_context():
        assert count_active_registrations(event_id) == 1


def test_69_lapsed_active_circle_registration_still_occupies_seat(client, app, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    _expire_subscription(app, sub_id)

    from app.services.event_registrations import count_active_registrations

    with app.app_context():
        assert count_active_registrations(event_id) == 1


def test_70_cancelled_registration_does_not_occupy_seat(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    registration = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{registration.id}/cancel", headers=auth_headers(user_a_token))

    from app.services.event_registrations import count_active_registrations

    with app.app_context():
        assert count_active_registrations(event_id) == 0


def test_71_capacity_race_safety_existing_behavior_intact(client, app, user_a_token, user_b_token):
    _give_active_circle(app, USER_A["email"])
    _give_active_circle(app, USER_B["email"])
    event_id = _make_event(app, access_type="circle_only", capacity=1)
    first = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    second = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token))
    assert first.status_code == 200
    assert second.status_code == 409
    assert second.get_json()["error"]["code"] == "capacity_full"


# ===========================================================================
# 72-78: Status / window regressions
# ===========================================================================


def test_72_cancelled_event_registration_remains_blocked(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", status="cancelled")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "event_cancelled"


def test_73_postponed_event_registration_blocked(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", status="postponed")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "event_postponed"


def test_74_past_event_registration_blocked(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", date=date.today() - timedelta(days=5))
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "event_past"


def test_75_registration_deadline_blocked(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", registration_deadline=date.today() - timedelta(days=1))
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "registration_closed"


def test_76_sold_out_blocked(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only", sold_out=True)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "sold_out"


def test_77_external_registration_still_rejected_from_wsf_endpoint(client, app, user_a_token):
    event_id = _make_event(app, access_type="public", registration_mode="external")
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "external_registration"


def test_78_registration_not_required_still_rejected(client, app, user_a_token):
    event_id = _make_event(app, access_type="public", registration_required=False)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "registration_not_required"


# ===========================================================================
# 79-83: Privacy / regressions
# ===========================================================================


def test_79_public_api_never_exposes_attendee_pii(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    slug = _event_slug(app, event_id)

    detail = client.get(f"/api/v1/events/{slug}")
    serialized = str(detail.get_json())
    assert USER_A["email"] not in serialized

    listing = client.get("/api/v1/events")
    assert USER_A["email"] not in str(listing.get_json())


def test_80_admin_attendee_listing_still_requires_events_manage(client, app, no_permission_token):
    event_id = _make_event(app, access_type="circle_only")
    resp = client.get(f"/api/v1/events/{event_id}/registrations", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_81_event_save_bookmark_independence_remains(client, app, user_a_token):
    event_id = _make_event(app, access_type="circle_only")
    save_resp = client.post(
        "/api/v1/saved", json={"content_type": "event", "content_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert save_resp.status_code == 200
    assert _count_registrations(app, event_id) == 0  # saving never registers, never requires Circle


def test_82_learning_enrollment_remains_independent_of_event_registration(client, app, user_a_token):
    from app.extensions import db
    from app.models.people import Author

    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    from app.models.learning import LearningProgram

    with app.app_context():
        author = Author.query.filter_by(slug="evtcircle-instructor").first()
        if author is None:
            author = Author(slug="evtcircle-instructor", name="Instructor", status="active")
            db.session.add(author)
            db.session.commit()
        program = LearningProgram(
            slug=_slug("program"), title="Program", overview=[], status="published", access_type="free",
            primary_instructor_id=author.id,
        )
        db.session.add(program)
        db.session.commit()
        program_id = program.id

    from app.models.learning_enrollment import LearningEnrollment

    with app.app_context():
        assert LearningEnrollment.query.filter_by(learning_program_id=program_id).count() == 0


def test_83_circle_event_registration_does_not_create_learning_enrollment(client, app, user_a_token):
    _give_active_circle(app, USER_A["email"])
    event_id = _make_event(app, access_type="circle_only")
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    from app.models.learning_enrollment import LearningEnrollment

    with app.app_context():
        assert LearningEnrollment.query.count() == 0


# ===========================================================================
# 84-85: ?access_type=circle_only list filter (Module 9 — WSF Circle Member
# Content Hub needs a way to ask the public list for only circle_only
# events, the same equality filter Resources/Learning already supported;
# this never changes entitlement, only which rows are returned).
# ===========================================================================


def test_84_access_type_filter_returns_only_circle_only_events(client, app):
    _make_event(app, access_type="public", title="Public Filter Event")
    circle_id = _make_event(app, access_type="circle_only", title="Circle Filter Event")
    resp = client.get("/api/v1/events?access_type=circle_only")
    items = resp.get_json()["data"]
    assert all(e["access_type"] == "circle_only" for e in items)
    assert any(e["id"] == circle_id for e in items)


def test_85_access_type_filter_still_excludes_virtual_link(client, app):
    _make_event(app, access_type="circle_only", virtual_link="https://meet.example.org/filtered-secret-room")
    resp = client.get("/api/v1/events?access_type=circle_only")
    assert "filtered-secret-room" not in str(resp.get_json())
