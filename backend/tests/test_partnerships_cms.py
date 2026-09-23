import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "partnerships-manager@example.com",
    "password": "supersecret1",
    "first_name": "Diana",
    "last_name": "Kioko",
    "country_code": "KE",
}

ADMIN_PAYLOAD = {
    "email": "partnerships-admin@example.com",
    "password": "supersecret1",
    "first_name": "Site",
    "last_name": "Admin",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "partnerships-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
}


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
def manager(client, app):
    token, user_id = _register_with_role(client, app, MANAGER_PAYLOAD, "partnerships_manager")
    return {"token": token, "id": user_id}


@pytest.fixture()
def manager_token(manager):
    return manager["token"]


@pytest.fixture()
def admin_token(client, app):
    token, _ = _register_with_role(client, app, ADMIN_PAYLOAD, "admin")
    return token


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_organization(app, slug="brand-co", name="Brand Co", country_code="US"):
    from app.extensions import db
    from app.models.people import Organization

    with app.app_context():
        org = Organization.query.filter_by(slug=slug).first()
        if org is None:
            org = Organization(slug=slug, name=name, country_code=country_code)
            db.session.add(org)
            db.session.commit()
        return org.slug


def _base_payload(**overrides):
    payload = {
        "contactName": "Jane Doe",
        "email": "jane@brandco.com",
        "company": "Brand Co",
        "website": "https://brandco.com",
        "partnershipType": "Brand Partnership",
        "subject": "Q1 campaign collaboration",
        "message": "We would like to explore a partnership for our Q1 campaign.",
        "consentGiven": True,
    }
    payload.update(overrides)
    return payload


def _submit(client, **overrides):
    return client.post("/api/v1/partnerships/inquiries", json=_base_payload(**overrides))


# ---------------------------------------------------------------------------
# Public submission
# ---------------------------------------------------------------------------


def test_submit_inquiry_success_and_confirmation_is_trimmed(client):
    resp = _submit(client)
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert set(data.keys()) == {"company", "status", "submittedAt"}
    assert data["status"] == "new"


def test_submit_requires_contact_name(client):
    payload = _base_payload()
    del payload["contactName"]
    resp = client.post("/api/v1/partnerships/inquiries", json=payload)
    assert resp.status_code == 422


def test_submit_requires_company(client):
    payload = _base_payload()
    del payload["company"]
    resp = client.post("/api/v1/partnerships/inquiries", json=payload)
    assert resp.status_code == 422


def test_submit_invalid_email_rejected(client):
    resp = _submit(client, email="not-an-email")
    assert resp.status_code == 422


def test_submit_invalid_website_rejected(client):
    resp = _submit(client, website="not a url")
    assert resp.status_code == 422


def test_submit_invalid_partnership_type_rejected(client):
    resp = _submit(client, partnershipType="Not A Real Type")
    assert resp.status_code == 422


def test_submit_without_consent_rejected(client):
    resp = _submit(client, consentGiven=False)
    assert resp.status_code == 422


def test_submit_allows_two_legitimate_inquiries_without_merging(client, app):
    first = _submit(client, subject="First inquiry")
    second = _submit(client, subject="Second, unrelated inquiry")
    assert first.status_code == 201
    assert second.status_code == 201

    from app.models.commerce import PartnershipInquiry

    with app.app_context():
        assert PartnershipInquiry.query.filter_by(email="jane@brandco.com").count() == 2


# ---------------------------------------------------------------------------
# Privacy — public can never read/list
# ---------------------------------------------------------------------------


def test_public_cannot_list_inquiries(client):
    _submit(client)
    resp = client.get("/api/v1/partnerships/inquiries")
    assert resp.status_code == 401


def test_public_cannot_read_inquiry_detail(client, app):
    _submit(client)
    from app.models.commerce import PartnershipInquiry

    with app.app_context():
        inquiry_id = PartnershipInquiry.query.first().id
    resp = client.get(f"/api/v1/partnerships/inquiries/{inquiry_id}")
    assert resp.status_code == 401


def test_no_permission_user_cannot_list(client, no_permission_token):
    resp = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin list / search / filter
# ---------------------------------------------------------------------------


def test_partnerships_manager_can_list(client, manager_token):
    _submit(client)
    resp = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]) == 1
    row = resp.get_json()["data"][0]
    assert row["email"] == "jane@brandco.com"
    assert "notes" in row


def test_admin_list_filter_by_status(client, manager_token):
    _submit(client, subject="Inquiry A")
    _submit(client, subject="Inquiry B", email="other@example.com")

    from app.extensions import db

    resp_all = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = resp_all.get_json()["data"][0]["id"]
    client.patch(f"/api/v1/partnerships/inquiries/{inquiry_id}/status", json={"status": "reviewing"}, headers=auth_headers(manager_token))

    reviewing = client.get("/api/v1/partnerships/inquiries?status=reviewing", headers=auth_headers(manager_token))
    assert len(reviewing.get_json()["data"]) == 1
    new_only = client.get("/api/v1/partnerships/inquiries?status=new", headers=auth_headers(manager_token))
    assert len(new_only.get_json()["data"]) == 1


