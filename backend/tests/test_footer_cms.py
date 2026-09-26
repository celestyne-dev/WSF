import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {"email": "footer-admin@example.com", "password": "supersecret1", "first_name": "Footer", "last_name": "Admin"}
EDITOR_PAYLOAD = {"email": "footer-editor@example.com", "password": "supersecret1", "first_name": "Footer", "last_name": "Editor"}
WRITER_PAYLOAD = {"email": "footer-writer@example.com", "password": "supersecret1", "first_name": "Footer", "last_name": "Writer"}
NO_PERMISSION_PAYLOAD = {"email": "footer-nobody@example.com", "password": "supersecret1", "first_name": "No", "last_name": "Permission"}


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


def _make_topic(app, slug="footer-leadership", status="published"):
    from app.extensions import db
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic.query.filter_by(slug=slug).first()
        if topic is None:
            topic = Topic(slug=slug, name=slug.title(), status=status)
            db.session.add(topic)
        else:
            topic.status = status
        db.session.commit()
        return topic.id


def _make_series(app, slug="footer-flagship", status="published"):
    from app.extensions import db
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series(slug=slug, name="Footer Flagship Series", status=status)
        db.session.add(series)
        db.session.commit()
        return series.id


def _make_page(app, key="footer-test-page", status="published"):
    from app.extensions import db
    from app.models.page import Page

    with app.app_context():
        page = Page.query.filter_by(key=key).first()
        if page is None:
            page = Page(key=key, slug=key, page_type="general", title="A Page", content=[], status=status)
            db.session.add(page)
        else:
            page.status = status
        db.session.commit()
        return page.id


def _basic_payload(**overrides):
    payload = {
        "groups": [
            {"heading": "Explore", "visible": True, "items": [{"label": "Stories", "itemType": "route", "url": "/topics"}]},
        ],
        "socialLinks": [],
        "settings": {},
    }
    payload.update(overrides)
    return payload


def _put(client, token, **overrides):
    return client.put("/api/v1/admin/footer", json=_basic_payload(**overrides), headers=auth_headers(token))


class TestPublicFooterRetrieval:
    def test_returns_settings_groups_and_social_links(self, client, admin_token):
        _put(
            client,
            admin_token,
            settings={"brandDescription": "A brand line.", "copyrightText": "Test Org. All rights reserved."},
        )
        resp = client.get("/api/v1/public/footer")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["settings"]["brandDescription"] == "A brand line."
        assert data["settings"]["copyrightText"] == "Test Org. All rights reserved."
        assert data["groups"][0]["heading"] == "Explore"
        assert data["socialLinks"] == []

    def test_never_crashes_with_no_footer_configured(self, client):
        resp = client.get("/api/v1/public/footer")
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert isinstance(data["groups"], list)
        assert isinstance(data["socialLinks"], list)


