"""Focused tests for WSF-managed event registration — see
app/models/event_registration.py, app/services/event_registrations.py,
app/api/v1/event_registrations.py (self-service), and the registration
endpoints added to app/api/v1/events.py (admin/staff).
"""
import threading
import uuid
from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers

USER_A = {
    "email": "evtreg-user-a@example.com",
    "password": "supersecret1",
    "first_name": "Amina",
    "last_name": "Diallo",
    "country_code": "SN",
}
USER_B = {
    "email": "evtreg-user-b@example.com",
    "password": "supersecret1",
    "first_name": "Beatrice",
    "last_name": "Mwangi",
    "country_code": "KE",
}
MANAGER_PAYLOAD = {
    "email": "evtreg-manager@example.com",
    "password": "supersecret1",
    "first_name": "Amara",
    "last_name": "Nwosu",
    "country_code": "NG",
}
NO_PERMISSION_PAYLOAD = {
    "email": "evtreg-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
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
    # Registration already assigns the base "member" role automatically
    # (see RegisterResource) — no events.manage permission on it, so no
    # extra role assignment is needed to exercise "unauthorized staff".
    return _register(client, NO_PERMISSION_PAYLOAD)


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


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
    )
    defaults.update(overrides)
    with app.app_context():
        event = Event(slug=_slug("event"), **defaults)
        db.session.add(event)
        db.session.commit()
        return event.id


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


def _event_slug(app, event_id):
    from app.extensions import db
    from app.models.opportunity import Event

    with app.app_context():
        return db.session.get(Event, event_id).slug


def _base_event_payload(**overrides):
    payload = {
        "title": "Women in Tech Forum",
        "format": "virtual",
        "shortDescription": "A forum for women in tech.",
        "description": [{"type": "paragraph", "text": "A forum for women in tech."}],
        "date": "2027-03-10",
        "registrationUrl": "https://example.com/register",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# 1-8: basic eligibility / authorization / idempotency
# ---------------------------------------------------------------------------


def test_unauthenticated_cannot_register(client, app):
    event_id = _make_event(app)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id})
    assert resp.status_code == 401


def test_member_can_register_for_free_wsf_event(client, app, user_a_token):
    event_id = _make_event(app, ticket_price=None)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert body["registered"] is True
    assert body["registration"]["status"] == "registered"


def test_community_membership_not_required(client, app, user_a_token):
    from app.models.community import Member

    with app.app_context():
        assert Member.query.count() == 0
    event_id = _make_event(app)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200


def test_duplicate_registration_is_idempotent(client, app, user_a_token):
    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    first = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    second = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["data"]["registered"] is True


def test_unique_event_user_lifecycle_row(client, app, user_a_token):
    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    assert _count_registrations(app, event_id) == 1
    reg = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    assert _count_registrations(app, event_id) == 1


def test_user_cannot_register_another_user(client, app, user_a_token):
    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id, "user_id": 999999}, headers=headers
    )
    assert resp.status_code == 200
    reg = _get_registration_row(app, event_id, USER_A["email"])
    assert reg is not None


def test_external_registration_event_does_not_create_wsf_registration(client, app, user_a_token):
    event_id = _make_event(app, registration_mode="external", registration_url="https://example.com/register")
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "external_registration"
    assert _count_registrations(app, event_id) == 0


def test_no_registration_required_event_rejects_wsf_registration(client, app, user_a_token):
    event_id = _make_event(app, registration_required=False)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "registration_not_required"


# ---------------------------------------------------------------------------
# 9-10, 50: publish validation
# ---------------------------------------------------------------------------


