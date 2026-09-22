import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "orgs-editor@example.com",
    "password": "supersecret1",
    "first_name": "Nia",
    "last_name": "Kimani",
    "country_code": "US",
}


@pytest.fixture()
def editor_token(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=EDITOR_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=EDITOR_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="editor").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": EDITOR_PAYLOAD["email"], "password": EDITOR_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def logo_media_id(app):
    from app.extensions import db
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename="logo.png",
            stored_filename="logo.png",
            file_path="/tmp/logo.png",
            public_url="/media/originals/logo.png",
            mime_type="image/png",
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _base_payload(**overrides):
    payload = {
        "name": "Baraza Ventures",
        "type": "company",
        "shortDescription": "An early-stage venture fund backing East African founders.",
        "description": [{"type": "paragraph", "text": "Baraza Ventures invests in pre-seed and seed-stage startups."}],
        "countryCode": "KE",
        "website": "https://example.com/baraza",
        "social": {"linkedin": "barazaventures"},
    }
    payload.update(overrides)
    return payload


def test_organization_create_requires_permission(client):
    resp = client.post("/api/v1/organizations", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_organization_create_update_and_slug_uniqueness(client, editor_token):
    create = client.post("/api/v1/organizations", json=_base_payload(), headers=auth_headers(editor_token))
    assert create.status_code == 201
    org = create.get_json()["data"]
    assert org["slug"] == "baraza-ventures"
    assert org["status"] == "draft"
    assert org["org_type"] == "company"
    assert org["description"] == [
        {"type": "paragraph", "text": "Baraza Ventures invests in pre-seed and seed-stage startups."}
    ]

    dupe = client.post(
        "/api/v1/organizations", json=_base_payload(name="Baraza Ventures"), headers=auth_headers(editor_token)
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != org["slug"]

    update = client.put(
        f"/api/v1/organizations/{org['slug']}",
        json=_base_payload(type="foundation"),
        headers=auth_headers(editor_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["org_type"] == "foundation"


def test_organization_invalid_type_rejected(client, editor_token):
    bad = client.post(
        "/api/v1/organizations", json=_base_payload(type="not-a-real-type"), headers=auth_headers(editor_token)
    )
    assert bad.status_code == 422


def test_organization_geography_and_media_persist(client, editor_token, logo_media_id):
    create = client.post(
        "/api/v1/organizations",
        json=_base_payload(countryCode="FR", logoMediaId=logo_media_id, location="Paris, France"),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    org = create.get_json()["data"]
    assert org["country"]["code"] == "FR"
    assert org["country"]["region"] == "Europe"
    assert org["location"] == "Paris, France"
    assert org["logo"]["id"] == logo_media_id


def test_organization_website_validation(client, editor_token):
    bad = client.post(
        "/api/v1/organizations", json=_base_payload(website="not-a-url"), headers=auth_headers(editor_token)
    )
    assert bad.status_code == 422


def test_organization_publish_requires_description_and_hides_drafts_publicly(client, editor_token):
    create = client.post(
        "/api/v1/organizations",
        json=_base_payload(name="Incomplete Org", shortDescription=None, description=[]),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    hidden = client.get(f"/api/v1/organizations/{slug}")
    assert hidden.status_code == 404

    preview = client.get(f"/api/v1/organizations/{slug}", headers=auth_headers(editor_token))
    assert preview.status_code == 200

    publish_attempt = client.put(
        f"/api/v1/organizations/{slug}",
        json=_base_payload(name="Incomplete Org", shortDescription=None, description=[], status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish_attempt.status_code == 422

    publish_ok = client.put(
        f"/api/v1/organizations/{slug}",
        json=_base_payload(name="Incomplete Org", status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish_ok.status_code == 200
    assert publish_ok.get_json()["data"]["status"] == "published"

    now_public = client.get(f"/api/v1/organizations/{slug}")
    assert now_public.status_code == 200


def test_organization_list_hides_drafts_from_anonymous_requests(client, editor_token):
    client.post("/api/v1/organizations", json=_base_payload(name="Draft Org"), headers=auth_headers(editor_token))
    client.post(
        "/api/v1/organizations",
        json=_base_payload(name="Published Org", status="published"),
        headers=auth_headers(editor_token),
    )

    anon_listing = client.get("/api/v1/organizations")
    names = [o["name"] for o in anon_listing.get_json()["data"]]
    assert "Published Org" in names
    assert "Draft Org" not in names

    editor_listing = client.get("/api/v1/organizations", headers=auth_headers(editor_token))
    editor_names = [o["name"] for o in editor_listing.get_json()["data"]]
    assert "Draft Org" in editor_names


def test_organization_people_count(client, editor_token):
    org_resp = client.post(
        "/api/v1/organizations", json=_base_payload(status="published"), headers=auth_headers(editor_token)
    )
    org_id = org_resp.get_json()["data"]["id"]
    org_slug = org_resp.get_json()["data"]["slug"]

    assert org_resp.get_json()["data"]["people_count"] == 0

    client.post(
        "/api/v1/people",
        json={
            "name": "Amina Diallo",
            "organizationId": org_id,
            "shortBio": "Founder.",
            "countryCode": "KE",
            "status": "published",
        },
        headers=auth_headers(editor_token),
    )

    refreshed = client.get(f"/api/v1/organizations/{org_slug}", headers=auth_headers(editor_token))
    assert refreshed.get_json()["data"]["people_count"] == 1


def test_organization_delete_blocked_when_referenced_by_person(client, editor_token):
    org_resp = client.post(
        "/api/v1/organizations", json=_base_payload(status="published"), headers=auth_headers(editor_token)
    )
    org_id = org_resp.get_json()["data"]["id"]
    org_slug = org_resp.get_json()["data"]["slug"]

    client.post(
        "/api/v1/people",
        json={"name": "Founder Person", "organizationId": org_id, "countryCode": "KE"},
        headers=auth_headers(editor_token),
    )

    blocked = client.delete(f"/api/v1/organizations/{org_slug}", headers=auth_headers(editor_token))
    assert blocked.status_code == 409

    archived = client.put(
        f"/api/v1/organizations/{org_slug}",
        json=_base_payload(status="archived"),
        headers=auth_headers(editor_token),
    )
    assert archived.status_code == 200
    assert archived.get_json()["data"]["status"] == "archived"


def test_organization_delete_blocked_when_referenced_by_article(client, editor_token):
    org_resp = client.post(
        "/api/v1/organizations",
        json=_base_payload(name="Article-Linked Org", status="published"),
        headers=auth_headers(editor_token),
    )
    org_slug = org_resp.get_json()["data"]["slug"]

    author_resp = client.post(
        "/api/v1/authors", json={"name": "Byline Author", "countryCode": "US"}, headers=auth_headers(editor_token)
    )
    author_slug = author_resp.get_json()["data"]["slug"]

    client.post(
        "/api/v1/articles",
        json={
            "title": "Article About Baraza",
            "authorSlug": author_slug,
            "relatedOrganizationSlugs": [org_slug],
            "content": [{"type": "paragraph", "text": "Body."}],
        },
        headers=auth_headers(editor_token),
    )

    blocked = client.delete(f"/api/v1/organizations/{org_slug}", headers=auth_headers(editor_token))
    assert blocked.status_code == 409


def test_organization_delete_allowed_when_unreferenced(client, editor_token):
    org_resp = client.post(
        "/api/v1/organizations", json=_base_payload(name="Unreferenced Org"), headers=auth_headers(editor_token)
    )
    slug = org_resp.get_json()["data"]["slug"]

    deleted = client.delete(f"/api/v1/organizations/{slug}", headers=auth_headers(editor_token))
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/organizations/{slug}", headers=auth_headers(editor_token))
    assert gone.status_code == 404


def test_organization_search_and_type_filter(client, editor_token):
    client.post(
        "/api/v1/organizations",
        json=_base_payload(name="Searchable Foundation Co", type="foundation", status="published"),
        headers=auth_headers(editor_token),
    )
    client.post(
        "/api/v1/organizations",
        json=_base_payload(name="Other Company Inc", type="company", status="published"),
        headers=auth_headers(editor_token),
    )

    search = client.get("/api/v1/organizations?query=Searchable")
    names = [o["name"] for o in search.get_json()["data"]]
    assert names == ["Searchable Foundation Co"]

    type_filter = client.get("/api/v1/organizations?org_type=foundation")
    filtered_names = [o["name"] for o in type_filter.get_json()["data"]]
    assert "Searchable Foundation Co" in filtered_names
    assert "Other Company Inc" not in filtered_names


def test_unpublished_organization_not_exposed_through_linked_person(client, editor_token):
    org_resp = client.post(
        "/api/v1/organizations", json=_base_payload(name="Stealth Startup"), headers=auth_headers(editor_token)
    )
    assert org_resp.get_json()["data"]["status"] == "draft"
    org_id = org_resp.get_json()["data"]["id"]

    person_resp = client.post(
        "/api/v1/people",
        json={
            "name": "Founder At Stealth",
            "organizationId": org_id,
            "shortBio": "Founder.",
            "countryCode": "KE",
            "status": "published",
        },
        headers=auth_headers(editor_token),
    )
    person_slug = person_resp.get_json()["data"]["slug"]

    public_person = client.get(f"/api/v1/people/{person_slug}")
    assert public_person.status_code == 200
    person_data = public_person.get_json()["data"]
    # The raw FK is harmless and lets the CMS editor resolve the link, but
    # the nested organization preview must not leak the draft org's name.
    assert person_data["organization_id"] == org_id
    assert person_data["organization"] is None

    # Publish the organization — now the nested preview appears.
    client.put(
        f"/api/v1/organizations/{org_resp.get_json()['data']['slug']}",
        json=_base_payload(name="Stealth Startup", status="published"),
        headers=auth_headers(editor_token),
    )
    public_person_after = client.get(f"/api/v1/people/{person_slug}")
    assert public_person_after.get_json()["data"]["organization"]["name"] == "Stealth Startup"