class TestGroupVisibilityAndOrdering:
    def test_hidden_group_excluded_publicly_but_kept_in_admin(self, client, admin_token):
        _put(
            client,
            admin_token,
            groups=[
                {"heading": "Explore", "visible": True, "items": [{"label": "Stories", "itemType": "route", "url": "/topics"}]},
                {"heading": "Hidden Group", "visible": False, "items": [{"label": "Jobs", "itemType": "route", "url": "/jobs"}]},
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert [g["heading"] for g in public["groups"]] == ["Explore"]

        admin = client.get("/api/v1/admin/footer", headers=auth_headers(admin_token)).get_json()["data"]
        assert sorted(g["heading"] for g in admin["groups"]) == ["Explore", "Hidden Group"]

    def test_group_with_no_visible_links_hidden_publicly(self, client, admin_token):
        _put(
            client,
            admin_token,
            groups=[
                {"heading": "Empty", "visible": True, "items": [{"label": "Jobs", "itemType": "route", "url": "/jobs", "visible": False}]},
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["groups"] == []

    def test_group_order_persisted_and_reflected_publicly(self, client, admin_token):
        _put(
            client,
            admin_token,
            groups=[
                {"heading": "First", "items": [{"label": "A", "itemType": "route", "url": "/a"}]},
                {"heading": "Second", "items": [{"label": "B", "itemType": "route", "url": "/b"}]},
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert [g["heading"] for g in public["groups"]] == ["First", "Second"]

        # Reorder and re-save.
        _put(
            client,
            admin_token,
            groups=[
                {"heading": "Second", "items": [{"label": "B", "itemType": "route", "url": "/b"}]},
                {"heading": "First", "items": [{"label": "A", "itemType": "route", "url": "/a"}]},
            ],
        )
        public2 = client.get("/api/v1/public/footer").get_json()["data"]
        assert [g["heading"] for g in public2["groups"]] == ["Second", "First"]


class TestLinkVisibilityAndOrdering:
    def test_hidden_link_excluded_publicly(self, client, admin_token):
        _put(
            client,
            admin_token,
            groups=[
                {
                    "heading": "Explore",
                    "items": [
                        {"label": "Stories", "itemType": "route", "url": "/topics"},
                        {"label": "Jobs", "itemType": "route", "url": "/jobs", "visible": False},
                    ],
                }
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        labels = [i["label"] for i in public["groups"][0]["items"]]
        assert labels == ["Stories"]

    def test_link_order_persisted(self, client, admin_token):
        _put(
            client,
            admin_token,
            groups=[
                {
                    "heading": "Explore",
                    "items": [
                        {"label": "Second", "itemType": "route", "url": "/b"},
                        {"label": "First", "itemType": "route", "url": "/a"},
                    ],
                }
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        labels = [i["label"] for i in public["groups"][0]["items"]]
        assert labels == ["Second", "First"]


class TestEntityLinkTypes:
    def test_page_link_resolves_url_from_slug(self, client, admin_token, app):
        page_id = _make_page(app, key="footer-page-1")
        _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "A Page", "itemType": "page", "pageId": page_id}]}])
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["groups"][0]["items"][0]["url"] == "/footer-page-1"

    def test_topic_link_resolves_url_from_slug(self, client, admin_token, app):
        topic_id = _make_topic(app)
        _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Leadership", "itemType": "topic", "topicId": topic_id}]}])
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["groups"][0]["items"][0]["url"] == "/topics/footer-leadership"

    def test_series_link_resolves_url_from_slug(self, client, admin_token, app):
        series_id = _make_series(app)
        _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Flagship", "itemType": "series", "seriesId": series_id}]}])
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["groups"][0]["items"][0]["url"] == "/series/footer-flagship"

    def test_topic_without_existing_topic_rejected(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Ghost", "itemType": "topic", "topicId": 999999}]}])
        assert resp.status_code == 422

    def test_unpublished_page_excluded_publicly_but_kept_in_admin_with_warning(self, client, admin_token, app):
        page_id = _make_page(app, key="footer-draft-page", status="draft")
        _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "Draft Page", "itemType": "page", "pageId": page_id}]}])

        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["groups"] == []

        admin = client.get("/api/v1/admin/footer", headers=auth_headers(admin_token)).get_json()["data"]
        group = next(g for g in admin["groups"] if g["heading"] == "About")
        assert group["items"][0]["warnings"]


class TestLegalLinkBehavior:
    def test_legal_page_link_survives_relabel_without_changing_route(self, client, admin_token, app):
        page_id = _make_page(app, key="privacy")
        _put(client, admin_token, groups=[{"heading": "Legal", "items": [{"label": "Privacy Policy", "itemType": "page", "pageId": page_id}]}])
        public1 = client.get("/api/v1/public/footer").get_json()["data"]
        assert public1["groups"][0]["items"][0]["url"] == "/privacy"

        _put(client, admin_token, groups=[{"heading": "Legal", "items": [{"label": "Privacy", "itemType": "page", "pageId": page_id}]}])
        public2 = client.get("/api/v1/public/footer").get_json()["data"]
        assert public2["groups"][0]["items"][0]["url"] == "/privacy"
        assert public2["groups"][0]["items"][0]["label"] == "Privacy"


class TestInternalRouteSafety:
    def test_admin_route_rejected(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Bad", "itemType": "route", "url": "/admin/users"}]}])
        assert resp.status_code == 422

    def test_api_route_rejected(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Bad", "itemType": "route", "url": "/api/v1/admin/footer"}]}])
        assert resp.status_code == 422

    def test_normal_route_accepted(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Jobs", "itemType": "route", "url": "/jobs"}]}])
        assert resp.status_code == 200


class TestExternalUrlValidation:
    def test_javascript_scheme_rejected(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "Bad", "itemType": "external", "url": "javascript:alert(1)"}]}])
        assert resp.status_code == 422

    def test_data_scheme_rejected(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "Bad", "itemType": "external", "url": "data:text/html,x"}]}])
        assert resp.status_code == 422

    def test_https_accepted(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "Partner", "itemType": "external", "url": "https://example.com"}]}])
        assert resp.status_code == 200