def test_paid_wsf_managed_event_cannot_be_published(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_event_payload(
            registrationMode="wsf", ticketPrice=10, currency="USD", status="published", registrationUrl=None
        ),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_external_paid_event_remains_valid(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_event_payload(
            registrationMode="external",
            ticketPrice=25,
            currency="USD",
            registrationUrl="https://example.com/tickets",
            status="published",
        ),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["registration_mode"] == "external"


def test_event_publish_validation_backward_compatible_for_external_events(client, manager_token):
    missing_url = client.post(
        "/api/v1/events",
        json=_base_event_payload(registrationUrl=None, status="published"),
        headers=auth_headers(manager_token),
    )
    assert missing_url.status_code == 422

    with_url = client.post(
        "/api/v1/events",
        json=_base_event_payload(registrationUrl="https://example.com/register", status="published"),
        headers=auth_headers(manager_token),
    )
    assert with_url.status_code == 201
    assert with_url.get_json()["data"]["registration_mode"] == "external"


# ---------------------------------------------------------------------------
# 11-17: registration window / state eligibility
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status", ["draft", "review", "archived"])
def test_non_public_event_cannot_be_registered(client, app, user_a_token, status):
    event_id = _make_event(app, status=status)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 404


def test_cancelled_event_cannot_be_registered(client, app, user_a_token):
    event_id = _make_event(app, status="cancelled")
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "event_cancelled"


def test_postponed_event_cannot_be_registered(client, app, user_a_token):
    event_id = _make_event(app, status="postponed")
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "event_postponed"


def test_past_event_cannot_be_registered(client, app, user_a_token):
    event_id = _make_event(app, date=date.today() - timedelta(days=5))
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "event_past"


def test_expired_registration_deadline_blocks_registration(client, app, user_a_token):
    event_id = _make_event(app, registration_deadline=date.today() - timedelta(days=1))
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "registration_closed"


def test_sold_out_blocks_registration(client, app, user_a_token):
    event_id = _make_event(app, sold_out=True)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "sold_out"


def test_capacity_full_blocks_registration(client, app, user_a_token, user_b_token):
    event_id = _make_event(app, capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token)
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "capacity_full"


def test_cancelled_registration_frees_capacity(client, app, user_a_token, user_b_token):
    event_id = _make_event(app, capacity=1)
    headers_a = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers_a)
    reg_a = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{reg_a.id}/cancel", headers=headers_a)

    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token)
    )
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 19-23: cancel / re-register
# ---------------------------------------------------------------------------


def test_user_can_cancel_own_active_registration(client, app, user_a_token):
    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    reg = _get_registration_row(app, event_id, USER_A["email"])
    resp = client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["registration"]["status"] == "cancelled"


def test_cancel_is_idempotent(client, app, user_a_token):
    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    reg = _get_registration_row(app, event_id, USER_A["email"])
    first = client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)
    second = client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["data"]["registration"]["status"] == "cancelled"


def test_user_cannot_cancel_another_users_registration(client, app, user_a_token, user_b_token):
    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    reg_a = _get_registration_row(app, event_id, USER_A["email"])
    resp = client.post(f"/api/v1/event-registrations/{reg_a.id}/cancel", headers=auth_headers(user_b_token))
    assert resp.status_code == 404
    reg_a_after = _get_registration_row(app, event_id, USER_A["email"])
    assert reg_a_after.status == "registered"


def test_cancelled_user_can_reregister_if_space_available(client, app, user_a_token):
    event_id = _make_event(app, capacity=5)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    reg = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)
    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    assert resp.status_code == 200
    assert resp.get_json()["data"]["registration"]["status"] == "registered"


def test_cancelled_user_cannot_reregister_when_full(client, app, user_a_token, user_b_token):
    event_id = _make_event(app, capacity=1)
    headers_a = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers_a)
    reg_a = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{reg_a.id}/cancel", headers=headers_a)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token))

    resp = client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers_a)
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "capacity_full"


# ---------------------------------------------------------------------------
# 24-28: check / me / pagination / attendance
# ---------------------------------------------------------------------------


def test_check_endpoint_only_reflects_current_user(client, app, user_a_token, user_b_token):
    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    check_b = client.get(
        f"/api/v1/event-registrations/check?event_id={event_id}", headers=auth_headers(user_b_token)
    )
    assert check_b.get_json()["data"]["registered"] is False

    check_a = client.get(
        f"/api/v1/event-registrations/check?event_id={event_id}", headers=auth_headers(user_a_token)
    )
    assert check_a.get_json()["data"]["registered"] is True


