import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "jobs-manager@example.com",
    "password": "supersecret1",
    "first_name": "Tariro",
    "last_name": "Chikafu",
    "country_code": "US",
}

EMPLOYER_PAYLOAD = {
    "email": "jobs-employer@example.com",
    "password": "supersecret1",
    "first_name": "Wanjiru",
    "last_name": "Kariuki",
    "country_code": "KE",
}

OTHER_EMPLOYER_PAYLOAD = {
    "email": "jobs-employer-2@example.com",
    "password": "supersecret1",
    "first_name": "Second",
    "last_name": "Employer",
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
def employer_token(client, app):
    return _register_with_role(client, app, EMPLOYER_PAYLOAD, "employer")


@pytest.fixture()
def other_employer_token(client, app):
    return _register_with_role(client, app, OTHER_EMPLOYER_PAYLOAD, "employer")


@pytest.fixture()
def organization_id(client, app):
    org_admin_token = _register_with_role(
        client,
        app,
        {
            "email": "jobs-org-admin@example.com",
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
        "title": "Senior Software Engineer",
        "companyName": "Baraza Ventures",
        "countryCode": "KE",
        "workMode": "Remote",
        "remoteScope": "worldwide",
        "employmentType": "Full-time",
        "careerLevel": "Senior",
        "description": [{"type": "paragraph", "text": "Join our engineering team building fintech infrastructure."}],
        "applicationUrl": "https://example.com/apply/senior-engineer",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_job_create_requires_permission(client):
    resp = client.post("/api/v1/jobs", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_job_create_update_slug_uniqueness_and_organization(client, manager_token, organization_id):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(organizationId=organization_id), headers=auth_headers(manager_token)
    )
    assert create.status_code == 201
    job = create.get_json()["data"]
    assert job["slug"] == "senior-software-engineer"
    assert job["organization"]["slug"] == "baraza-ventures"
    assert job["company_name"] == "Baraza Ventures"
    assert job["description"] == [
        {"type": "paragraph", "text": "Join our engineering team building fintech infrastructure."}
    ]

    dupe = client.post(
        "/api/v1/jobs", json=_base_payload(organizationId=organization_id), headers=auth_headers(manager_token)
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != job["slug"]

    update = client.put(
        f"/api/v1/jobs/{job['slug']}",
        json=_base_payload(organizationId=organization_id, title="Staff Software Engineer"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["title"] == "Staff Software Engineer"


def test_job_requires_employer_name_or_organization(client, manager_token):
    payload = _base_payload()
    payload.pop("companyName")
    resp = client.post("/api/v1/jobs", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_job_remote_geography(client, manager_token):
    create = client.post(
        "/api/v1/jobs",
        json=_base_payload(workMode="Remote", remoteScope="region", remoteRegion="Africa"),
        headers=auth_headers(manager_token),
    )
    assert create.status_code == 201
    job = create.get_json()["data"]
    assert job["remote_scope"] == "region"
    assert job["remote_region"] == "Africa"


def test_job_invalid_employment_type_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/jobs", json=_base_payload(employmentType="Freelance-ish"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_job_salary_and_currency(client, manager_token):
    create = client.post(
        "/api/v1/jobs",
        json=_base_payload(salaryMin=80000, salaryMax=110000, currency="USD", salaryPeriod="year"),
        headers=auth_headers(manager_token),
    )
    assert create.status_code == 201
    job = create.get_json()["data"]
    assert job["salary_min"] == 80000
    assert job["currency"] == "USD"

    bad_range = client.post(
        "/api/v1/jobs",
        json=_base_payload(salaryMin=110000, salaryMax=80000),
        headers=auth_headers(manager_token),
    )
    assert bad_range.status_code == 422


def test_job_application_url_validation(client, manager_token):
    bad = client.post(
        "/api/v1/jobs", json=_base_payload(applicationUrl="not-a-url"), headers=auth_headers(manager_token)
    )
    assert bad.status_code == 422


def test_job_deadline_after_expiry_rejected(client, manager_token):
    bad = client.post(
        "/api/v1/jobs",
        json=_base_payload(deadline="2027-06-01", expiryDate="2027-01-01"),
        headers=auth_headers(manager_token),
    )
    assert bad.status_code == 422


def test_job_publish_requires_application_url(client, manager_token):
    payload = _base_payload(status="published")
    payload.pop("applicationUrl")
    resp = client.post("/api/v1/jobs", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_job_status_and_public_visibility(client, manager_token):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(status="draft"), headers=auth_headers(manager_token)
    )
    slug = create.get_json()["data"]["slug"]

    hidden = client.get(f"/api/v1/jobs/{slug}")
    assert hidden.status_code == 404

    preview = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert preview.status_code == 200

    publish = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(status="published"), headers=auth_headers(manager_token)
    )
    assert publish.status_code == 200
    assert publish.get_json()["data"]["status"] == "published"

    now_public = client.get(f"/api/v1/jobs/{slug}")
    assert now_public.status_code == 200

    listing = client.get("/api/v1/jobs")
    slugs = [j["slug"] for j in listing.get_json()["data"]]
    assert slug in slugs


def test_job_expired_excluded_from_public_listing_but_visible_on_detail(client, manager_token):
    create = client.post(
        "/api/v1/jobs",
        json=_base_payload(status="published", expiryDate="2020-01-01"),
        headers=auth_headers(manager_token),
    )
    slug = create.get_json()["data"]["slug"]
    assert create.get_json()["data"]["is_closed"] is True

    listing = client.get("/api/v1/jobs")
    slugs = [j["slug"] for j in listing.get_json()["data"]]
    assert slug not in slugs

    detail = client.get(f"/api/v1/jobs/{slug}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["is_closed"] is True


def test_job_closed_status_marks_is_closed(client, manager_token):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(status="published"), headers=auth_headers(manager_token)
    )
    slug = create.get_json()["data"]["slug"]

    closed = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(status="closed"), headers=auth_headers(manager_token)
    )
    assert closed.status_code == 200
    assert closed.get_json()["data"]["is_closed"] is True
    # Closed jobs remain accessible directly, matching "applications closed" UX.
    detail = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert detail.status_code == 200


def test_job_featured_and_sponsored_flags(client, manager_token):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(featured=True, sponsored=True), headers=auth_headers(manager_token)
    )
    assert create.status_code == 201
    job = create.get_json()["data"]
    assert job["featured"] is True
    assert job["sponsored"] is True


def test_job_employer_can_only_edit_own_jobs(client, employer_token, other_employer_token):
    create = client.post("/api/v1/jobs", json=_base_payload(), headers=auth_headers(employer_token))
    assert create.status_code == 201
    slug = create.get_json()["data"]["slug"]

    blocked = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(title="Hijacked"), headers=auth_headers(other_employer_token)
    )
    assert blocked.status_code == 403

    allowed = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(title="My Own Edit"), headers=auth_headers(employer_token)
    )
    assert allowed.status_code == 200
    assert allowed.get_json()["data"]["title"] == "My Own Edit"

    blocked_delete = client.delete(f"/api/v1/jobs/{slug}", headers=auth_headers(other_employer_token))
    assert blocked_delete.status_code == 403


def test_job_serializer_excludes_posted_by_id(client, manager_token):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(status="published"), headers=auth_headers(manager_token)
    )
    assert "posted_by_id" not in create.get_json()["data"]

    slug = create.get_json()["data"]["slug"]
    public_view = client.get(f"/api/v1/jobs/{slug}")
    assert "posted_by_id" not in public_view.get_json()["data"]


def test_job_duplicate(client, manager_token):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(status="published"), headers=auth_headers(manager_token)
    )
    slug = create.get_json()["data"]["slug"]

    duplicate = client.post(f"/api/v1/jobs/{slug}/duplicate", headers=auth_headers(manager_token))
    assert duplicate.status_code == 201
    dup_data = duplicate.get_json()["data"]
    assert dup_data["slug"] != slug
    assert dup_data["status"] == "draft"
    assert dup_data["title"] == "Senior Software Engineer"
    assert dup_data["description"] == create.get_json()["data"]["description"]


def test_job_delete_requires_permission(client, manager_token, employer_token):
    create = client.post("/api/v1/jobs", json=_base_payload(), headers=auth_headers(manager_token))
    slug = create.get_json()["data"]["slug"]

    blocked = client.delete(f"/api/v1/jobs/{slug}", headers=auth_headers(employer_token))
    assert blocked.status_code == 403

    deleted = client.delete(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    assert gone.status_code == 404
