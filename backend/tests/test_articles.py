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
            "content": [{"type": "paragraph", "text": "Body text."}],
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


def test_article_listing_filters_by_person_and_organization(client, editor_token, author_slug):
    person = client.post(
        "/api/v1/people", json={"name": "Naliaka Wafula"}, headers=auth_headers(editor_token)
    )
    assert person.status_code == 201
    person_slug = person.get_json()["data"]["slug"]

    with client.application.app_context():
        from app.extensions import db
        from app.models.people import Organization

        db.session.add(Organization(slug="kaziwave", name="Kaziwave"))
        db.session.commit()

    create = client.post(
        "/api/v1/articles",
        json={
            "title": "How Women Are Redefining Leadership",
            "authorSlug": author_slug,
            "relatedPersonSlugs": [person_slug],
            "relatedOrganizationSlugs": ["kaziwave"],
            "status": "published",
            "content": [{"type": "paragraph", "text": "Body text."}],
        },
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201

    by_person = client.get(f"/api/v1/articles?person={person_slug}")
    assert by_person.status_code == 200
    assert len(by_person.get_json()["data"]) == 1

    by_org = client.get("/api/v1/articles?organization=kaziwave")
    assert by_org.status_code == 200
    assert len(by_org.get_json()["data"]) == 1

    no_match = client.get("/api/v1/articles?person=nobody")
    assert no_match.status_code == 200
    assert no_match.get_json()["data"] == []


def test_article_content_persists_and_updates(client, editor_token, author_slug):
    blocks = [
        {"type": "heading", "level": 2, "text": "A section heading"},
        {"type": "paragraph", "text": "First <strong>paragraph</strong> with <em>emphasis</em>."},
        {"type": "list", "style": "bullet", "items": ["One", "Two"]},
        {"type": "blockquote", "text": "A quoted line.", "attribution": "Someone"},
    ]
    create = client.post(
        "/api/v1/articles",
        json={"title": "Content Persistence Check", "authorSlug": author_slug, "content": blocks},
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    slug = create.get_json()["data"]["slug"]
    assert len(create.get_json()["data"]["content"]) == 4

    # Reload as a fresh GET (simulating "leave editor, reopen article").
    reopened = client.get(f"/api/v1/articles/{slug}", headers=auth_headers(editor_token))
    assert reopened.status_code == 200
    reloaded_blocks = reopened.get_json()["data"]["content"]
    assert len(reloaded_blocks) == 4
    assert reloaded_blocks[0]["text"] == "A section heading"
    assert reloaded_blocks[2]["items"] == ["One", "Two"]

    # Edit content and save again — must actually update, not just append.
    updated_blocks = blocks + [{"type": "divider"}]
    update = client.put(
        f"/api/v1/articles/{slug}",
        json={"title": "Content Persistence Check", "authorSlug": author_slug, "content": updated_blocks},
        headers=auth_headers(editor_token),
    )
    assert update.status_code == 200
    assert len(update.get_json()["data"]["content"]) == 5

    reloaded_again = client.get(f"/api/v1/articles/{slug}", headers=auth_headers(editor_token))
    assert len(reloaded_again.get_json()["data"]["content"]) == 5


def test_article_content_is_sanitized(client, editor_token, author_slug):
    blocks = [{"type": "paragraph", "text": '<script>alert(1)</script>Hello <a href="javascript:alert(1)">link</a>'}]
    create = client.post(
        "/api/v1/articles",
        json={"title": "Sanitize Check", "authorSlug": author_slug, "content": blocks},
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    text = create.get_json()["data"]["content"][0]["text"]
    assert "<script>" not in text
    assert "javascript:" not in text
    assert "Hello" in text


def test_article_revision_captures_content_changes(client, editor_token, author_slug):
    create = client.post(
        "/api/v1/articles",
        json={
            "title": "Revision Content Check",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Version one."}],
        },
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]

    client.put(
        f"/api/v1/articles/{slug}",
        json={
            "title": "Revision Content Check",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Version two."}],
        },
        headers=auth_headers(editor_token),
    )

    with client.application.app_context():
        from app.models.article import Article, ArticleRevision

        article = Article.query.filter_by(slug=slug).first()
        revisions = (
            ArticleRevision.query.filter_by(article_id=article.id).order_by(ArticleRevision.created_at.asc()).all()
        )
        assert len(revisions) == 2
        assert revisions[0].data["content"][0]["text"] == "Version one."
        assert revisions[1].data["content"][0]["text"] == "Version two."


def test_article_ai_fields_roundtrip(client, editor_token, author_slug):
    create = client.post(
        "/api/v1/articles",
        json={
            "title": "AI Fields Check",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Body."}],
            "aiInvolvement": "ai_assisted",
            "humanReviewed": True,
            "aiDisclosureRequired": True,
            "aiDisclosureText": "This article was created with assistance from generative AI.",
            "aiEditorialNotes": "Drafted with an LLM, fact-checked by the editor.",
        },
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    data = create.get_json()["data"]
    assert data["ai_involvement"] == "ai_assisted"
    assert data["human_reviewed"] is True
    assert data["ai_disclosure_required"] is True
    assert data["ai_disclosure_text"] == "This article was created with assistance from generative AI."
    # The creating editor can still see their own internal notes when
    # reloading the article for editing.
    assert data["ai_editorial_notes"] == "Drafted with an LLM, fact-checked by the editor."


def test_ai_editorial_notes_excluded_from_public_article(client, editor_token, author_slug):
    create = client.post(
        "/api/v1/articles",
        json={
            "title": "Public AI Notes Check",
            "authorSlug": author_slug,
            "status": "published",
            "content": [{"type": "paragraph", "text": "Body."}],
            "aiInvolvement": "ai_generated_reviewed",
            "humanReviewed": True,
            "aiDisclosureRequired": True,
            "aiDisclosureText": "Reviewed and edited by the WSF editorial team.",
            "aiEditorialNotes": "Internal note: verify statistics before next edit.",
        },
        headers=auth_headers(editor_token),
    )
    slug = create.get_json()["data"]["slug"]
    assert "ai_editorial_notes" in create.get_json()["data"]  # visible to the editor who just created it

    public = client.get(f"/api/v1/articles/{slug}")
    assert public.status_code == 200
    public_data = public.get_json()["data"]
    assert "ai_editorial_notes" not in public_data
    # The public disclosure text itself IS meant to be public.
    assert public_data["ai_disclosure_text"] == "Reviewed and edited by the WSF editorial team."
    assert public_data["ai_disclosure_required"] is True

    summary = client.get("/api/v1/articles")
    assert summary.status_code == 200
    assert "ai_editorial_notes" not in summary.get_json()["data"][0]


def test_publish_requires_content(client, editor_token, author_slug):
    create = client.post(
        "/api/v1/articles",
        json={"title": "Empty Body Should Not Publish", "authorSlug": author_slug, "content": []},
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    slug = create.get_json()["data"]["slug"]

    publish = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert publish.status_code == 422
    assert publish.get_json()["error"]["code"] == "publish_validation_failed"

    direct_publish = client.put(
        f"/api/v1/articles/{slug}",
        json={"title": "Empty Body Should Not Publish", "authorSlug": author_slug, "status": "published", "content": []},
        headers=auth_headers(editor_token),
    )
    assert direct_publish.status_code == 422


def test_publish_requires_human_review_when_ai_involved(client, editor_token, author_slug):
    create = client.post(
        "/api/v1/articles",
        json={
            "title": "AI Draft Needs Review",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Body."}],
            "aiInvolvement": "ai_generated_reviewed",
            "humanReviewed": False,
        },
        headers=auth_headers(editor_token),
    )
    assert create.status_code == 201
    slug = create.get_json()["data"]["slug"]

    publish = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert publish.status_code == 422
    assert "human-reviewed" in publish.get_json()["error"]["message"]

    # Confirming human review unblocks publication.
    client.put(
        f"/api/v1/articles/{slug}",
        json={
            "title": "AI Draft Needs Review",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Body."}],
            "aiInvolvement": "ai_generated_reviewed",
            "humanReviewed": True,
        },
        headers=auth_headers(editor_token),
    )
    publish_again = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert publish_again.status_code == 200


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
