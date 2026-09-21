import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "commadmin@example.com",
    "password": "supersecret1",
    "first_name": "Comm",
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


def test_newsletter_subscribe_unsubscribe_and_resubscribe(client):
    subscribe = client.post(
        "/api/v1/newsletter/subscribe",
        json={
            "email": "reader@example.com",
            "firstName": "Reader",
            "countryCode": "US",
            "placement": "footer",
            "acquisition": {"source": "linkedin", "isFromLinkedIn": True},
        },
    )
    assert subscribe.status_code == 201
    assert subscribe.get_json()["data"]["status"] == "active"

    # Subscribing again with the same email updates rather than duplicates.
    again = client.post(
        "/api/v1/newsletter/subscribe", json={"email": "reader@example.com", "firstName": "Reader Updated"}
    )
    assert again.status_code == 201
    assert again.get_json()["data"]["first_name"] == "Reader Updated"

    unsub = client.post("/api/v1/newsletter/unsubscribe", json={"email": "reader@example.com"})
    assert unsub.status_code == 200

    resub = client.post("/api/v1/newsletter/subscribe", json={"email": "reader@example.com"})
    assert resub.status_code == 201
    assert resub.get_json()["data"]["status"] == "active"


def test_newsletter_subscribe_ignores_unknown_frontend_fields(client):
    # Reproduces the exact payload NewsletterForm.jsx sends (email, placement,
    # consentTimestamp, acquisition) — consentTimestamp isn't a declared
    # field on SubscribeInputSchema and previously caused a 422.
    subscribe = client.post(
        "/api/v1/newsletter/subscribe",
        json={
            "email": "consent@example.com",
            "placement": "footer",
            "consentTimestamp": "2026-09-21T00:00:00.000Z",
            "acquisition": {"source": "direct"},
        },
    )
    assert subscribe.status_code == 201
    assert subscribe.get_json()["data"]["status"] == "active"


def test_newsletter_subscribers_list_requires_permission(client, admin_token):
    client.post("/api/v1/newsletter/subscribe", json={"email": "a@example.com"})

    denied = client.post(
        "/api/v1/auth/register",
        json={"email": "notallowed@example.com", "password": "supersecret1", "first_name": "N", "last_name": "A"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "notallowed@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]
    resp = client.get("/api/v1/newsletter/subscribers", headers=auth_headers(token))
    assert resp.status_code == 403

    allowed = client.get("/api/v1/newsletter/subscribers", headers=auth_headers(admin_token))
    assert allowed.status_code == 200
    assert allowed.get_json()["meta"]["total"] == 1


def test_story_submission_lifecycle(client, admin_token):
    created = client.post(
        "/api/v1/submissions",
        json={
            "name": "Beatrice Achieng",
            "email": "beatrice@example.com",
            "countryCode": "KE",
            "title": "How I Rebuilt My Career",
            "excerpt": "After ten years raising three children...",
        },
    )
    assert created.status_code == 201
    submission_id = created.get_json()["data"]["id"]
    assert created.get_json()["data"]["status"] == "new"

    listed = client.get("/api/v1/submissions", headers=auth_headers(admin_token))
    assert listed.status_code == 200
    assert listed.get_json()["meta"]["total"] == 1

    updated = client.patch(
        f"/api/v1/submissions/{submission_id}/status",
        json={"status": "accepted"},
        headers=auth_headers(admin_token),
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["status"] == "accepted"


def test_nomination_lifecycle(client, admin_token):
    created = client.post(
        "/api/v1/nominations",
        json={
            "nomineeName": "Judith Kilonzo",
            "countryCode": "KE",
            "profession": "Chief Financial Officer",
            "nominatorName": "Naliaka Wafula",
            "nominatorEmail": "naliaka@example.com",
            "category": "Women to Watch",
        },
    )
    assert created.status_code == 201
    nomination_id = created.get_json()["data"]["id"]

    updated = client.patch(
        f"/api/v1/nominations/{nomination_id}/status",
        json={"status": "reviewing"},
        headers=auth_headers(admin_token),
    )
    assert updated.status_code == 200
    assert updated.get_json()["data"]["status"] == "reviewing"


def test_partnership_inquiry_sponsor_and_audience_stats(client, admin_token):
    inquiry = client.post(
        "/api/v1/partnerships/inquiries",
        json={
            "company": "Equity Bank",
            "contactName": "James Muriuki",
            "email": "james@example.com",
            "interest": "Newsletter sponsorship",
        },
    )
    assert inquiry.status_code == 201

    listed = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(admin_token))
    assert listed.status_code == 200
    assert listed.get_json()["meta"]["total"] == 1

    # There's no public Organizations-create endpoint yet (out of scope for
    # this phase), so seed one directly to exercise the Sponsor endpoint.
    with client.application.app_context():
        from app.extensions import db
        from app.models.people import Organization

        db.session.add(Organization(slug="kaziwave", name="Kaziwave"))
        db.session.commit()

    sponsor = client.post(
        "/api/v1/partnerships/sponsors",
        json={"organizationSlug": "kaziwave", "tier": "Gold"},
        headers=auth_headers(admin_token),
    )
    assert sponsor.status_code == 201
    assert sponsor.get_json()["data"]["organization"]["name"] == "Kaziwave"

    sponsors = client.get("/api/v1/partnerships/sponsors")
    assert sponsors.status_code == 200
    assert len(sponsors.get_json()["data"]) == 1

    empty_stats = client.get("/api/v1/partnerships/audience")
    assert empty_stats.status_code == 200
    assert empty_stats.get_json()["data"] == {}

    saved = client.put(
        "/api/v1/admin/settings",
        json={"settings": {"audience_stats": {"linkedinFollowers": 132000, "newsletterSubscribers": 34210}}},
        headers=auth_headers(admin_token),
    )
    assert saved.status_code == 200

    stats = client.get("/api/v1/partnerships/audience")
    assert stats.status_code == 200
    assert stats.get_json()["data"]["linkedinFollowers"] == 132000
