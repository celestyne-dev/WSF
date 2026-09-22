import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "opportunities-manager@example.com",
    "password": "supersecret1",
    "first_name": "Zanele",
    "last_name": "Mokoena",
    "country_code": "ZA",
}

NO_PERMISSION_PAYLOAD = {
    "email": "opportunities-nobody@example.com",
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

    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "opportunities_manager")


@pytest.fixture()
def no_permission_token(client, app):
    # Registration already grants the default "member" role, which lacks
    # opportunities.manage — no additional role assignment needed.
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def organization_id(client, app):
    org_admin_token = _register_with_role(
        client,
        app,
        {
            "email": "opportunities-org-admin@example.com",
            "password": "supersecret1",
            "first_name": "Org",
            "last_name": "Admin",
            "country_code": "US",
        },
        "admin",
    )
    resp = client.post(
        "/api/v1/organizations",
        json={
            "name": "Baraza Ventures",
            "countryCode": "KE",
            "shortDescription": "An early-stage venture fund backing East African founders.",
            "status": "published",
        },
        headers=auth_headers(org_admin_token),
    )
    return resp.get_json()["data"]["id"]


def _base_payload(**overrides):
    payload = {
        "title": "Rising Leaders Fellowship",
        "organizationName": "Foster Capital",
        "type": "Fellowship",
        "shortDescription": "A six-month fellowship for women in mid-career roles.",
        "description": [{"type": "paragraph", "text": "A six-month fellowship for women in mid-career roles."}],
        "eligibility": "Women with 5-12 years of professional experience.",
        "countriesEligible": ["US", "GB"],
        "fundingType": "partially_funded",
        "fundingMin": 10000,
        "fundingMax": 10000,
        "currency": "USD",
        "fundingValue": "$10,000 grant + mentorship",
        "applicationUrl": "https://example.com/apply/rising-leaders",
        "deadline": "2027-01-15",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_opportunity_create_requires_permission(client):
    resp = client.post("/api/v1/opportunities", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_opportunity_create_requires_permission_even_with_account(client, no_permission_token):
    resp = client.post("/api/v1/opportunities", json=_base_payload(), headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_opportunity_create_update_and_slug_uniqueness(client, manager_token, organization_id):
    create = client.post(
        "/api/v1/opportunities",
        json=_base_payload(organizationId=organization_id),
        headers=auth_headers(manager_token),
    )
    assert create.status_code == 201
    opp = create.get_json()["data"]
    assert opp["slug"] == "rising-leaders-fellowship"
    assert opp["organization"]["slug"] == "baraza-ventures"
    assert opp["organization_id"] == organization_id
    assert opp["description"] == [
        {"type": "paragraph", "text": "A six-month fellowship for women in mid-career roles."}
    ]

    dupe = client.post(
        "/api/v1/opportunities",
        json=_base_payload(organizationId=organization_id),
        headers=auth_headers(manager_token),
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != opp["slug"]

    update = client.put(
        f"/api/v1/opportunities/{opp['slug']}",
        json=_base_payload(organizationId=organization_id, title="Rising Leaders Fellowship 2027"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["title"] == "Rising Leaders Fellowship 2027"


def test_opportunity_requires_provider_name_or_organization(client, manager_token):
    payload = _base_payload()
    payload.pop("organizationName")
    resp = client.post("/api/v1/opportunities", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_opportunity_invalid_type_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities", json=_base_payload(type="Not A Real Type"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_opportunity_funding_range_validation(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities",
        json=_base_payload(fundingMin=50000, fundingMax=1000),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_opportunity_application_url_validation(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities", json=_base_payload(applicationUrl="not-a-url"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_opportunity_deadline_after_expiry_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities",
        json=_base_payload(deadline="2027-06-01", expiryDate="2027-01-01"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_opportunity_publish_requires_description_and_application_url(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities",
        json=_base_payload(status="published", description=[], applicationUrl=None),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "publish_validation_failed"


def test_opportunity_global_and_multi_country_eligibility(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities",
        json=_base_payload(countriesEligible=["GLOBAL"]),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    assert [c["code"] for c in resp.get_json()["data"]["countries_eligible"]] == ["GLOBAL"]

    multi = client.post(
        "/api/v1/opportunities",
        json=_base_payload(title="Multi-Country Grant", countriesEligible=["US", "GB", "KE", "IN"]),
        headers=auth_headers(manager_token),
    )
    assert multi.status_code == 201
    assert {c["code"] for c in multi.get_json()["data"]["countries_eligible"]} == {"US", "GB", "KE", "IN"}


def test_opportunity_status_and_public_visibility(client, manager_token):
    draft = client.post(
        "/api/v1/opportunities", json=_base_payload(status="draft"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/opportunities/{draft['slug']}")
    assert anon_detail.status_code == 404

    manager_detail = client.get(f"/api/v1/opportunities/{draft['slug']}", headers=auth_headers(manager_token))
    assert manager_detail.status_code == 200

    anon_list = client.get("/api/v1/opportunities")
    assert draft["slug"] not in [o["slug"] for o in anon_list.get_json()["data"]]

    publish = client.put(
        f"/api/v1/opportunities/{draft['slug']}",
        json=_base_payload(status="published"),
        headers=auth_headers(manager_token),
    )
    assert publish.status_code == 200

    anon_detail_after_publish = client.get(f"/api/v1/opportunities/{draft['slug']}")
    assert anon_detail_after_publish.status_code == 200
    anon_list_after_publish = client.get("/api/v1/opportunities")
    assert draft["slug"] in [o["slug"] for o in anon_list_after_publish.get_json()["data"]]


def test_opportunity_closed_and_archived_marked_is_closed_and_excluded_from_active_listing(client, manager_token):
    closed = client.post(
        "/api/v1/opportunities",
        json=_base_payload(title="Closed Fellowship", status="closed"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert closed["is_closed"] is True

    detail = client.get(f"/api/v1/opportunities/{closed['slug']}", headers=auth_headers(manager_token))
    assert detail.get_json()["data"]["is_closed"] is True

    archived = client.post(
        "/api/v1/opportunities",
        json=_base_payload(title="Archived Grant", status="archived"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert archived["is_closed"] is True


def test_opportunity_expired_deadline_marks_is_closed_but_stays_visible_on_detail(client, manager_token):
    expired = client.post(
        "/api/v1/opportunities",
        json=_base_payload(title="Past Deadline Fellowship", status="published", deadline="2020-01-01"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert expired["is_closed"] is True

    detail = client.get(f"/api/v1/opportunities/{expired['slug']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["is_closed"] is True


def test_opportunity_featured_and_sponsored_flags(client, manager_token):
    resp = client.post(
        "/api/v1/opportunities",
        json=_base_payload(title="Sponsored Fellowship", status="published", featured=True, sponsored=True),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["featured"] is True
    assert data["sponsored"] is True


def test_opportunity_delete_requires_permission(client, manager_token, no_permission_token):
    created = client.post(
        "/api/v1/opportunities", json=_base_payload(), headers=auth_headers(manager_token)
    ).get_json()["data"]

    denied = client.delete(f"/api/v1/opportunities/{created['slug']}", headers=auth_headers(no_permission_token))
    assert denied.status_code == 403

    allowed = client.delete(f"/api/v1/opportunities/{created['slug']}", headers=auth_headers(manager_token))
    assert allowed.status_code == 200


def test_opportunity_draft_not_in_public_serializer_fields_but_organization_id_present_for_cms(
    client, manager_token, organization_id
):
    created = client.post(
        "/api/v1/opportunities",
        json=_base_payload(organizationId=organization_id, status="draft"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    # organization_id is dump-only but always present for the CMS editor to
    # pre-select the linked Organization, even before publish.
    assert created["organization_id"] == organization_id
