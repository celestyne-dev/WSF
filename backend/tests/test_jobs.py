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


def test_job_archived_status_marks_is_closed(client, manager_token):
    create = client.post(
        "/api/v1/jobs", json=_base_payload(status="published"), headers=auth_headers(manager_token)
    )
    slug = create.get_json()["data"]["slug"]

    closed = client.put(
        f"/api/v1/jobs/{slug}", json=_base_payload(status="archived"), headers=auth_headers(manager_token)
    )
    assert closed.status_code == 200
    assert closed.get_json()["data"]["is_closed"] is True
    # Archived jobs remain accessible directly, matching "applications closed" UX.
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


def test_job_structured_lists_persist(client, manager_token):
    payload = _base_payload(
        responsibilities=["Own the roadmap", "Partner with engineering"],
        requirements=["6+ years experience"],
        qualifications=["Bachelor's degree"],
        skills=["SQL", "Product strategy"],
        benefits=["Health insurance", "  ", ""],
    )
    resp = client.post("/api/v1/jobs", json=payload, headers=auth_headers(manager_token))
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["responsibilities"] == ["Own the roadmap", "Partner with engineering"]
    assert data["requirements"] == ["6+ years experience"]
    assert data["qualifications"] == ["Bachelor's degree"]
    assert data["skills"] == ["SQL", "Product strategy"]
    # Blank/whitespace-only entries are dropped rather than stored as noise.
    assert data["benefits"] == ["Health insurance"]


def test_job_city_field_persists_and_filters(client, manager_token):
    resp = client.post(
        "/api/v1/jobs", json=_base_payload(city="Nairobi", status="published"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["city"] == "Nairobi"

    filtered = client.get("/api/v1/jobs?city=Nairobi")
    assert filtered.status_code == 200
    assert len(filtered.get_json()["data"]) == 1


def test_job_salary_visible_hides_salary_from_public(client, manager_token):
    create = client.post(
        "/api/v1/jobs",
        json=_base_payload(
            status="published", salaryMin=90000, salaryMax=110000, currency="USD", salaryVisible=False
        ),
        headers=auth_headers(manager_token),
    )
    assert create.status_code == 201
    slug = create.get_json()["data"]["slug"]

    public_detail = client.get(f"/api/v1/jobs/{slug}")
    assert public_detail.status_code == 200
    public_data = public_detail.get_json()["data"]
    assert public_data["salary_min"] is None
    assert public_data["salary_max"] is None

    manager_detail = client.get(f"/api/v1/jobs/{slug}", headers=auth_headers(manager_token))
    manager_data = manager_detail.get_json()["data"]
    assert manager_data["salary_min"] == 90000
    assert manager_data["salary_max"] == 110000


def test_job_application_email_validation(client, manager_token):
    invalid = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl=None, applicationEmail="not-an-email"),
        headers=auth_headers(manager_token),
    )
    assert invalid.status_code == 422

    valid = client.post(
        "/api/v1/jobs",
        json=_base_payload(applicationUrl=None, applicationEmail="careers@example.com"),
        headers=auth_headers(manager_token),
    )
    assert valid.status_code == 201
    assert valid.get_json()["data"]["application_email"] == "careers@example.com"


def test_job_publish_allows_email_only_application_destination(client, manager_token):
    resp = client.post(
        "/api/v1/jobs",
        json=_base_payload(status="published", applicationUrl=None, applicationEmail="careers@example.com"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201


def test_job_review_status_is_valid_and_not_publicly_visible(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(status="review"), headers=auth_headers(manager_token))
    assert resp.status_code == 201
    slug = resp.get_json()["data"]["slug"]

    anon = client.get(f"/api/v1/jobs/{slug}")
    assert anon.status_code == 404


def test_job_closed_status_no_longer_valid(client, manager_token):
    resp = client.post("/api/v1/jobs", json=_base_payload(status="closed"), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_job_scheduled_status_becomes_visible_once_published_date_arrives(client, manager_token):
    from datetime import date, timedelta

    future = client.post(
        "/api/v1/jobs",
        json=_base_payload(status="scheduled", publishedDate=str(date.today() + timedelta(days=5))),
        headers=auth_headers(manager_token),
    )
    assert future.status_code == 201
    future_slug = future.get_json()["data"]["slug"]
    assert future.get_json()["data"]["is_scheduled"] is True

    anon_future = client.get(f"/api/v1/jobs/{future_slug}")
    assert anon_future.status_code == 404

    today = client.post(
        "/api/v1/jobs",
        json=_base_payload(status="scheduled", publishedDate=str(date.today()), title="Scheduled Today Role"),
        headers=auth_headers(manager_token),
    )
    assert today.status_code == 201
    today_slug = today.get_json()["data"]["slug"]
    assert today.get_json()["data"]["is_scheduled"] is False

    anon_today = client.get(f"/api/v1/jobs/{today_slug}")
    assert anon_today.status_code == 200

    listed = client.get("/api/v1/jobs")
    assert today_slug in [j["slug"] for j in listed.get_json()["data"]]
    assert future_slug not in [j["slug"] for j in listed.get_json()["data"]]


def test_job_sort_by_deadline_and_closing_within_days_filter(client, manager_token):
    from datetime import date, timedelta

    soon = client.post(
        "/api/v1/jobs",
        json=_base_payload(status="published", title="Closes Soon Role", deadline=str(date.today() + timedelta(days=3))),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    later = client.post(
        "/api/v1/jobs",
        json=_base_payload(status="published", title="Closes Later Role", deadline=str(date.today() + timedelta(days=60))),
        headers=auth_headers(manager_token),
    ).get_json()["data"]

    sorted_resp = client.get("/api/v1/jobs?sort=deadline")
    slugs_in_order = [j["slug"] for j in sorted_resp.get_json()["data"]]
    assert slugs_in_order.index(soon["slug"]) < slugs_in_order.index(later["slug"])

    closing_soon = client.get("/api/v1/jobs?closingWithinDays=7")
    closing_slugs = [j["slug"] for j in closing_soon.get_json()["data"]]
    assert soon["slug"] in closing_slugs
    assert later["slug"] not in closing_slugs


def test_job_sponsor_relationship(client, app, manager_token, organization_id):
    with app.app_context():
        from app.extensions import db
        from app.models.commerce import Sponsor

        sponsor = Sponsor(campaign_name="Job Board Sponsorship", organization_id=organization_id, tier="Gold", status="active")
        db.session.add(sponsor)
        db.session.commit()
        sponsor_id = sponsor.id

    resp = client.post(
        "/api/v1/jobs", json=_base_payload(sponsorId=sponsor_id, sponsored=True), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["sponsor_id"] == sponsor_id
    assert data["sponsor"]["tier"] == "Gold"
