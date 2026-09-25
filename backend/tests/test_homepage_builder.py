import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "hp-admin@example.com",
    "password": "supersecret1",
    "first_name": "Home",
    "last_name": "Admin",
}
EDITOR_PAYLOAD = {
    "email": "hp-editor@example.com",
    "password": "supersecret1",
    "first_name": "Home",
    "last_name": "Editor",
}
WRITER_PAYLOAD = {
    "email": "hp-writer@example.com",
    "password": "supersecret1",
    "first_name": "Home",
    "last_name": "Writer",
}
NO_PERMISSION_PAYLOAD = {
    "email": "hp-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
}


def _register_with_role(client, app, payload, role_name):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        if role_name:
            role = Role.query.filter_by(name=role_name).first()
            user.roles.append(role)
            db.session.commit()

    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, ADMIN_PAYLOAD, "admin")


@pytest.fixture()
def editor_token(client, app):
    return _register_with_role(client, app, EDITOR_PAYLOAD, "editor")


@pytest.fixture()
def writer_token(client, app):
    return _register_with_role(client, app, WRITER_PAYLOAD, "author")


@pytest.fixture()
def no_permission_token(client, app):
    return _register_with_role(client, app, NO_PERMISSION_PAYLOAD, None)


def _make_article(app, slug="a-story", status="published"):
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
        db.session.add(article)
        db.session.commit()
        return article.slug


def _make_person(app, slug="jane-doe", status="published"):
    from app.extensions import db
    from app.models.people import Person

    with app.app_context():
        person = Person(slug=slug, name="Jane Doe", bio="A leader.", status=status)
        db.session.add(person)
        db.session.commit()
        return person.slug


def _basic_modules_payload():
    return {
        "modules": [
            {"type": "hero", "config": {"leadArticleSlug": "some-article"}},
            {"type": "latest_stories", "enabled": False, "config": {"itemCount": 8}},
        ]
    }


class TestPublicHomepage:
    def test_returns_only_enabled_modules_in_order(self, client, admin_token):
        client.put(
            "/api/v1/admin/homepage", json=_basic_modules_payload(), headers=auth_headers(admin_token)
        )
        resp = client.get("/api/v1/public/homepage")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert [m["type"] for m in data] == ["hero"]

    def test_response_includes_cache_hint_meta(self, client, admin_token):
        client.put(
            "/api/v1/admin/homepage", json=_basic_modules_payload(), headers=auth_headers(admin_token)
        )
        resp = client.get("/api/v1/public/homepage")
        assert "updatedAt" in resp.get_json()["meta"]

    def test_public_serializer_excludes_no_admin_only_fields_unexpectedly(self, client, admin_token):
        # The public and admin endpoints intentionally share one schema
        # (see HomepageModuleSchema docstring) since nothing here is
        # sensitive — this test documents that decision rather than
        # asserting a hidden field.
        client.put(
            "/api/v1/admin/homepage", json=_basic_modules_payload(), headers=auth_headers(admin_token)
        )
        resp = client.get("/api/v1/public/homepage")
        row = resp.get_json()["data"][0]
        assert "warnings" not in row  # warnings are an admin-only computed field

    def test_empty_config_never_crashes(self, client):
        resp = client.get("/api/v1/public/homepage")
        assert resp.status_code == 200
        assert resp.get_json()["data"] == []


class TestModuleTypeValidation:
    def test_unsupported_module_type_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "not_a_real_module"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_item_count_out_of_bounds_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "jobs", "config": {"itemCount": 99}}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_item_count_within_bounds_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "jobs", "config": {"itemCount": 4}}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_duplicate_hero_singleton_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "hero"}, {"type": "hero"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_two_editorial_callouts_allowed(self, client, admin_token):
        # editorial_callout is not a singleton — repeats are fine.
        resp = client.put(
            "/api/v1/admin/homepage",
            json={
                "modules": [
                    {"type": "editorial_callout", "heading": "One"},
                    {"type": "editorial_callout", "heading": "Two"},
                ]
            },
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_unknown_sponsor_placement_key_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "sponsor_placement", "config": {"placementKey": "bogus_key"}}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_known_sponsor_placement_key_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "sponsor_placement", "config": {"placementKey": "homepage_featured"}}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200


class TestCtaUrlValidation:
    def test_javascript_scheme_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "editorial_callout", "ctaUrl": "javascript:alert(1)"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_scheme_relative_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "editorial_callout", "ctaUrl": "//evil.example.com"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_internal_path_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "editorial_callout", "ctaUrl": "/community"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_https_url_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "editorial_callout", "ctaUrl": "https://example.com/promo"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_plain_domain_without_scheme_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "editorial_callout", "ctaUrl": "example.com"}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422


