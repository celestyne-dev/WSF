import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "tax-editor@example.com",
    "password": "supersecret1",
    "first_name": "Tia",
    "last_name": "Editor",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "tax-nobody@example.com",
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


def _make_article(app, slug="a-story", status="published", topics=None, category_id=None, series_id=None, tags=None):
    from app.extensions import db
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="wsf-editorial").first()
        if author is None:
            author = Author(slug="wsf-editorial", name="WSF Editorial")
            db.session.add(author)
            db.session.flush()
        article = Article(title="A Story Worth Reading", status=status, content=[], author_id=author.id, slug=slug)
        if category_id is not None:
            article.category_id = category_id
        if series_id is not None:
            article.series_id = series_id
        db.session.add(article)
        db.session.flush()
        for topic_id in topics or []:
            article.topics.append(db.session.get(__import__("app.models.taxonomy", fromlist=["Topic"]).Topic, topic_id))
        for tag_id in tags or []:
            article.tags.append(db.session.get(__import__("app.models.taxonomy", fromlist=["Tag"]).Tag, tag_id))
        db.session.commit()
        return article.id


# ---------------------------------------------------------------------------
# Topic
# ---------------------------------------------------------------------------


class TestTopicAdmin:
    def test_create_requires_permission(self, client, no_permission_token):
        resp = client.post(
            "/api/v1/admin/taxonomy/topics",
            json={"name": "Leadership"},
            headers=auth_headers(no_permission_token),
        )
        assert resp.status_code == 403

    def test_create_requires_auth(self, client):
        resp = client.post("/api/v1/admin/taxonomy/topics", json={"name": "Leadership"})
        assert resp.status_code == 401

    def test_create_defaults_to_draft_and_hides_from_public_list(self, client, editor_token):
        resp = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 201
        assert resp.get_json()["data"]["status"] == "draft"
        assert resp.get_json()["data"]["slug"] == "leadership"

        public = client.get("/api/v1/topics")
        assert "leadership" not in [t["slug"] for t in public.get_json()["data"]]

    def test_duplicate_name_case_insensitive_blocked(self, client, editor_token):
        client.post("/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token))
        resp = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "  leadership  "}, headers=auth_headers(editor_token)
        )
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "duplicate_name"

    def test_publish_makes_it_public_with_seo_and_hero(self, client, editor_token):
        create = client.post(
            "/api/v1/admin/taxonomy/topics",
            json={"name": "Leadership", "description": "About leading.", "seo": {"title": "Leadership | WSF"}},
            headers=auth_headers(editor_token),
        )
        topic_id = create.get_json()["data"]["id"]

        status = client.put(
            f"/api/v1/admin/taxonomy/topics/{topic_id}/status",
            json={"status": "published"},
            headers=auth_headers(editor_token),
        )
        assert status.status_code == 200
        assert status.get_json()["data"]["status"] == "published"

        detail = client.get("/api/v1/topics/leadership")
        assert detail.status_code == 200
        assert detail.get_json()["data"]["topic"]["seo"]["title"] == "Leadership | WSF"
        assert detail.get_json()["data"]["topic"]["description"] == "About leading."

    def test_rename_does_not_change_slug(self, client, editor_token):
        create = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token)
        )
        topic_id = create.get_json()["data"]["id"]

        update = client.put(
            f"/api/v1/admin/taxonomy/topics/{topic_id}",
            json={"name": "Leadership & Growth"},
            headers=auth_headers(editor_token),
        )
        assert update.status_code == 200
        assert update.get_json()["data"]["slug"] == "leadership"
        assert update.get_json()["data"]["name"] == "Leadership & Growth"

    def test_delete_blocked_when_referenced_by_article(self, client, editor_token, app):
        create = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token)
        )
        topic_id = create.get_json()["data"]["id"]
        _make_article(app, slug="leadership-story", topics=[topic_id])

        delete = client.delete(f"/api/v1/admin/taxonomy/topics/{topic_id}", headers=auth_headers(editor_token))
        assert delete.status_code == 409
        assert delete.get_json()["error"]["code"] == "reference_conflict"

    def test_archive_preserves_article_relationship_but_leaves_public_list(self, client, editor_token, app):
        from app.extensions import db
        from app.models.article import Article
        from app.models.taxonomy import Topic

        create = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "Leadership", "status": "published"}, headers=auth_headers(editor_token)
        )
        topic_id = create.get_json()["data"]["id"]
        article_id = _make_article(app, slug="leadership-story", topics=[topic_id])

        archive = client.put(
            f"/api/v1/admin/taxonomy/topics/{topic_id}/status",
            json={"status": "archived"},
            headers=auth_headers(editor_token),
        )
        assert archive.status_code == 200

        public = client.get("/api/v1/topics")
        assert "leadership" not in [t["slug"] for t in public.get_json()["data"]]

        with app.app_context():
            article = db.session.get(Article, article_id)
            topic = db.session.get(Topic, topic_id)
            assert topic in article.topics

    def test_delete_succeeds_when_unused(self, client, editor_token):
        create = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "Unused Topic"}, headers=auth_headers(editor_token)
        )
        topic_id = create.get_json()["data"]["id"]
        delete = client.delete(f"/api/v1/admin/taxonomy/topics/{topic_id}", headers=auth_headers(editor_token))
        assert delete.status_code == 204

    def test_usage_count_reflects_real_relationships(self, client, editor_token, app):
        create = client.post(
            "/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token)
        )
        topic_id = create.get_json()["data"]["id"]
        _make_article(app, slug="story-1", topics=[topic_id])
        _make_article(app, slug="story-2", topics=[topic_id])

        detail = client.get(f"/api/v1/admin/taxonomy/topics/{topic_id}", headers=auth_headers(editor_token))
        assert detail.get_json()["data"]["usageCount"] == 2