def test_me_only_returns_current_users_registrations(client, app, user_a_token, user_b_token):
    event_a = _make_event(app)
    event_b = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_a}, headers=auth_headers(user_a_token))
    client.post("/api/v1/event-registrations", json={"event_id": event_b}, headers=auth_headers(user_b_token))

    items = client.get("/api/v1/event-registrations/me", headers=auth_headers(user_a_token)).get_json()["data"]
    assert len(items) == 1
    assert items[0]["event"]["id"] == event_a


def test_upcoming_past_filtering(client, app, user_a_token):
    upcoming_event = _make_event(app, date=date.today() + timedelta(days=5))
    past_event = _make_event(app, date=date.today() - timedelta(days=5), registration_mode="wsf")
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": upcoming_event}, headers=headers)
    # Directly insert a past "attended" registration (can't register for a
    # past event through the API — that's its own rejection, tested above).
    from app.extensions import db
    from app.models.event_registration import EventRegistration
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        db.session.add(EventRegistration(event_id=past_event, user_id=user.id, status="attended"))
        db.session.commit()

    upcoming = client.get("/api/v1/event-registrations/me?when=upcoming", headers=headers).get_json()["data"]
    assert [i["event"]["id"] for i in upcoming] == [upcoming_event]

    past = client.get("/api/v1/event-registrations/me?when=past", headers=headers).get_json()["data"]
    assert [i["event"]["id"] for i in past] == [past_event]


def test_pagination_me(client, app, user_a_token):
    headers = auth_headers(user_a_token)
    event_ids = [_make_event(app, date=date.today() + timedelta(days=10 + i)) for i in range(3)]
    for event_id in event_ids:
        client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)

    resp = client.get("/api/v1/event-registrations/me?per_page=2&page=1", headers=headers)
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 3
    assert body["meta"]["total_pages"] == 2


def test_attendance_state_accurate(client, app, user_a_token, manager_token):
    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    reg = _get_registration_row(app, event_id, USER_A["email"])

    client.patch(
        f"/api/v1/events/{event_id}/registrations/{reg.id}", json={"status": "attended"}, headers=auth_headers(manager_token)
    )

    items = client.get("/api/v1/event-registrations/me", headers=headers).get_json()["data"]
    assert items[0]["status"] == "attended"
    assert items[0]["attended_at"] is not None


# ---------------------------------------------------------------------------
# 29-35: private virtual link protection
# ---------------------------------------------------------------------------


def test_unauthenticated_public_api_does_not_expose_private_virtual_link(client, app):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/secret", virtual_link_public=False)
    slug = _event_slug(app, event_id)

    resp = client.get(f"/api/v1/events/{slug}")
    assert "virtual_link" not in resp.get_json()["data"] or resp.get_json()["data"]["virtual_link"] is None


def test_authenticated_non_registrant_does_not_receive_virtual_link(client, app, user_a_token):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/secret", virtual_link_public=False)
    slug = _event_slug(app, event_id)

    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] is None


def test_cancelled_registrant_does_not_receive_virtual_link(client, app, user_a_token):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/secret", virtual_link_public=False)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    reg = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)

    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=headers)
    assert resp.get_json()["data"]["virtual_link"] is None


def test_active_registrant_can_access_virtual_link(client, app, user_a_token):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/secret", virtual_link_public=False)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)

    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=headers)
    assert resp.get_json()["data"]["virtual_link"] == "https://zoom.example.com/secret"

    me_items = client.get("/api/v1/event-registrations/me", headers=headers).get_json()["data"]
    assert me_items[0]["event"]["virtual_link"] == "https://zoom.example.com/secret"


def test_public_virtual_link_still_works_when_marked_public(client, app):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/open", virtual_link_public=True)
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}")
    assert resp.get_json()["data"]["virtual_link"] == "https://zoom.example.com/open"