class TestSocialLinks:
    def test_social_crud_round_trip(self, client, admin_token):
        resp = _put(
            client,
            admin_token,
            socialLinks=[{"platform": "linkedin", "url": "https://linkedin.com/company/wsf", "handle": "WSF", "visible": True}],
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["socialLinks"][0]["platform"] == "linkedin"

        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["socialLinks"][0]["platform"] == "linkedin"
        assert public["socialLinks"][0]["label"] == "Women Shaping Futures on LinkedIn"

    def test_hidden_social_link_excluded_publicly(self, client, admin_token):
        _put(
            client,
            admin_token,
            socialLinks=[
                {"platform": "linkedin", "url": "https://linkedin.com/company/wsf", "visible": True},
                {"platform": "instagram", "url": "https://instagram.com/wsf", "visible": False},
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert [s["platform"] for s in public["socialLinks"]] == ["linkedin"]

    def test_custom_accessible_label_used_when_set(self, client, admin_token):
        _put(client, admin_token, socialLinks=[{"platform": "linkedin", "url": "https://linkedin.com/company/wsf", "label": "Follow WSF"}])
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["socialLinks"][0]["label"] == "Follow WSF"

    def test_invalid_platform_rejected(self, client, admin_token):
        resp = _put(client, admin_token, socialLinks=[{"platform": "myspace", "url": "https://myspace.com/wsf"}])
        assert resp.status_code == 422

    def test_unsafe_social_url_rejected(self, client, admin_token):
        resp = _put(client, admin_token, socialLinks=[{"platform": "linkedin", "url": "javascript:alert(1)"}])
        assert resp.status_code == 422

    def test_social_order_persisted(self, client, admin_token):
        _put(
            client,
            admin_token,
            socialLinks=[
                {"platform": "instagram", "url": "https://instagram.com/wsf"},
                {"platform": "linkedin", "url": "https://linkedin.com/company/wsf"},
            ],
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert [s["platform"] for s in public["socialLinks"]] == ["instagram", "linkedin"]


class TestFooterSettings:
    def test_newsletter_cta_configuration(self, client, admin_token):
        _put(
            client,
            admin_token,
            settings={"newsletterHeading": "Join us", "newsletterDescription": "Weekly updates.", "newsletterVisible": False},
        )
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["settings"]["newsletterHeading"] == "Join us"
        assert public["settings"]["newsletterDescription"] == "Weekly updates."
        assert public["settings"]["newsletterVisible"] is False

    def test_branding_configuration(self, client, admin_token):
        _put(client, admin_token, settings={"brandDescription": "A global platform for women."})
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["settings"]["brandDescription"] == "A global platform for women."

    def test_copyright_configuration(self, client, admin_token):
        _put(client, admin_token, settings={"copyrightText": "WSF Global. All rights reserved."})
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["settings"]["copyrightText"] == "WSF Global. All rights reserved."

    def test_contact_email_configuration(self, client, admin_token):
        _put(client, admin_token, settings={"contactEmail": "hello@womenshapingfutures.org"})
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert public["settings"]["contactEmail"] == "hello@womenshapingfutures.org"

    def test_invalid_contact_email_rejected(self, client, admin_token):
        resp = _put(client, admin_token, settings={"contactEmail": "not-an-email"})
        assert resp.status_code == 422

    def test_html_in_brand_description_rejected(self, client, admin_token):
        resp = _put(client, admin_token, settings={"brandDescription": "<script>alert(1)</script>"})
        assert resp.status_code == 422

    def test_overlong_brand_description_rejected(self, client, admin_token):
        resp = _put(client, admin_token, settings={"brandDescription": "x" * 400})
        assert resp.status_code == 422


class TestGroupAndLinkCrud:
    def test_create_group(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "Brand New", "items": []}])
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["groups"][0]["heading"] == "Brand New"
        assert data["groups"][0]["key"].startswith("footer_")

    def test_rename_group_keeps_same_key(self, client, admin_token):
        first = _put(client, admin_token, groups=[{"heading": "Original", "items": []}])
        key = first.get_json()["data"]["groups"][0]["key"]
        second = _put(client, admin_token, groups=[{"key": key, "heading": "Renamed", "items": []}])
        data = second.get_json()["data"]
        assert data["groups"][0]["key"] == key
        assert data["groups"][0]["heading"] == "Renamed"

    def test_omitted_group_is_deleted(self, client, admin_token):
        first = _put(
            client,
            admin_token,
            groups=[{"heading": "Keep", "items": []}, {"heading": "Drop", "items": []}],
        )
        groups_by_heading = {g["heading"]: g["key"] for g in first.get_json()["data"]["groups"]}
        second = _put(client, admin_token, groups=[{"key": groups_by_heading["Keep"], "heading": "Keep", "items": []}])
        data = second.get_json()["data"]
        assert [g["heading"] for g in data["groups"]] == ["Keep"]

    def test_too_many_groups_rejected(self, client, admin_token):
        groups = [{"heading": f"Group {i}", "items": []} for i in range(9)]
        resp = _put(client, admin_token, groups=groups)
        assert resp.status_code == 422

    def test_link_label_length_validated(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "x" * 200, "itemType": "route", "url": "/jobs"}]}])
        assert resp.status_code == 422

    def test_group_heading_length_validated(self, client, admin_token):
        resp = _put(client, admin_token, groups=[{"heading": "x" * 100, "items": []}])
        assert resp.status_code == 422


