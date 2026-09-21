import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "opsadmin@example.com",
    "password": "supersecret1",
    "first_name": "Ops",
    "last_name": "Admin",
}


@pytest.fixture()
def admin_token(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=ADMIN_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=ADMIN_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="admin").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_PAYLOAD["email"], "password": ADMIN_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


def test_job_create_and_country_region_filtering(client, admin_token):
    us_job = client.post(
        "/api/v1/jobs",
        json={
            "title": "Senior Product Manager",
            "companyName": "Lumen Analytics",
            "countryCode": "US",
            "employmentType": "Full-time",
            "salaryMin": 145000,
            "salaryMax": 175000,
            "currency": "USD",
        },
        headers=auth_headers(admin_token),
    )
    assert us_job.status_code == 201

    ke_job = client.post(
        "/api/v1/jobs",
        json={"title": "Marketing Manager", "companyName": "Kaziwave", "countryCode": "KE", "currency": "KES"},
        headers=auth_headers(admin_token),
    )
    assert ke_job.status_code == 201

    by_country = client.get("/api/v1/jobs?country=US")
    assert by_country.status_code == 200
    assert [j["title"] for j in by_country.get_json()["data"]] == ["Senior Product Manager"]

    by_region = client.get("/api/v1/jobs?region=Africa")
    assert by_region.status_code == 200
    assert [j["title"] for j in by_region.get_json()["data"]] == ["Marketing Manager"]

    detail = client.get(f"/api/v1/jobs/{us_job.get_json()['data']['slug']}")
    assert detail.status_code == 200
    assert detail.get_json()["data"]["currency"] == "USD"