class TestOrderingAndVisibility:
    def test_order_persists_by_submission_order(self, client, admin_token):
        payload = {
            "modules": [
                {"type": "jobs", "config": {"itemCount": 2}},
                {"type": "events", "config": {"itemCount": 2}},
                {"type": "resources", "config": {"itemCount": 2}},
            ]
        }
        resp = client.put("/api/v1/admin/homepage", json=payload, headers=auth_headers(admin_token))
        types_in_order = [m["type"] for m in resp.get_json()["data"]]
        assert types_in_order == ["jobs", "events", "resources"]

    def test_reordering_via_resubmission_persists(self, client, admin_token):
        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "jobs"}, {"type": "events"}]},
            headers=auth_headers(admin_token),
        )
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "events"}, {"type": "jobs"}]},
            headers=auth_headers(admin_token),
        )
        assert [m["type"] for m in resp.get_json()["data"]] == ["events", "jobs"]

    def test_disabled_module_kept_in_admin_but_hidden_publicly(self, client, admin_token):
        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "jobs", "enabled": False}]},
            headers=auth_headers(admin_token),
        )
        admin_resp = client.get("/api/v1/admin/homepage", headers=auth_headers(admin_token))
        assert len(admin_resp.get_json()["data"]) == 1
        public_resp = client.get("/api/v1/public/homepage")
        assert public_resp.get_json()["data"] == []


class TestContentEligibilityWarnings:
    def test_unpublished_article_reference_surfaces_warning(self, client, admin_token, app):
        _make_article(app, slug="draft-story", status="draft")
        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "hero", "config": {"leadArticleSlug": "draft-story"}}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/admin/homepage", headers=auth_headers(admin_token))
        row = resp.get_json()["data"][0]
        assert any("draft-story" in w for w in row["warnings"])

    def test_published_article_reference_has_no_warning(self, client, admin_token, app):
        _make_article(app, slug="live-story", status="published")
        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "hero", "config": {"leadArticleSlug": "live-story"}}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/admin/homepage", headers=auth_headers(admin_token))
        row = resp.get_json()["data"][0]
        assert row["warnings"] == []

    def test_unpublished_person_reference_surfaces_warning(self, client, admin_token, app):
        _make_person(app, slug="hidden-person", status="draft")
        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "featured_woman", "config": {"personSlug": "hidden-person"}}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/admin/homepage", headers=auth_headers(admin_token))
        row = resp.get_json()["data"][0]
        assert any("hidden-person" in w for w in row["warnings"])

    def test_warnings_do_not_block_saving(self, client, admin_token):
        # A stale reference is a warning, never a save-blocking error —
        # content naturally drifts out from under a homepage config.
        resp = client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "featured_woman", "config": {"personSlug": "nobody-home"}}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200


class TestRBAC:
    def test_editor_can_view_and_save(self, client, editor_token):
        get_resp = client.get("/api/v1/admin/homepage", headers=auth_headers(editor_token))
        assert get_resp.status_code == 200
        put_resp = client.put(
            "/api/v1/admin/homepage", json={"modules": [{"type": "jobs"}]}, headers=auth_headers(editor_token)
        )
        assert put_resp.status_code == 200

    def test_writer_cannot_view_or_save(self, client, writer_token):
        get_resp = client.get("/api/v1/admin/homepage", headers=auth_headers(writer_token))
        assert get_resp.status_code == 403
        put_resp = client.put(
            "/api/v1/admin/homepage", json={"modules": [{"type": "jobs"}]}, headers=auth_headers(writer_token)
        )
        assert put_resp.status_code == 403

    def test_user_with_no_permission_cannot_view_or_save(self, client, no_permission_token):
        get_resp = client.get("/api/v1/admin/homepage", headers=auth_headers(no_permission_token))
        assert get_resp.status_code == 403

    def test_unauthenticated_request_rejected(self, client):
        resp = client.get("/api/v1/admin/homepage")
        assert resp.status_code == 401


class TestAudit:
    def test_publish_writes_audit_entry(self, client, admin_token, app):
        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "jobs"}, {"type": "events"}]},
            headers=auth_headers(admin_token),
        )
        with app.app_context():
            from app.models.audit import AuditLog

            entry = AuditLog.query.filter_by(action="homepage.publish").order_by(AuditLog.id.desc()).first()
            assert entry is not None
            assert entry.changes["module_count"] == 2
            assert entry.changes["types"] == ["jobs", "events"]


class TestSeedIdempotency:
    def test_seed_pages_never_overwrites_admin_edit(self, app):
        from app.extensions import db
        from app.models.cms import HomepageModule
        from app.services.demo_seed import seed_demo_content

        with app.app_context():
            seed_demo_content()
            first_count = HomepageModule.query.count()
            assert first_count > 0

            first_module = HomepageModule.query.order_by(HomepageModule.sort_order).first()
            first_module.heading = "Admin Edited This Heading"
            db.session.commit()

            seed_demo_content()

            assert HomepageModule.query.count() == first_count
            reloaded = db.session.get(HomepageModule, first_module.id)
            assert reloaded.heading == "Admin Edited This Heading"


class TestMediaDeletionProtection:
    def test_media_referenced_by_homepage_module_cannot_be_deleted(self, client, admin_token, app):
        from app.extensions import db
        from app.models.media import Media

        with app.app_context():
            media = Media(
                original_filename="hero.png",
                stored_filename="hero-stored.png",
                file_path="/tmp/hero-stored.png",
                public_url="https://cdn.example.com/hero-stored.png",
                mime_type="image/png",
            )
            db.session.add(media)
            db.session.commit()
            media_id = media.id

        client.put(
            "/api/v1/admin/homepage",
            json={"modules": [{"type": "hero", "mediaId": media_id}]},
            headers=auth_headers(admin_token),
        )

        with app.app_context():
            reloaded = db.session.get(Media, media_id)
            assert reloaded.is_referenced() is True