def test_external_registrant_not_assumed_authorized_for_virtual_link(client, app, user_a_token):
    event_id = _make_event(
        app,
        registration_mode="external",
        registration_url="https://example.com/register",
        virtual_link="https://zoom.example.com/secret",
        virtual_link_public=False,
    )
    slug = _event_slug(app, event_id)
    resp = client.get(f"/api/v1/events/{slug}", headers=auth_headers(user_a_token))
    assert resp.get_json()["data"]["virtual_link"] is None


def test_saved_event_api_does_not_leak_virtual_link(client, app, user_a_token):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/secret", virtual_link_public=False)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/saved", json={"content_type": "event", "content_id": event_id}, headers=headers)

    resp = client.get("/api/v1/saved?type=event", headers=headers)
    items = resp.get_json()["data"]["items"]
    assert len(items) == 1
    assert "virtual_link" not in items[0]["content"]


# ---------------------------------------------------------------------------
# 36-44: admin / staff management + CSV export
# ---------------------------------------------------------------------------


def test_staff_can_list_registrations(client, app, manager_token, user_a_token):
    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    resp = client.get(f"/api/v1/events/{event_id}/registrations", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    body = resp.get_json()["data"]
    assert len(body["items"]) == 1
    assert body["items"][0]["attendee_email"] == USER_A["email"]
    assert body["counts"]["registered"] == 1
    assert body["active_count"] == 1


def test_unauthorized_staff_cannot_list_registrations(client, app, no_permission_token):
    event_id = _make_event(app)
    resp = client.get(f"/api/v1/events/{event_id}/registrations", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_admin_event_scoping_prevents_cross_event_mutation(client, app, manager_token, user_a_token):
    event_1 = _make_event(app)
    event_2 = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_1}, headers=auth_headers(user_a_token))
    reg = _get_registration_row(app, event_1, USER_A["email"])

    resp = client.patch(
        f"/api/v1/events/{event_2}/registrations/{reg.id}", json={"status": "attended"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 404
    reg_after = _get_registration_row(app, event_1, USER_A["email"])
    assert reg_after.status == "registered"


def test_staff_can_mark_attended(client, app, manager_token, user_a_token):
    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    reg = _get_registration_row(app, event_id, USER_A["email"])

    resp = client.patch(
        f"/api/v1/events/{event_id}/registrations/{reg.id}", json={"status": "attended"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "attended"


def test_staff_can_cancel_registration(client, app, manager_token, user_a_token):
    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    reg = _get_registration_row(app, event_id, USER_A["email"])

    resp = client.patch(
        f"/api/v1/events/{event_id}/registrations/{reg.id}", json={"status": "cancelled"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "cancelled"


def test_staff_restore_respects_capacity(client, app, manager_token, user_a_token, user_b_token):
    event_id = _make_event(app, capacity=1)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    reg_a = _get_registration_row(app, event_id, USER_A["email"])
    manager_headers = auth_headers(manager_token)
    client.patch(f"/api/v1/events/{event_id}/registrations/{reg_a.id}", json={"status": "cancelled"}, headers=manager_headers)

    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_b_token))

    blocked = client.patch(
        f"/api/v1/events/{event_id}/registrations/{reg_a.id}", json={"status": "registered"}, headers=manager_headers
    )
    assert blocked.status_code == 409
    assert blocked.get_json()["error"]["code"] == "capacity_full"

    reg_b = _get_registration_row(app, event_id, USER_B["email"])
    client.patch(f"/api/v1/events/{event_id}/registrations/{reg_b.id}", json={"status": "cancelled"}, headers=manager_headers)

    restored = client.patch(
        f"/api/v1/events/{event_id}/registrations/{reg_a.id}", json={"status": "registered"}, headers=manager_headers
    )
    assert restored.status_code == 200
    assert restored.get_json()["data"]["status"] == "registered"


def test_csv_export_requires_manage_permission(client, app, no_permission_token):
    event_id = _make_event(app)
    resp = client.get(f"/api/v1/events/{event_id}/registrations/export", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_csv_contains_expected_attendee_fields(client, app, manager_token, user_a_token):
    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    resp = client.get(f"/api/v1/events/{event_id}/registrations/export", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.headers["Content-Disposition"].startswith("attachment;")
    body = resp.get_data(as_text=True)
    assert "name,email,country,status,registered_at,attended_at,cancelled_at" in body
    assert USER_A["email"] in body


def test_csv_never_includes_private_virtual_link(client, app, manager_token, user_a_token):
    event_id = _make_event(app, virtual_link="https://zoom.example.com/super-secret", virtual_link_public=False)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))

    resp = client.get(f"/api/v1/events/{event_id}/registrations/export", headers=auth_headers(manager_token))
    body = resp.get_data(as_text=True)
    assert "zoom.example.com" not in body


# ---------------------------------------------------------------------------
# 45-48: email / audit / forced password change
# ---------------------------------------------------------------------------


def test_registration_email_failure_does_not_undo_registration(client, app, user_a_token, monkeypatch):
    import app.api.v1.event_registrations as event_registrations_api

    monkeypatch.setattr(event_registrations_api, "send_email", lambda **kwargs: False)
    event_id = _make_event(app)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["registered"] is True
    assert _count_registrations(app, event_id) == 1


def test_self_service_actions_do_not_add_noisy_audit_entries(client, app, user_a_token):
    from app.models.audit import AuditLog

    with app.app_context():
        before = AuditLog.query.count()

    event_id = _make_event(app)
    headers = auth_headers(user_a_token)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=headers)
    reg = _get_registration_row(app, event_id, USER_A["email"])
    client.post(f"/api/v1/event-registrations/{reg.id}/cancel", headers=headers)

    with app.app_context():
        after = AuditLog.query.count()
    assert after == before


def test_staff_status_change_is_audit_logged_with_safe_metadata(client, app, manager_token, user_a_token):
    from app.models.audit import AuditLog

    event_id = _make_event(app)
    client.post("/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token))
    reg = _get_registration_row(app, event_id, USER_A["email"])

    client.patch(
        f"/api/v1/events/{event_id}/registrations/{reg.id}", json={"status": "attended"}, headers=auth_headers(manager_token)
    )

    with app.app_context():
        entry = AuditLog.query.filter_by(action="event_registration.status_changed").first()
        assert entry is not None
        assert entry.changes["status_from"] == "registered"
        assert entry.changes["status_to"] == "attended"
        assert USER_A["email"] not in str(entry.changes)
        assert USER_A["first_name"] not in str(entry.changes)


def test_forced_password_change_blocks_registration(client, app, user_a_token):
    from app.extensions import db
    from app.models.user import User

    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        user.must_change_password = True
        db.session.commit()

    event_id = _make_event(app)
    resp = client.post(
        "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(user_a_token)
    )
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "password_change_required"


# ---------------------------------------------------------------------------
# 49: race/capacity regression
# ---------------------------------------------------------------------------


def test_concurrent_registration_never_exceeds_capacity(app, client):
    event_id = _make_event(app, capacity=1)

    payload_a = dict(USER_A, email="evtreg-race-a@example.com")
    payload_b = dict(USER_B, email="evtreg-race-b@example.com")
    token_a = _register(client, payload_a)
    token_b = _register(client, payload_b)

    results = {}

    def _attempt(name, token):
        with app.test_client() as thread_client:
            resp = thread_client.post(
                "/api/v1/event-registrations", json={"event_id": event_id}, headers=auth_headers(token)
            )
            results[name] = resp.status_code

    t1 = threading.Thread(target=_attempt, args=("a", token_a))
    t2 = threading.Thread(target=_attempt, args=("b", token_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    statuses = sorted(results.values())
    assert statuses == [200, 409]
    assert _count_registrations(app, event_id) == 1
