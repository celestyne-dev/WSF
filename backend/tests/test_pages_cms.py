import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "pages-editor@example.com",
    "password": "supersecret1",
    "first_name": "Page",
    "last_name": "Editor",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "pages-nobody@example.com",
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
def editor_token(client, app):
    return _register_with_role(client, app, EDITOR_PAYLOAD, "editor")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_system_page(app, key="privacy", status="published"):
    from app.extensions import db
    from app.models.page import Page

    with app.app_context():
        page = Page.query.filter_by(key=key).first()
        if page is None:
            page = Page(
                key=key,
                slug=key,
                page_type="system",
                title=key.title(),
                content=[{"type": "paragraph", "text": "Seed body."}],
                status=status,
            )
            db.session.add(page)
        else:
            page.status = status
        db.session.commit()
        return page.id


class TestPublicPages:
    def test_seeded_system_pages_are_public(self, client, app):
        _make_system_page(app, "privacy")
        resp = client.get("/api/v1/pages/public/privacy")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["title"] == "Privacy"
        assert "content" in data

    def test_draft_page_not_publicly_visible(self, client, app):
        _make_system_page(app, "privacy", status="draft")
        resp = client.get("/api/v1/pages/public/privacy")
        assert resp.status_code == 404

    def test_public_serializer_excludes_internal_fields(self, client, app):
        _make_system_page(app, "privacy")
        data = client.get("/api/v1/pages/public/privacy").get_json()["data"]
        assert "status" not in data
        assert "internal_name" not in data
        assert "internalName" not in data
        assert "updated_by" not in data
        assert "updatedBy" not in data
        assert "last_reviewed_by" not in data
        assert "createdAt" not in data
        assert "created_at" not in data

    def test_unknown_key_404s_gracefully(self, client):
        resp = client.get("/api/v1/pages/public/does-not-exist")
        assert resp.status_code == 404
        assert resp.get_json()["success"] is False


