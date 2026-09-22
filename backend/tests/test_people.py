import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "people-editor@example.com",
    "password": "supersecret1",
    "first_name": "Pat",
    "last_name": "Osei",
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
def photo_media_id(app):
    from app.extensions import db
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename="portrait.jpg",
            stored_filename="portrait.jpg",
            file_path="/tmp/portrait.jpg",
            public_url="/media/originals/portrait.jpg",
            mime_type="image/jpeg",
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _base_payload(**overrides):
    payload = {
        "name": "Amina Diallo",
        "pronouns": "she/her",
        "title": "Founder & CEO",
        "shortBio": "Founder of a fintech startup serving West Africa.",
        "bio": [{"type": "paragraph", "text": "Amina Diallo founded her company in 2021."}],
        "countryCode": "KE",
        "industry": "Financial Technology",
        "website": "https://example.com",
        "social": {"linkedin": "aminadiallo"},
    }
    payload.update(overrides)
    return payload


def test_person_create_requires_permission(client):
    resp = client.post("/api/v1/people", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_person_create_update_and_slug_uniqueness(client, editor_token):
    create = client.post("/api/v1/people", json=_base_payload(), headers=auth_headers(editor_token))
    assert create.status_code == 201
    person = create.get_json()["data"]
    assert person["slug"] == "amina-diallo"
    assert person["status"] == "draft"
    assert person["pronouns"] == "she/her"
    assert person["bio"] == [{"type": "paragraph", "text": "Amina Diallo founded her company in 2021."}]

    # A second person with the same name gets a de-duplicated slug.
    dupe = client.post(
        "/api/v1/people", json=_base_payload(name="Amina Diallo"), headers=auth_headers(editor_token)
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != person["slug"]

    update = client.put(
        f"/api/v1/people/{person['slug']}",
        json=_base_payload(title="Executive Chair"),
        headers=auth_headers(editor_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["title"] == "Executive Chair"


def test_person_geography_and_media_persist(client, editor_token, photo_media_id):
    create = client.post(
        "/api/v1/people",
        json=_base_payload(countryCode="FR", photoMediaId=photo_media_id),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    person = create.get_json()["data"]
    assert person["country"]["code"] == "FR"
    assert person["country"]["region"] == "Europe"
    assert person["photo"]["id"] == photo_media_id


def test_person_publish_requires_bio_and_hides_drafts_publicly(client, editor_token):
    create = client.post(
        "/api/v1/people",
        json=_base_payload(name="Incomplete Person", shortBio=None, bio=[]),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    # Draft is invisible to the public.
    hidden = client.get(f"/api/v1/people/{slug}")
    assert hidden.status_code == 404

    # But visible to an editor.
    preview = client.get(f"/api/v1/people/{slug}", headers=auth_headers(editor_token))
    assert preview.status_code == 200

    # Publishing without any bio content is rejected.
    publish_attempt = client.put(
        f"/api/v1/people/{slug}",
        json=_base_payload(name="Incomplete Person", shortBio=None, bio=[], status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish_attempt.status_code == 422

    # Adding a short bio makes it publishable.
    publish_ok = client.put(
        f"/api/v1/people/{slug}",
        json=_base_payload(name="Incomplete Person", status="published"),
        headers=auth_headers(editor_token),
    )
    assert publish_ok.status_code == 200
    assert publish_ok.get_json()["data"]["status"] == "published"

    now_public = client.get(f"/api/v1/people/{slug}")
    assert now_public.status_code == 200


def test_person_list_hides_drafts_from_anonymous_requests(client, editor_token):
    client.post("/api/v1/people", json=_base_payload(name="Draft Person"), headers=auth_headers(editor_token))
    published = _base_payload(name="Published Person", status="published")
    client.post("/api/v1/people", json=published, headers=auth_headers(editor_token))

    anon_listing = client.get("/api/v1/people")
    names = [p["name"] for p in anon_listing.get_json()["data"]]
    assert "Published Person" in names
    assert "Draft Person" not in names

    editor_listing = client.get("/api/v1/people", headers=auth_headers(editor_token))
    editor_names = [p["name"] for p in editor_listing.get_json()["data"]]
    assert "Draft Person" in editor_names


def test_person_series_relationship(client, editor_token):
    series_resp = client.post(
        "/api/v1/series", json={"name": "Women Doing Incredible Things"}, headers=auth_headers(editor_token)
    )
    assert series_resp.status_code == 201
    series_slug = series_resp.get_json()["data"]["slug"]

    create = client.post(
        "/api/v1/people",
        json=_base_payload(seriesSlugs=[series_slug]),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    assert create.get_json()["data"]["series"][0]["slug"] == series_slug


def test_person_related_articles_visible_both_ways(client, editor_token, author_slug=None):
    person_resp = client.post("/api/v1/people", json=_base_payload(status="published"), headers=auth_headers(editor_token))
    person_slug = person_resp.get_json()["data"]["slug"]

    author_resp = client.post(
        "/api/v1/authors", json={"name": "Byline Author", "countryCode": "US"}, headers=auth_headers(editor_token)
    )
    author_slug = author_resp.get_json()["data"]["slug"]

    article_resp = client.post(
        "/api/v1/articles",
        json={
            "title": "Profile: Amina Diallo",
            "authorSlug": author_slug,
            "relatedPersonSlugs": [person_slug],
            "content": [{"type": "paragraph", "text": "Body."}],
            "status": "published",
        },
        headers=auth_headers(editor_token),
    )
    assert article_resp.status_code == 201

    related = client.get(f"/api/v1/articles?person={person_slug}")
    assert related.status_code == 200
    slugs = [a["slug"] for a in related.get_json()["data"]]
    assert article_resp.get_json()["data"]["slug"] in slugs


def test_person_delete_blocked_when_referenced_by_article(client, editor_token):
    person_resp = client.post("/api/v1/people", json=_base_payload(status="published"), headers=auth_headers(editor_token))
    person_slug = person_resp.get_json()["data"]["slug"]

    author_resp = client.post(
        "/api/v1/authors", json={"name": "Second Author", "countryCode": "US"}, headers=auth_headers(editor_token)
    )
    author_slug = author_resp.get_json()["data"]["slug"]

    client.post(
        "/api/v1/articles",
        json={
            "title": "Another Profile Story",
            "authorSlug": author_slug,
            "relatedPersonSlugs": [person_slug],
            "content": [{"type": "paragraph", "text": "Body."}],
        },
        headers=auth_headers(editor_token),
    )

    blocked = client.delete(f"/api/v1/people/{person_slug}", headers=auth_headers(editor_token))
    assert blocked.status_code == 409

    # Archiving instead of deleting always works.
    archived = client.put(
        f"/api/v1/people/{person_slug}",
        json=_base_payload(status="archived"),
        headers=auth_headers(editor_token),
    )
    assert archived.status_code == 200
    assert archived.get_json()["data"]["status"] == "archived"


def test_person_delete_allowed_when_unreferenced(client, editor_token):
    person_resp = client.post(
        "/api/v1/people", json=_base_payload(name="Unreferenced Person"), headers=auth_headers(editor_token)
    )
    slug = person_resp.get_json()["data"]["slug"]

    deleted = client.delete(f"/api/v1/people/{slug}", headers=auth_headers(editor_token))
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/people/{slug}", headers=auth_headers(editor_token))
    assert gone.status_code == 404
