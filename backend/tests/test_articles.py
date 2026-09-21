import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "editor@example.com",
    "password": "supersecret1",
    "first_name": "Edie",
    "last_name": "Torres",
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
def author_slug(client, editor_token):
    resp = client.post(
        "/api/v1/authors",
        json={"name": "Amara Otieno", "role": "Senior Editor", "countryCode": "KE"},
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["slug"]


def test_topic_and_category_creation_and_listing(client, editor_token):
    resp = client.post(
        "/api/v1/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["slug"] == "leadership"

    listing = client.get("/api/v1/topics")
    assert listing.status_code == 200
    assert listing.get_json()["data"][0]["name"] == "Leadership"


def test_article_create_publish_and_slug_change_redirects(client, editor_token, author_slug):
    create = client.post(
        "/api/v1/articles",
        json={
            "title": "How Women Are Redefining Leadership",
            "excerpt": "A look at the shift.",
            "authorSlug": author_slug,
            "topicSlugs": [],
            "content": [{"type": "paragraph", "text": "Body text."}],
        },
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    article = create.get_json()["data"]
    assert article["slug"] == "how-women-are-redefining-leadership"
    assert article["status"] == "draft"

    # Not published yet — public GET must 404, not leak the draft.
    hidden = client.get(f"/api/v1/articles/{article['slug']}")
    assert hidden.status_code == 404

    # But the owning editor can preview it.
    preview = client.get(f"/api/v1/articles/{article['slug']}", headers=auth_headers(editor_token))
    assert preview.status_code == 200

    publish = client.post(f"/api/v1/articles/{article['slug']}/publish", headers=auth_headers(editor_token))
    assert publish.status_code == 200
    assert publish.get_json()["data"]["status"] == "published"
    assert publish.get_json()["data"]["publish_date"] is not None

    public = client.get(f"/api/v1/articles/{article['slug']}")
    assert public.status_code == 200
    assert public.get_json()["data"]["status"] == "published"

    old_slug = article["slug"]
    update = client.put(
        f"/api/v1/articles/{old_slug}",
        json={
            "title": "How Women Are Redefining Leadership",
            "slug": "redefining-leadership-updated",
            "excerpt": "A look at the shift.",
            "authorSlug": author_slug,
            "status": "published",
            "content": [{"type": "paragraph", "text": "Body text."}],
        },
        headers=auth_headers(editor_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["slug"] == "redefining-leadership-updated"

    followed = client.get(f"/api/v1/articles/{old_slug}")
    assert followed.status_code == 301
    assert followed.headers["Location"] == "/api/v1/articles/redefining-leadership-updated"

    revisions = client.get(f"/api/v1/articles/redefining-leadership-updated/revisions", headers=auth_headers(editor_token))
    assert revisions.status_code == 200
    assert len(revisions.get_json()["data"]) == 3  # created, published, updated


def test_article_listing_filters_by_topic(client, editor_token, author_slug):
    client.post("/api/v1/topics", json={"name": "Careers"}, headers=auth_headers(editor_token))
    create = client.post(
        "/api/v1/articles",
        json={
            "title": "Negotiating Your Next Raise",
            "authorSlug": author_slug,
            "topicSlugs": ["careers"],
            "status": "published",
            "content": [],
        },
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201

    listed = client.get("/api/v1/articles?topic=careers")
    assert listed.status_code == 200
    assert len(listed.get_json()["data"]) == 1

    empty = client.get("/api/v1/articles?topic=nonexistent-topic")
    assert empty.status_code == 200
    assert listed.get_json()["data"][0]["slug"] != "" and empty.get_json()["data"] == []


def test_article_requires_permission_to_create(client):
    client.post(
        "/api/v1/auth/register",
        json={
            "email": "plain@example.com",
            "password": "supersecret1",
            "first_name": "Plain",
            "last_name": "Member",
        },
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "plain@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/articles",
        json={"title": "Should Not Work", "authorSlug": "nobody", "content": []},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