class TestAdminPageCRUD:
    def test_list_requires_auth(self, client):
        assert client.get("/api/v1/pages").status_code == 401

    def test_list_requires_permission(self, client, no_permission_token):
        resp = client.get("/api/v1/pages", headers=auth_headers(no_permission_token))
        assert resp.status_code == 403

    def test_create_general_page(self, client, editor_token):
        resp = client.post(
            "/api/v1/pages",
            json={"title": "Careers at WSF", "content": [{"type": "paragraph", "text": "We are hiring."}]},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 201
        data = resp.get_json()["data"]
        assert data["slug"] == "careers-at-wsf"
        assert data["page_type"] == "general"

    def test_create_system_page_rejected(self, client, editor_token):
        resp = client.post(
            "/api/v1/pages",
            json={"title": "Fake System Page", "page_type": "system"},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 400

    def test_slug_collides_with_reserved_route(self, client, editor_token):
        resp = client.post(
            "/api/v1/pages",
            json={"title": "Articles", "slug": "articles"},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code in (400, 409)

    def test_slug_collides_with_existing_article(self, client, editor_token, app):
        from app.extensions import db
        from app.models.article import Article
        from app.models.people import Author

        with app.app_context():
            author = Author(slug="wsf-editorial", name="WSF Editorial")
            db.session.add(author)
            db.session.flush()
            article = Article(title="A Story", status="published", content=[], author_id=author.id, slug="a-story")
            db.session.add(article)
            db.session.commit()

        resp = client.post(
            "/api/v1/pages",
            json={"title": "A Story", "slug": "a-story"},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "slug_taken"

    def test_content_is_sanitized(self, client, editor_token):
        resp = client.post(
            "/api/v1/pages",
            json={
                "title": "Sanitize Test",
                "content": [{"type": "paragraph", "text": '<script>alert(1)</script>Hello <b>world</b>'}],
            },
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 201
        text = resp.get_json()["data"]["content"][0]["text"]
        assert "<script>" not in text
        assert "Hello" in text

    def test_update_general_page_content_seo_effective_date(self, client, editor_token):
        create = client.post(
            "/api/v1/pages", json={"title": "Editable Page"}, headers=auth_headers(editor_token)
        )
        page_id = create.get_json()["data"]["id"]

        update = client.put(
            f"/api/v1/pages/{page_id}",
            json={
                "content": [{"type": "paragraph", "text": "Updated body."}],
                "seo": {"title": "Custom SEO title"},
                "effectiveDate": "2026-01-01",
            },
            headers=auth_headers(editor_token),
        )
        assert update.status_code == 200
        data = update.get_json()["data"]
        assert data["content"][0]["text"] == "Updated body."
        assert data["seo"]["title"] == "Custom SEO title"
        assert data["effective_date"] == "2026-01-01" or data["effectiveDate"] == "2026-01-01"

    def test_publish_requires_pages_manage_or_publish_permission(self, client, editor_token, no_permission_token):
        # Same OR-of-two-permissions convention as Article's own
        # articles.manage/articles.publish split (pages.manage alone is
        # a superset that already covers publishing — pages.publish
        # exists for a narrower publish-only role nothing currently
        # grants). What's actually guaranteed: a user with neither
        # permission at all can't reach the publish action.
        create = client.post("/api/v1/pages", json={"title": "Needs Publish Perm"}, headers=auth_headers(editor_token))
        page_id = create.get_json()["data"]["id"]

        resp = client.put(
            f"/api/v1/pages/{page_id}/status", json={"status": "published"}, headers=auth_headers(no_permission_token)
        )
        assert resp.status_code == 403

        resp = client.put(
            f"/api/v1/pages/{page_id}/status", json={"status": "published"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "published"

    def test_general_page_delete_allowed(self, client, editor_token):
        create = client.post("/api/v1/pages", json={"title": "Deletable Page"}, headers=auth_headers(editor_token))
        page_id = create.get_json()["data"]["id"]
        resp = client.delete(f"/api/v1/pages/{page_id}", headers=auth_headers(editor_token))
        assert resp.status_code == 204


class TestSystemPageProtection:
    def test_system_page_delete_blocked(self, client, editor_token, app):
        page_id = _make_system_page(app, "privacy")
        resp = client.delete(f"/api/v1/pages/{page_id}", headers=auth_headers(editor_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "system_page_protected"

    def test_system_page_archive_blocked(self, client, editor_token, app):
        page_id = _make_system_page(app, "privacy")
        resp = client.put(f"/api/v1/pages/{page_id}/status", json={"status": "archived"}, headers=auth_headers(editor_token))
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "system_page_protected"

    def test_system_page_slug_edit_ignored(self, client, editor_token, app):
        page_id = _make_system_page(app, "privacy")
        resp = client.put(
            f"/api/v1/pages/{page_id}", json={"slug": "totally-different"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["slug"] == "privacy"

    def test_system_page_title_still_editable(self, client, editor_token, app):
        page_id = _make_system_page(app, "privacy")
        resp = client.put(
            f"/api/v1/pages/{page_id}", json={"title": "Our Privacy Commitment"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["title"] == "Our Privacy Commitment"

    def test_content_edit_on_published_page_never_404s_the_public_route(self, client, editor_token, app):
        # This CMS edits a page's single live row in place — the same
        # immediate-apply convention every other content type here uses
        # (Article included: a PUT to an already-published Article updates
        # the same row a reader sees). There is no separate staging copy.
        # What IS guaranteed: the public route never drops to a 404 or a
        # partially-written state mid-save — each field update is one
        # atomic transaction (see PageDetailResource.put), and a save
        # never implicitly changes `status` (that's a dedicated action).
        page_id = _make_system_page(app, "privacy", status="published")

        resp = client.put(
            f"/api/v1/pages/{page_id}",
            json={"content": [{"type": "paragraph", "text": "Revised privacy wording."}]},
            headers=auth_headers(editor_token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["status"] == "published"

        public = client.get("/api/v1/pages/public/privacy")
        assert public.status_code == 200
        assert public.get_json()["data"]["content"][0]["text"] == "Revised privacy wording."


class TestRevisionsAndReview:
    def test_revision_created_on_create_and_update(self, client, editor_token):
        create = client.post("/api/v1/pages", json={"title": "Revision Test"}, headers=auth_headers(editor_token))
        page_id = create.get_json()["data"]["id"]
        client.put(f"/api/v1/pages/{page_id}", json={"title": "Revision Test Updated"}, headers=auth_headers(editor_token))

        revisions = client.get(f"/api/v1/pages/{page_id}/revisions", headers=auth_headers(editor_token))
        assert revisions.status_code == 200
        assert len(revisions.get_json()["data"]) == 2

    def test_mark_reviewed_sets_reviewer_and_timestamp(self, client, editor_token, app):
        page_id = _make_system_page(app, "privacy")
        resp = client.put(f"/api/v1/pages/{page_id}/review", json={"note": "Legal reviewed this quarter."}, headers=auth_headers(editor_token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["last_reviewed_at"] is not None or data["lastReviewedAt"] is not None
        assert data["last_reviewed_by"]["id"] is not None or data["lastReviewedBy"]["id"] is not None


class TestAuditAndSeedIdempotency:
    def test_audit_log_written_on_create(self, client, editor_token, app):
        from app.models.audit import AuditLog

        client.post("/api/v1/pages", json={"title": "Audit Test"}, headers=auth_headers(editor_token))
        with app.app_context():
            entry = AuditLog.query.filter_by(action="page.create").first()
            assert entry is not None
            assert entry.entity_type == "Page"

    def test_seed_pages_is_idempotent_and_never_overwrites(self, app):
        from app.extensions import db
        from app.models.page import Page
        from app.services.demo_seed import _seed_pages

        with app.app_context():
            _seed_pages()
            db.session.commit()
            first_count = Page.query.count()

            about = Page.query.filter_by(key="about").first()
            about.title = "Admin Edited About"
            db.session.commit()

            _seed_pages()
            db.session.commit()

            assert Page.query.count() == first_count
            assert Page.query.filter_by(key="about").first().title == "Admin Edited About"
