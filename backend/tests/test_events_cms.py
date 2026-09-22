import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "events-manager@example.com",
    "password": "supersecret1",
    "first_name": "Amara",
    "last_name": "Nwosu",
    "country_code": "NG",
}

NO_PERMISSION_PAYLOAD = {
    "email": "events-nobody@example.com",
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
    return _register_with_role(client, app, MANAGER_PAYLOAD, "events_manager")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def organizer_id(client, app):
    org_admin_token = _register_with_role(
        client,
        app,
        {
            "email": "events-org-admin@example.com",
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
        "title": "Women in Leadership Summit",
        "organizerName": "Women Shaping Futures",
        "type": "Conference",
        "format": "in-person",
        "shortDescription": "Our flagship annual leadership summit.",
        "description": [{"type": "paragraph", "text": "Our flagship annual leadership summit."}],
        "date": "2027-03-10",
        "timezone": "Africa/Nairobi",
        "location": "Nairobi, Kenya",
        "countryCode": "KE",
        "venue": "KICC",
        "registrationUrl": "https://example.com/register/leadership-summit",
        "status": "draft",
    }
    payload.update(overrides)
    return payload


def test_event_create_requires_permission(client):
    resp = client.post("/api/v1/events", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_event_create_requires_permission_even_with_account(client, no_permission_token):
    resp = client.post("/api/v1/events", json=_base_payload(), headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_event_create_update_and_slug_uniqueness(client, manager_token, organizer_id):
    create = client.post(
        "/api/v1/events", json=_base_payload(organizerId=organizer_id), headers=auth_headers(manager_token)
    )
    assert create.status_code == 201
    event = create.get_json()["data"]
    assert event["slug"] == "women-in-leadership-summit"
    assert event["organizer"]["slug"] == "baraza-ventures"
    assert event["organizer_id"] == organizer_id
    assert event["description"] == [{"type": "paragraph", "text": "Our flagship annual leadership summit."}]

    dupe = client.post(
        "/api/v1/events", json=_base_payload(organizerId=organizer_id), headers=auth_headers(manager_token)
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != event["slug"]

    update = client.put(
        f"/api/v1/events/{event['slug']}",
        json=_base_payload(organizerId=organizer_id, title="Women in Leadership Summit 2027"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["title"] == "Women in Leadership Summit 2027"


def test_event_invalid_type_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(type="Not A Real Type"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_event_end_date_before_start_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(endDate="2027-03-01"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_event_registration_url_validation(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(registrationUrl="not-a-url"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_event_publish_requires_description_and_registration_url(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(status="published", description=[], registrationUrl=None),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "publish_validation_failed"


def test_event_publish_without_registration_url_ok_when_not_required(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(status="published", registrationRequired=False, registrationUrl=None),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201


def test_event_virtual_and_hybrid_formats(client, manager_token):
    virtual = client.post(
        "/api/v1/events",
        json=_base_payload(title="Virtual Webinar", format="virtual", virtualLink="https://zoom.example.com/join", virtualLinkPublic=False),
        headers=auth_headers(manager_token),
    )
    assert virtual.status_code == 201
    assert virtual.get_json()["data"]["virtual_link_public"] is False

    hybrid = client.post(
        "/api/v1/events",
        json=_base_payload(title="Hybrid Panel", format="hybrid", virtualLink="https://zoom.example.com/join", virtualLinkPublic=True, venue="KICC"),
        headers=auth_headers(manager_token),
    )
    assert hybrid.status_code == 201
    body = hybrid.get_json()["data"]
    assert body["format"] == "hybrid"
    assert body["virtual_link_public"] is True
    assert body["virtual_link"] == "https://zoom.example.com/join"


def test_event_timezone_persists(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(timezone="America/New_York"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["timezone"] == "America/New_York"


def test_event_price_and_currency(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(ticketPrice=8500, currency="KES"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    body = resp.get_json()["data"]
    assert body["ticket_price"] == 8500
    assert body["currency"] == "KES"

    free = client.post(
        "/api/v1/events", json=_base_payload(title="Free Meetup"), headers=auth_headers(manager_token)
    )
    assert free.status_code == 201
    assert free.get_json()["data"]["ticket_price"] is None


def test_event_speakers(client, app, manager_token):
    admin_token = _register_with_role(
        client,
        app,
        {
            "email": "events-people-admin@example.com",
            "password": "supersecret1",
            "first_name": "People",
            "last_name": "Admin",
            "country_code": "US",
        },
        "admin",
    )
    speaker = client.post(
        "/api/v1/people", json={"name": "Naliaka Wafula", "countryCode": "KE"}, headers=auth_headers(admin_token)
    )
    assert speaker.status_code == 201
    speaker_slug = speaker.get_json()["data"]["slug"]

    resp = client.post(
        "/api/v1/events",
        json=_base_payload(speakers=[{"personSlug": speaker_slug}]),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["speakers"][0]["person"]["slug"] == speaker_slug


def test_event_status_and_public_visibility(client, manager_token):
    draft = client.post(
        "/api/v1/events", json=_base_payload(status="draft"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/events/{draft['slug']}")
    assert anon_detail.status_code == 404

    manager_detail = client.get(f"/api/v1/events/{draft['slug']}", headers=auth_headers(manager_token))
    assert manager_detail.status_code == 200

    anon_list = client.get("/api/v1/events")
    assert draft["slug"] not in [e["slug"] for e in anon_list.get_json()["data"]]

    publish = client.put(
        f"/api/v1/events/{draft['slug']}", json=_base_payload(status="published"), headers=auth_headers(manager_token)
    )
    assert publish.status_code == 200

    anon_detail_after_publish = client.get(f"/api/v1/events/{draft['slug']}")
    assert anon_detail_after_publish.status_code == 200
    anon_list_after_publish = client.get("/api/v1/events")
    assert draft["slug"] in [e["slug"] for e in anon_list_after_publish.get_json()["data"]]


def test_event_cancelled_stays_publicly_visible_and_marked(client, manager_token):
    cancelled = client.post(
        "/api/v1/events",
        json=_base_payload(title="Cancelled Panel", status="cancelled"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert cancelled["is_cancelled"] is True

    anon_detail = client.get(f"/api/v1/events/{cancelled['slug']}")
    assert anon_detail.status_code == 200
    assert anon_detail.get_json()["data"]["is_cancelled"] is True


def test_event_archived_hidden_from_public(client, manager_token):
    archived = client.post(
        "/api/v1/events",
        json=_base_payload(title="Archived Workshop", status="archived"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/events/{archived['slug']}")
    assert anon_detail.status_code == 404


def test_event_upcoming_and_past_are_computed_from_date(client, manager_token):
    upcoming = client.post(
        "/api/v1/events",
        json=_base_payload(title="Future Event", status="published", date="2027-06-01"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert upcoming["is_upcoming"] is True
    assert upcoming["is_past"] is False

    past = client.post(
        "/api/v1/events",
        json=_base_payload(title="Past Event", status="published", date="2020-01-01"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert past["is_past"] is True
    assert past["is_upcoming"] is False

    upcoming_list = client.get("/api/v1/events?when=upcoming")
    upcoming_slugs = [e["slug"] for e in upcoming_list.get_json()["data"]]
    assert upcoming["slug"] in upcoming_slugs
    assert past["slug"] not in upcoming_slugs

    past_list = client.get("/api/v1/events?when=past")
    past_slugs = [e["slug"] for e in past_list.get_json()["data"]]
    assert past["slug"] in past_slugs
    assert upcoming["slug"] not in past_slugs


def test_event_featured_and_sponsored_flags(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(title="Sponsored Summit", status="published", featured=True, sponsored=True),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["featured"] is True
    assert data["sponsored"] is True


def test_event_delete_requires_permission(client, manager_token, no_permission_token):
    created = client.post(
        "/api/v1/events", json=_base_payload(), headers=auth_headers(manager_token)
    ).get_json()["data"]

    denied = client.delete(f"/api/v1/events/{created['slug']}", headers=auth_headers(no_permission_token))
    assert denied.status_code == 403

    allowed = client.delete(f"/api/v1/events/{created['slug']}", headers=auth_headers(manager_token))
    assert allowed.status_code == 200


def test_event_city_filter(client, manager_token):
    client.post(
        "/api/v1/events",
        json=_base_payload(title="Nairobi Meetup", city="Nairobi", status="published"),
        headers=auth_headers(manager_token),
    )
    client.post(
        "/api/v1/events",
        json=_base_payload(title="Toronto Meetup", city="Toronto", status="published"),
        headers=auth_headers(manager_token),
    )

    resp = client.get("/api/v1/events?city=Nairobi")
    titles = [e["title"] for e in resp.get_json()["data"]]
    assert "Nairobi Meetup" in titles
    assert "Toronto Meetup" not in titles


def test_event_date_range_filter(client, manager_token):
    near = client.post(
        "/api/v1/events",
        json=_base_payload(title="Near Event", date="2027-01-10", status="published"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    far = client.post(
        "/api/v1/events",
        json=_base_payload(title="Far Event", date="2027-06-10", status="published"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]

    resp = client.get("/api/v1/events?dateFrom=2027-01-01&dateTo=2027-02-01")
    slugs = [e["slug"] for e in resp.get_json()["data"]]
    assert near["slug"] in slugs
    assert far["slug"] not in slugs


def test_event_free_paid_filter(client, manager_token):
    free = client.post(
        "/api/v1/events",
        json=_base_payload(title="Free Meetup 2", ticketPrice=None, currency=None, status="published"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    paid = client.post(
        "/api/v1/events",
        json=_base_payload(title="Paid Summit 2", ticketPrice=5000, currency="KES", status="published"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert free["is_free"] is True
    assert paid["is_free"] is False

    free_only = client.get("/api/v1/events?price=free")
    free_slugs = [e["slug"] for e in free_only.get_json()["data"]]
    assert free["slug"] in free_slugs
    assert paid["slug"] not in free_slugs

    paid_only = client.get("/api/v1/events?price=paid")
    paid_slugs = [e["slug"] for e in paid_only.get_json()["data"]]
    assert paid["slug"] in paid_slugs
    assert free["slug"] not in paid_slugs


def test_event_paid_requires_currency(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(ticketPrice=100, currency=None), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_event_negative_price_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(ticketPrice=-5, currency="USD"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_event_keyword_search(client, manager_token):
    client.post(
        "/api/v1/events",
        json=_base_payload(title="Founder Growth Retreat", status="published"),
        headers=auth_headers(manager_token),
    )
    client.post(
        "/api/v1/events",
        json=_base_payload(title="Career Advancement Masterclass", status="published"),
        headers=auth_headers(manager_token),
    )

    resp = client.get("/api/v1/events?query=Founder")
    titles = [e["title"] for e in resp.get_json()["data"]]
    assert "Founder Growth Retreat" in titles
    assert "Career Advancement Masterclass" not in titles


def test_event_leadership_type(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(type="Leadership Event"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["type"] == "Leadership Event"


def test_event_speaker_fallback_fields(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(
            speakers=[
                {
                    "name": "Fatima Al-Sayed",
                    "title": "VP of Engineering",
                    "organizationName": "Skyline Cloud",
                    "bio": "Leads a large distributed engineering organization.",
                }
            ]
        ),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    speaker = resp.get_json()["data"]["speakers"][0]
    assert speaker["name"] == "Fatima Al-Sayed"
    assert speaker["title"] == "VP of Engineering"
    assert speaker["person"] is None


def test_event_speaker_requires_name_or_person(client, manager_token):
    resp = client.post(
        "/api/v1/events", json=_base_payload(speakers=[{"title": "No name or person"}]), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_event_sponsor_tier_and_fallback(client, manager_token):
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(
            sponsors=[
                {"name": "Skyline Cloud", "url": "https://skylinecloud.example.com", "tier": "Supporting Partner"}
            ]
        ),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    sponsor = resp.get_json()["data"]["sponsors"][0]
    assert sponsor["name"] == "Skyline Cloud"
    assert sponsor["tier"] == "Supporting Partner"
    assert sponsor["organization"] is None


def test_event_sponsor_organization_link(client, app, manager_token):
    admin_token = _register_with_role(
        client,
        app,
        {
            "email": "events-org-admin-2@example.com",
            "password": "supersecret1",
            "first_name": "Org",
            "last_name": "Admin",
            "country_code": "US",
        },
        "admin",
    )
    org = client.post(
        "/api/v1/organizations",
        json={
            "name": "Baraza Ventures 2",
            "countryCode": "KE",
            "shortDescription": "An early-stage venture fund backing East African founders.",
            "status": "published",
        },
        headers=auth_headers(admin_token),
    ).get_json()["data"]

    resp = client.post(
        "/api/v1/events",
        json=_base_payload(sponsors=[{"organizationId": org["id"], "tier": "Gold Sponsor"}]),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    sponsor = resp.get_json()["data"]["sponsors"][0]
    assert sponsor["organization"]["id"] == org["id"]
    assert sponsor["tier"] == "Gold Sponsor"


def test_event_agenda_structured_items_persist(client, manager_token):
    agenda = [
        {"startTime": "09:00", "endTime": "09:30", "title": "Registration", "sessionType": "Networking"},
        {
            "startTime": "09:30",
            "endTime": "10:30",
            "title": "Opening Keynote",
            "description": "A look at what's next.",
            "sessionType": "Keynote",
            "speakerNames": ["Jane Doe"],
        },
    ]
    resp = client.post(
        "/api/v1/events", json=_base_payload(agenda=agenda), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    persisted = resp.get_json()["data"]["agenda"]
    assert persisted[0]["title"] == "Registration"
    assert persisted[0]["startTime"] == "09:00"
    assert persisted[1]["description"] == "A look at what's next."
    assert persisted[1]["speakerNames"] == ["Jane Doe"]


def test_event_postponed_status_publicly_visible(client, manager_token):
    postponed = client.post(
        "/api/v1/events", json=_base_payload(title="Postponed Summit", status="postponed"), headers=auth_headers(manager_token)
    ).get_json()["data"]
    assert postponed["is_postponed"] is True

    anon_detail = client.get(f"/api/v1/events/{postponed['slug']}")
    assert anon_detail.status_code == 200
    assert anon_detail.get_json()["data"]["is_postponed"] is True


def test_event_scheduled_status_publish_validation_and_visibility(client, manager_token):
    from datetime import date, timedelta

    future = (date.today() + timedelta(days=5)).isoformat()
    resp = client.post(
        "/api/v1/events",
        json=_base_payload(status="scheduled", publishedDate=future),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    scheduled = resp.get_json()["data"]

    # Not yet publicly visible — published_date is in the future.
    anon_detail = client.get(f"/api/v1/events/{scheduled['slug']}")
    assert anon_detail.status_code == 404

    manager_detail = client.get(f"/api/v1/events/{scheduled['slug']}", headers=auth_headers(manager_token))
    assert manager_detail.status_code == 200


def test_event_review_status_requires_permission_to_view(client, manager_token):
    review = client.post(
        "/api/v1/events", json=_base_payload(title="Review Event", status="review"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/events/{review['slug']}")
    assert anon_detail.status_code == 404

    manager_detail = client.get(f"/api/v1/events/{review['slug']}", headers=auth_headers(manager_token))
    assert manager_detail.status_code == 200


def test_event_is_ongoing_and_is_completed_computed(client, manager_token):
    from datetime import date, timedelta

    today_event = client.post(
        "/api/v1/events",
        json=_base_payload(title="Live Now", date=date.today().isoformat(), status="published"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert today_event["is_ongoing"] is True
    assert today_event["is_completed"] is False

    past_event = client.post(
        "/api/v1/events",
        json=_base_payload(title="Already Happened", date=(date.today() - timedelta(days=10)).isoformat(), status="published"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert past_event["is_completed"] is True
    assert past_event["is_ongoing"] is False