# ---------------------------------------------------------------------------
# Category
# ---------------------------------------------------------------------------


class TestCategoryAdmin:
    def test_create_and_duplicate_block(self, client, editor_token):
        create = client.post(
            "/api/v1/admin/taxonomy/categories", json={"name": "Editorial"}, headers=auth_headers(editor_token)
        )
        assert create.status_code == 201
        dup = client.post(
            "/api/v1/admin/taxonomy/categories", json={"name": "EDITORIAL"}, headers=auth_headers(editor_token)
        )
        assert dup.status_code == 409

    def test_delete_blocked_when_article_references_it(self, client, editor_token, app):
        create = client.post(
            "/api/v1/admin/taxonomy/categories", json={"name": "Editorial"}, headers=auth_headers(editor_token)
        )
        category_id = create.get_json()["data"]["id"]
        _make_article(app, slug="editorial-story", category_id=category_id)

        delete = client.delete(f"/api/v1/admin/taxonomy/categories/{category_id}", headers=auth_headers(editor_token))
        assert delete.status_code == 409

    def test_no_permission_cannot_create(self, client, no_permission_token):
        resp = client.post(
            "/api/v1/admin/taxonomy/categories", json={"name": "Editorial"}, headers=auth_headers(no_permission_token)
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Series
# ---------------------------------------------------------------------------


class TestSeriesAdmin:
    def test_create_publish_and_public_page(self, client, editor_token):
        create = client.post(
            "/api/v1/admin/taxonomy/series",
            json={"name": "Women Leading Organizations", "subtitle": "Profiles", "status": "published"},
            headers=auth_headers(editor_token),
        )
        assert create.status_code == 201
        slug = create.get_json()["data"]["slug"]

        detail = client.get(f"/api/v1/series/{slug}")
        assert detail.status_code == 200
        assert detail.get_json()["data"]["series"]["subtitle"] == "Profiles"

    def test_archive_keeps_article_relationship(self, client, editor_token, app):
        from app.extensions import db
        from app.models.article import Article
        from app.models.taxonomy import Series

        create = client.post(
            "/api/v1/admin/taxonomy/series",
            json={"name": "Women Leading Organizations", "status": "published"},
            headers=auth_headers(editor_token),
        )
        series_id = create.get_json()["data"]["id"]
        article_id = _make_article(app, slug="series-story", series_id=series_id)

        archive = client.put(
            f"/api/v1/admin/taxonomy/series/{series_id}/status",
            json={"status": "archived"},
            headers=auth_headers(editor_token),
        )
        assert archive.status_code == 200

        public_list = client.get("/api/v1/series")
        assert create.get_json()["data"]["slug"] not in [s["slug"] for s in public_list.get_json()["data"]]

        with app.app_context():
            article = db.session.get(Article, article_id)
            series = db.session.get(Series, series_id)
            assert article.series_id == series.id

    def test_delete_blocked_when_referenced(self, client, editor_token, app):
        create = client.post(
            "/api/v1/admin/taxonomy/series", json={"name": "Women Leading Organizations"}, headers=auth_headers(editor_token)
        )
        series_id = create.get_json()["data"]["id"]
        _make_article(app, slug="series-story", series_id=series_id)

        delete = client.delete(f"/api/v1/admin/taxonomy/series/{series_id}", headers=auth_headers(editor_token))
        assert delete.status_code == 409


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------


class TestTagAdmin:
    def test_create_and_duplicate_block(self, client, editor_token):
        create = client.post("/api/v1/admin/taxonomy/tags", json={"name": "Fintech"}, headers=auth_headers(editor_token))
        assert create.status_code == 201
        dup = client.post("/api/v1/admin/taxonomy/tags", json={"name": "fintech"}, headers=auth_headers(editor_token))
        assert dup.status_code == 409

    def test_delete_blocked_when_referenced(self, client, editor_token, app):
        create = client.post("/api/v1/admin/taxonomy/tags", json={"name": "Fintech"}, headers=auth_headers(editor_token))
        tag_id = create.get_json()["data"]["id"]
        _make_article(app, slug="fintech-story", tags=[tag_id])

        delete = client.delete(f"/api/v1/admin/taxonomy/tags/{tag_id}", headers=auth_headers(editor_token))
        assert delete.status_code == 409

    def test_merge_moves_relationships_and_deletes_source(self, client, editor_token, app):
        from app.extensions import db
        from app.models.article import Article
        from app.models.taxonomy import Tag

        src = client.post("/api/v1/admin/taxonomy/tags", json={"name": "Merge Src"}, headers=auth_headers(editor_token))
        dst = client.post("/api/v1/admin/taxonomy/tags", json={"name": "Merge Dst"}, headers=auth_headers(editor_token))
        src_id, dst_id = src.get_json()["data"]["id"], dst.get_json()["data"]["id"]
        article_id = _make_article(app, slug="merge-story", tags=[src_id])

        merge = client.post(
            "/api/v1/admin/taxonomy/tags/merge",
            json={"fromTagId": src_id, "toTagId": dst_id},
            headers=auth_headers(editor_token),
        )
        assert merge.status_code == 200

        with app.app_context():
            article = db.session.get(Article, article_id)
            dst_tag = db.session.get(Tag, dst_id)
            assert dst_tag in article.tags
            assert db.session.get(Tag, src_id) is None

    def test_merge_into_self_rejected(self, client, editor_token):
        create = client.post("/api/v1/admin/taxonomy/tags", json={"name": "Solo"}, headers=auth_headers(editor_token))
        tag_id = create.get_json()["data"]["id"]
        merge = client.post(
            "/api/v1/admin/taxonomy/tags/merge",
            json={"fromTagId": tag_id, "toTagId": tag_id},
            headers=auth_headers(editor_token),
        )
        assert merge.status_code == 400


# ---------------------------------------------------------------------------
# Cross-cutting: RBAC, audit log, public serializer shape
# ---------------------------------------------------------------------------


class TestCrossCutting:
    def test_audit_log_written_on_create(self, client, editor_token, app):
        from app.models.audit import AuditLog

        client.post("/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(editor_token))
        with app.app_context():
            entry = AuditLog.query.filter_by(action="topic.create").first()
            assert entry is not None
            assert entry.entity_type == "Topic"

    def test_public_endpoints_never_return_draft_or_archived(self, client, editor_token):
        client.post("/api/v1/admin/taxonomy/topics", json={"name": "Draft Topic", "status": "draft"}, headers=auth_headers(editor_token))
        client.post(
            "/api/v1/admin/taxonomy/categories", json={"name": "Draft Category", "status": "draft"}, headers=auth_headers(editor_token)
        )
        client.post(
            "/api/v1/admin/taxonomy/series", json={"name": "Draft Series", "status": "draft"}, headers=auth_headers(editor_token)
        )

        assert "draft-topic" not in [t["slug"] for t in client.get("/api/v1/topics").get_json()["data"]]
        assert "draft-category" not in [c["slug"] for c in client.get("/api/v1/categories").get_json()["data"]]
        assert "draft-series" not in [s["slug"] for s in client.get("/api/v1/series").get_json()["data"]]

    def test_public_list_endpoints_do_not_require_auth(self, client):
        assert client.get("/api/v1/topics").status_code == 200
        assert client.get("/api/v1/categories").status_code == 200
        assert client.get("/api/v1/series").status_code == 200

    def test_admin_list_endpoints_require_auth(self, client):
        assert client.get("/api/v1/admin/taxonomy/topics").status_code == 401
        assert client.get("/api/v1/admin/taxonomy/categories").status_code == 401
        assert client.get("/api/v1/admin/taxonomy/series").status_code == 401
        assert client.get("/api/v1/admin/taxonomy/tags").status_code == 401

    def test_taxonomy_manager_role_can_manage(self, client, app):
        payload = {
            "email": "tax-manager@example.com",
            "password": "supersecret1",
            "first_name": "Tax",
            "last_name": "Manager",
            "country_code": "US",
        }
        token = _register_with_role(client, app, payload, "taxonomy_manager")
        resp = client.post("/api/v1/admin/taxonomy/topics", json={"name": "Leadership"}, headers=auth_headers(token))
        assert resp.status_code == 201
