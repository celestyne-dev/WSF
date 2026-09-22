import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "authors-editor@example.com",
    "password": "supersecret1",
    "first_name": "Robin",
    "last_name": "Achieng",
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
            original_filename="author-portrait.jpg",
            stored_filename="author-portrait.jpg",
            file_path="/tmp/author-portrait.jpg",
            public_url="/media/originals/author-portrait.jpg",
            mime_type="image/jpeg",
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _base_payload(**overrides):
    payload = {
        "name": "Zainab Bello",
        "role": "Staff Writer",
        "shortBio": "Staff writer covering fintech and workforce policy.",
        "bio": [{"type": "paragraph", "text": "Zainab joined WSF in 2022 after a decade in financial journalism."}],
        "countryCode": "NG",
        "website": "https://example.com/zainab",
        "social": {"linkedin": "zainabbello"},
    }
    payload.update(overrides)
    return payload


def test_author_create_requires_permission(client):
    resp = client.post("/api/v1/authors", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_author_create_update_and_slug_uniqueness(client, editor_token):
    create = client.post("/api/v1/authors", json=_base_payload(), headers=auth_headers(editor_token))
    assert create.status_code == 201
    author = create.get_json()["data"]
    assert author["slug"] == "zainab-bello"
    assert author["status"] == "draft"
    assert author["bio"] == [
        {"type": "paragraph", "text": "Zainab joined WSF in 2022 after a decade in financial journalism."}
    ]

    dupe = client.post(
        "/api/v1/authors", json=_base_payload(name="Zainab Bello"), headers=auth_headers(editor_token)
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != author["slug"]

    update = client.put(
        f"/api/v1/authors/{author['slug']}",
        json=_base_payload(role="Contributing Editor"),
        headers=auth_headers(editor_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["role"] == "Contributing Editor"


def test_author_geography_and_media_persist(client, editor_token, photo_media_id):
    create = client.post(
        "/api/v1/authors",
        json=_base_payload(countryCode="FR", photoMediaId=photo_media_id),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    author = create.get_json()["data"]
    assert author["country"]["code"] == "FR"
    assert author["country"]["region"] == "Europe"
    assert author["photo"]["id"] == photo_media_id


def test_author_website_validation(client, editor_token):
    bad = client.post(
        "/api/v1/authors", json=_base_payload(website="not-a-url"), headers=auth_headers(editor_token)
    )
    assert bad.status_code == 422


def test_author_activate_requires_bio_and_hides_drafts_publicly(client, editor_token):
    create = client.post(
        "/api/v1/authors",
        json=_base_payload(name="Incomplete Author", shortBio=None, bio=[]),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    hidden = client.get(f"/api/v1/authors/{slug}")
    assert hidden.status_code == 404

    preview = client.get(f"/api/v1/authors/{slug}", headers=auth_headers(editor_token))
    assert preview.status_code == 200

    activate_attempt = client.put(
        f"/api/v1/authors/{slug}",
        json=_base_payload(name="Incomplete Author", shortBio=None, bio=[], status="active"),
        headers=auth_headers(editor_token),
    )
    assert activate_attempt.status_code == 422

    activate_ok = client.put(
        f"/api/v1/authors/{slug}",
        json=_base_payload(name="Incomplete Author", status="active"),
        headers=auth_headers(editor_token),
    )
    assert activate_ok.status_code == 200
    assert activate_ok.get_json()["data"]["status"] == "active"

    now_public = client.get(f"/api/v1/authors/{slug}")
    assert now_public.status_code == 200


def test_author_list_hides_drafts_from_anonymous_requests(client, editor_token):
    client.post("/api/v1/authors", json=_base_payload(name="Draft Author"), headers=auth_headers(editor_token))
    client.post(
        "/api/v1/authors", json=_base_payload(name="Active Author", status="active"), headers=auth_headers(editor_token)
    )

    anon_listing = client.get("/api/v1/authors")
    names = [a["name"] for a in anon_listing.get_json()["data"]]
    assert "Active Author" in names
    assert "Draft Author" not in names

    editor_listing = client.get("/api/v1/authors", headers=auth_headers(editor_token))
    editor_names = [a["name"] for a in editor_listing.get_json()["data"]]
    assert "Draft Author" in editor_names


def test_author_topics_relationship(client, editor_token):
    topic_resp = client.post(
        "/api/v1/topics", json={"name": "Fintech"}, headers=auth_headers(editor_token)
    )
    assert topic_resp.status_code == 201
    topic_slug = topic_resp.get_json()["data"]["slug"]

    create = client.post(
        "/api/v1/authors",
        json=_base_payload(topicSlugs=[topic_slug]),
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    assert create.get_json()["data"]["topics"][0]["slug"] == topic_slug


def test_author_person_link_visibility(client, editor_token):
    person_resp = client.post(
        "/api/v1/people",
        json={"name": "Zainab Bello", "shortBio": "Profiled founder.", "countryCode": "NG"},
        headers=auth_headers(editor_token),
    )
    person_id = person_resp.get_json()["data"]["id"]

    create = client.post(
        "/api/v1/authors",
        json=_base_payload(personId=person_id, status="active"),
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    # Person is still a draft — must not leak through the public Author response.
    public_view = client.get(f"/api/v1/authors/{slug}")
    assert public_view.get_json()["data"]["author"]["person"] is None
    assert public_view.get_json()["data"]["author"]["person_id"] == person_id

    # Publish the Person — now the Author's public response includes it.
    client.put(
        f"/api/v1/people/{person_resp.get_json()['data']['slug']}",
        json={"name": "Zainab Bello", "shortBio": "Profiled founder.", "countryCode": "NG", "status": "published"},
        headers=auth_headers(editor_token),
    )
    public_view_after = client.get(f"/api/v1/authors/{slug}")
    assert public_view_after.get_json()["data"]["author"]["person"]["slug"] == person_resp.get_json()["data"]["slug"]


def test_author_public_schema_excludes_user_id(client, editor_token):
    create = client.post(
        "/api/v1/authors", json=_base_payload(status="active"), headers=auth_headers(editor_token)
    )
    slug = create.get_json()["data"]["slug"]
    assert "user_id" not in create.get_json()["data"]

    public_view = client.get(f"/api/v1/authors/{slug}")
    assert "user_id" not in public_view.get_json()["data"]["author"]


def test_author_delete_blocked_when_referenced_by_article(client, editor_token):
    author_resp = client.post(
        "/api/v1/authors", json=_base_payload(status="active"), headers=auth_headers(editor_token)
    )
    author_slug = author_resp.get_json()["data"]["slug"]

    client.post(
        "/api/v1/articles",
        json={
            "title": "A Story By Zainab",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Body."}],
        },
        headers=auth_headers(editor_token),
    )

    blocked = client.delete(f"/api/v1/authors/{author_slug}", headers=auth_headers(editor_token))
    assert blocked.status_code == 409

    archived = client.put(
        f"/api/v1/authors/{author_slug}",
        json=_base_payload(status="archived"),
        headers=auth_headers(editor_token),
    )
    assert archived.status_code == 200
    assert archived.get_json()["data"]["status"] == "archived"


def test_author_delete_allowed_when_unreferenced(client, editor_token):
    author_resp = client.post(
        "/api/v1/authors", json=_base_payload(name="Unreferenced Author"), headers=auth_headers(editor_token)
    )
    slug = author_resp.get_json()["data"]["slug"]

    deleted = client.delete(f"/api/v1/authors/{slug}", headers=auth_headers(editor_token))
    assert deleted.status_code == 200

    gone = client.get(f"/api/v1/authors/{slug}", headers=auth_headers(editor_token))
    assert gone.status_code == 404


def test_author_published_articles_visible_on_detail(client, editor_token):
    author_resp = client.post(
        "/api/v1/authors", json=_base_payload(status="active"), headers=auth_headers(editor_token)
    )
    author_slug = author_resp.get_json()["data"]["slug"]

    article_resp = client.post(
        "/api/v1/articles",
        json={
            "title": "Zainab's Published Story",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Body."}],
            "status": "published",
        },
        headers=auth_headers(editor_token),
    )
    assert article_resp.status_code == 201

    detail = client.get(f"/api/v1/authors/{author_slug}")
    assert detail.status_code == 200
    titles = [a["title"] for a in detail.get_json()["data"]["articles"]]
    assert "Zainab's Published Story" in titles