class TestSafeDeleteAndContentProtection:
    def test_removing_page_link_does_not_delete_page(self, client, admin_token, app):
        page_id = _make_page(app, key="footer-safe-page")
        _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "A Page", "itemType": "page", "pageId": page_id}]}])
        _put(client, admin_token, groups=[{"heading": "About", "items": []}])
        with app.app_context():
            from app.models.page import Page

            assert Page.query.get(page_id) is not None

    def test_removing_topic_link_does_not_delete_topic(self, client, admin_token, app):
        topic_id = _make_topic(app, slug="footer-safe-topic")
        _put(client, admin_token, groups=[{"heading": "Explore", "items": [{"label": "Topic", "itemType": "topic", "topicId": topic_id}]}])
        _put(client, admin_token, groups=[{"heading": "Explore", "items": []}])
        with app.app_context():
            from app.models.taxonomy import Topic

            assert Topic.query.get(topic_id) is not None

    def test_deleting_group_does_not_delete_linked_page(self, client, admin_token, app):
        page_id = _make_page(app, key="footer-group-delete-page")
        _put(client, admin_token, groups=[{"heading": "About", "items": [{"label": "A Page", "itemType": "page", "pageId": page_id}]}])
        _put(client, admin_token, groups=[])
        with app.app_context():
            from app.models.page import Page

            assert Page.query.get(page_id) is not None


class TestRBAC:
    def test_editor_can_view_and_save(self, client, editor_token):
        assert client.get("/api/v1/admin/footer", headers=auth_headers(editor_token)).status_code == 200
        assert _put(client, editor_token).status_code == 200

    def test_writer_cannot_view_or_save(self, client, writer_token):
        assert client.get("/api/v1/admin/footer", headers=auth_headers(writer_token)).status_code == 403
        assert _put(client, writer_token).status_code == 403

    def test_no_permission_user_blocked(self, client, no_permission_token):
        assert client.get("/api/v1/admin/footer", headers=auth_headers(no_permission_token)).status_code == 403

    def test_unauthenticated_rejected(self, client):
        assert client.get("/api/v1/admin/footer").status_code == 401


class TestPublicAdminSerializerSeparation:
    def test_public_payload_excludes_admin_metadata(self, client, admin_token):
        _put(client, admin_token, socialLinks=[{"platform": "linkedin", "url": "https://linkedin.com/company/wsf"}])
        public = client.get("/api/v1/public/footer").get_json()["data"]
        assert "warnings" not in public["groups"][0]["items"][0]
        assert "id" not in public["socialLinks"][0]
        assert "visible" not in public["socialLinks"][0]
        for group in public["groups"]:
            assert "visible" not in group


class TestAudit:
    def test_publish_writes_audit_entry(self, client, admin_token, app):
        _put(client, admin_token)
        with app.app_context():
            from app.models.audit import AuditLog

            entry = AuditLog.query.filter_by(action="footer.publish").order_by(AuditLog.id.desc()).first()
            assert entry is not None
            assert entry.changes["group_count"] == 1


class TestSeedIdempotency:
    def test_seeding_twice_does_not_duplicate_or_overwrite_admin_edits(self, client, admin_token, app):
        from app.services.demo_seed import seed_demo_content

        with app.app_context():
            seed_demo_content()

        _put(client, admin_token, groups=[{"heading": "Admin Edited", "items": []}], settings={"brandDescription": "Admin wrote this."})

        with app.app_context():
            seed_demo_content()

        admin = client.get("/api/v1/admin/footer", headers=auth_headers(admin_token)).get_json()["data"]
        assert any(g["heading"] == "Admin Edited" for g in admin["groups"])
        assert admin["settings"]["brandDescription"] == "Admin wrote this."