def test_admin_search_by_company_and_email(client, manager_token):
    _submit(client, company="Acme Corp", email="lead@acme.com")
    _submit(client, company="Zeta Industries", email="lead@zeta.com")

    resp = client.get("/api/v1/partnerships/inquiries?q=Acme", headers=auth_headers(manager_token))
    rows = resp.get_json()["data"]
    assert len(rows) == 1
    assert rows[0]["company"] == "Acme Corp"


# ---------------------------------------------------------------------------
# Admin update / status / assignment / organization link / notes
# ---------------------------------------------------------------------------


def test_admin_update_inquiry_fields(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    resp = client.patch(
        f"/api/v1/partnerships/inquiries/{inquiry_id}",
        json={"estimatedValue": 5000, "currency": "USD", "commercialNotes": "Budget confirmed by finance."},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["estimated_value"] == 5000
    assert resp.get_json()["data"]["currency"] == "USD"


def test_admin_update_rejects_negative_commercial_value(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    resp = client.patch(
        f"/api/v1/partnerships/inquiries/{inquiry_id}", json={"estimatedValue": -100}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_status_transitions_and_invalid_status_rejected(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    for status in ("reviewing", "contacted", "qualified", "proposal", "active"):
        resp = client.patch(
            f"/api/v1/partnerships/inquiries/{inquiry_id}/status", json={"status": status}, headers=auth_headers(manager_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == status

    invalid = client.patch(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/status", json={"status": "won"}, headers=auth_headers(manager_token)
    )
    assert invalid.status_code == 422


def test_assign_and_unassign_owner(client, manager):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager["token"]))
    inquiry_id = listed.get_json()["data"][0]["id"]

    assign = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/assign",
        json={"assignedToId": manager["id"]},
        headers=auth_headers(manager["token"]),
    )
    assert assign.status_code == 200
    assert assign.get_json()["data"]["assigned_to"]["id"] == manager["id"]

    unassign = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/assign", json={}, headers=auth_headers(manager["token"])
    )
    assert unassign.status_code == 200
    assert unassign.get_json()["data"]["assigned_to"] is None


def test_assign_to_nonexistent_user_rejected(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    resp = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/assign", json={"assignedToId": 999999}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 404


def test_link_and_unlink_organization(client, app, manager_token):
    org_slug = _make_organization(app)
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    link = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/organization",
        json={"organizationSlug": org_slug},
        headers=auth_headers(manager_token),
    )
    assert link.status_code == 200
    assert link.get_json()["data"]["organization"]["slug"] == org_slug

    unlink = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/organization", json={}, headers=auth_headers(manager_token)
    )
    assert unlink.status_code == 200
    assert unlink.get_json()["data"]["organization"] is None


def test_link_unknown_organization_rejected(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    resp = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/organization",
        json={"organizationSlug": "does-not-exist"},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 404


def test_internal_note_added_and_never_leaks_publicly(client, manager_token):
    resp = _submit(client)
    assert set(resp.get_json()["data"].keys()) == {"company", "status", "submittedAt"}

    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    add_note = client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/notes",
        json={"body": "Requested audience demographics."},
        headers=auth_headers(manager_token),
    )
    assert add_note.status_code == 201
    notes = add_note.get_json()["data"]["notes"]
    assert len(notes) == 1
    assert notes[0]["body"] == "Requested audience demographics."
    assert notes[0]["user"]["email"] == MANAGER_PAYLOAD["email"]


def test_archive_sets_status(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    resp = client.post(f"/api/v1/partnerships/inquiries/{inquiry_id}/archive", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "archived"

    # Archived records remain searchable by authorized admins.
    still_listed = client.get("/api/v1/partnerships/inquiries?status=archived", headers=auth_headers(manager_token))
    assert len(still_listed.get_json()["data"]) == 1


def test_history_records_actions(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]

    client.patch(f"/api/v1/partnerships/inquiries/{inquiry_id}/status", json={"status": "reviewing"}, headers=auth_headers(manager_token))
    client.post(f"/api/v1/partnerships/inquiries/{inquiry_id}/notes", json={"body": "Note."}, headers=auth_headers(manager_token))

    history = client.get(f"/api/v1/partnerships/inquiries/{inquiry_id}/history", headers=auth_headers(manager_token))
    assert history.status_code == 200
    actions = [h["action"] for h in history.get_json()["data"]]
    assert "partnership.status_change" in actions
    assert "partnership.note_add" in actions


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


def test_export_requires_permission(client, no_permission_token):
    resp = client.get("/api/v1/partnerships/inquiries/export", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_export_does_not_include_note_bodies(client, manager_token):
    _submit(client)
    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(manager_token))
    inquiry_id = listed.get_json()["data"][0]["id"]
    client.post(
        f"/api/v1/partnerships/inquiries/{inquiry_id}/notes",
        json={"body": "SUPER-SECRET-INTERNAL-NOTE-TEXT"},
        headers=auth_headers(manager_token),
    )

    resp = client.get("/api/v1/partnerships/inquiries/export", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert "SUPER-SECRET-INTERNAL-NOTE-TEXT" not in resp.get_data(as_text=True)
    assert "Brand Co" in resp.get_data(as_text=True)


def test_overview_requires_permission_and_reports_real_counts(client, manager_token):
    denied = client.get("/api/v1/partnerships/overview")
    assert denied.status_code == 401

    _submit(client)
    resp = client.get("/api/v1/partnerships/overview", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.get_json()["data"]["newInquiries"] == 1