def test_opportunity_create_with_countries_and_topics(client, admin_token):
    client.post("/api/v1/topics", json={"name": "Leadership"}, headers=auth_headers(admin_token))

    created = client.post(
        "/api/v1/opportunities",
        json={
            "title": "Rising Leaders Fellowship",
            "organizationName": "Foster Capital",
            "type": "Fellowship",
            "countriesEligible": ["US", "GB", "CA"],
            "topicSlugs": ["leadership"],
            "fundingValue": "$10,000 grant",
        },
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201
    body = created.get_json()["data"]
    assert {c["code"] for c in body["countries_eligible"]} == {"US", "GB", "CA"}

    filtered = client.get("/api/v1/opportunities?country=GB")
    assert filtered.status_code == 200
    assert len(filtered.get_json()["data"]) == 1

    bad_country = client.post(
        "/api/v1/opportunities",
        json={"title": "Bad", "countriesEligible": ["ZZ"]},
        headers=auth_headers(admin_token),
    )
    assert bad_country.status_code == 404


def test_event_create_with_speakers_and_sponsors(client, admin_token):
    speaker = client.post(
        "/api/v1/people",
        json={"name": "Naliaka Wafula", "countryCode": "KE"},
        headers=auth_headers(admin_token),
    )
    assert speaker.status_code == 201
    speaker_slug = speaker.get_json()["data"]["slug"]

    event = client.post(
        "/api/v1/events",
        json={
            "title": "Women in Leadership Summit",
            "date": "2026-12-14",
            "countryCode": "KE",
            "speakerSlugs": [speaker_slug],
            "agenda": [{"time": "08:30", "title": "Registration"}],
        },
        headers=auth_headers(admin_token),
    )
    assert event.status_code == 201
    body = event.get_json()["data"]
    assert body["speakers"][0]["name"] == "Naliaka Wafula"
    assert body["agenda"][0]["title"] == "Registration"

    listed = client.get("/api/v1/events?country=KE")
    assert listed.status_code == 200
    assert len(listed.get_json()["data"]) == 1


def test_resource_create_and_topic_filter(client, admin_token):
    client.post("/api/v1/topics", json={"name": "Career"}, headers=auth_headers(admin_token))

    created = client.post(
        "/api/v1/resources",
        json={
            "name": "The 5-Year Career Planning Guide",
            "type": "Guide",
            "topicSlug": "career",
            "price": 0,
            "currency": "USD",
        },
        headers=auth_headers(admin_token),
    )
    assert created.status_code == 201
    assert created.get_json()["data"]["is_premium"] is False

    filtered = client.get("/api/v1/resources?topic=career")
    assert filtered.status_code == 200
    assert len(filtered.get_json()["data"]) == 1


def test_jobs_opportunities_people_filter_by_organization(client, admin_token):
    org = client.post(
        "/api/v1/organizations",
        json={"name": "Foster Capital", "countryCode": "US"},
        headers=auth_headers(admin_token),
    )
    assert org.status_code == 201
    org_id = org.get_json()["data"]["id"]
    org_slug = org.get_json()["data"]["slug"]

    other_org = client.post(
        "/api/v1/organizations",
        json={"name": "Kaziwave", "countryCode": "KE"},
        headers=auth_headers(admin_token),
    )
    other_org_id = other_org.get_json()["data"]["id"]

    client.post(
        "/api/v1/jobs",
        json={"title": "Program Lead", "companyName": "Foster Capital", "organizationId": org_id, "countryCode": "US"},
        headers=auth_headers(admin_token),
    )
    client.post(
        "/api/v1/jobs",
        json={"title": "Marketing Manager", "companyName": "Kaziwave", "organizationId": other_org_id, "countryCode": "KE"},
        headers=auth_headers(admin_token),
    )
    jobs = client.get(f"/api/v1/jobs?organization={org_slug}")
    assert jobs.status_code == 200
    assert [j["title"] for j in jobs.get_json()["data"]] == ["Program Lead"]

    client.post(
        "/api/v1/opportunities",
        json={"title": "Rising Leaders Fellowship", "organizationId": org_id, "type": "Fellowship"},
        headers=auth_headers(admin_token),
    )
    opportunities = client.get(f"/api/v1/opportunities?organization={org_slug}")
    assert opportunities.status_code == 200
    assert [o["title"] for o in opportunities.get_json()["data"]] == ["Rising Leaders Fellowship"]

    client.post(
        "/api/v1/people",
        json={"name": "Amina Yusuf", "countryCode": "US", "organizationId": org_id},
        headers=auth_headers(admin_token),
    )
    people = client.get(f"/api/v1/people?organization={org_slug}")
    assert people.status_code == 200
    assert [p["name"] for p in people.get_json()["data"]] == ["Amina Yusuf"]


def test_featured_filter_on_jobs_opportunities_events_resources(client, admin_token):
    client.post(
        "/api/v1/jobs",
        json={"title": "Featured Role", "companyName": "Acme", "countryCode": "US", "featured": True},
        headers=auth_headers(admin_token),
    )
    client.post(
        "/api/v1/jobs",
        json={"title": "Regular Role", "companyName": "Acme", "countryCode": "US", "featured": False},
        headers=auth_headers(admin_token),
    )
    jobs = client.get("/api/v1/jobs?featured=true")
    assert jobs.status_code == 200
    assert [j["title"] for j in jobs.get_json()["data"]] == ["Featured Role"]

    client.post(
        "/api/v1/opportunities",
        json={"title": "Featured Fellowship", "type": "Fellowship", "featured": True},
        headers=auth_headers(admin_token),
    )
    client.post(
        "/api/v1/opportunities",
        json={"title": "Regular Grant", "type": "Grant", "featured": False},
        headers=auth_headers(admin_token),
    )
    opportunities = client.get("/api/v1/opportunities?featured=true")
    assert opportunities.status_code == 200
    assert [o["title"] for o in opportunities.get_json()["data"]] == ["Featured Fellowship"]

    client.post(
        "/api/v1/events",
        json={"title": "Featured Summit", "date": "2026-11-01", "countryCode": "US", "featured": True},
        headers=auth_headers(admin_token),
    )
    client.post(
        "/api/v1/events",
        json={"title": "Regular Meetup", "date": "2026-11-02", "countryCode": "US", "featured": False},
        headers=auth_headers(admin_token),
    )
    events = client.get("/api/v1/events?featured=true")
    assert events.status_code == 200
    assert [e["title"] for e in events.get_json()["data"]] == ["Featured Summit"]

    client.post(
        "/api/v1/resources",
        json={"name": "Featured Guide", "type": "Guide", "price": 0, "currency": "USD", "featured": True},
        headers=auth_headers(admin_token),
    )
    client.post(
        "/api/v1/resources",
        json={"name": "Regular Guide", "type": "Guide", "price": 0, "currency": "USD", "featured": False},
        headers=auth_headers(admin_token),
    )
    resources = client.get("/api/v1/resources?featured=true")
    assert resources.status_code == 200
    assert [r["name"] for r in resources.get_json()["data"]] == ["Featured Guide"]


def test_opportunity_and_event_creation_requires_permission(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "plainmember@example.com", "password": "supersecret1", "first_name": "P", "last_name": "M"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "plainmember@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/opportunities", json={"title": "Should fail"}, headers=auth_headers(token)
    )
    assert resp.status_code == 403
