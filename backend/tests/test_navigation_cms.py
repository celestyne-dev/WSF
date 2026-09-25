import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {"email": "nav-admin@example.com", "password": "supersecret1", "first_name": "Nav", "last_name": "Admin"}
EDITOR_PAYLOAD = {"email": "nav-editor@example.com", "password": "supersecret1", "first_name": "Nav", "last_name": "Editor"}
WRITER_PAYLOAD = {"email": "nav-writer@example.com", "password": "supersecret1", "first_name": "Nav", "last_name": "Writer"}
NO_PERMISSION_PAYLOAD = {"email": "nav-nobody@example.com", "password": "supersecret1", "first_name": "No", "last_name": "Permission"}


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


def _make_topic(app, slug="leadership", status="published"):
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


def _make_series(app, slug="flagship", status="published"):
    from app.extensions import db
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series(slug=slug, name="Flagship Series", status=status)
        db.session.add(series)
        db.session.commit()
        return series.id


def _make_page(app, key="corrections", status="published"):
    from app.extensions import db
    from app.models.page import Page

    with app.app_context():
        page = Page(key=key, slug=key, page_type="general", title="A Page", content=[], status=status)
        db.session.add(page)
        db.session.commit()
        return page.id


def _basic_payload():
    return {"menus": [{"key": "primary", "items": [{"label": "Jobs", "url": "/jobs"}]}]}


class TestPublicNavigation:
    def test_returns_visible_items_in_order(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "A", "url": "/a"}, {"label": "B", "url": "/b"}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        assert resp.status_code == 200
        items = resp.get_json()["data"]["menus"]["primary"]["items"]
        assert [i["label"] for i in items] == ["A", "B"]

    def test_hidden_item_excluded_publicly(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {
                        "key": "primary",
                        "items": [{"label": "Visible", "url": "/v"}, {"label": "Hidden", "url": "/h", "visible": False}],
                    }
                ]
            },
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        items = resp.get_json()["data"]["menus"]["primary"]["items"]
        assert [i["label"] for i in items] == ["Visible"]

    def test_hidden_parent_hides_children_too(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {
                        "key": "primary",
                        "items": [
                            {"label": "Parent", "url": "/p", "visible": False, "children": [{"label": "Child", "url": "/c"}]}
                        ],
                    }
                ]
            },
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        items = resp.get_json()["data"]["menus"]["primary"]["items"]
        assert items == []

    def test_public_response_omits_admin_only_fields(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "A", "url": "/a"}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        item = resp.get_json()["data"]["menus"]["primary"]["items"][0]
        assert "warnings" not in item
        assert "topicId" not in item
        assert "effectiveUrl" not in item

    def test_empty_navigation_never_crashes(self, client):
        resp = client.get("/api/v1/public/navigation")
        assert resp.status_code == 200


class TestItemTypes:
    def test_topic_item_resolves_url_from_slug(self, client, admin_token, app):
        topic_id = _make_topic(app, slug="leadership")
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Leadership", "itemType": "topic", "topicId": topic_id}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        item = resp.get_json()["data"]["menus"]["primary"]["items"][0]
        assert item["url"] == "/topics/leadership"

    def test_series_item_resolves_url_from_slug(self, client, admin_token, app):
        series_id = _make_series(app, slug="flagship")
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Flagship", "itemType": "series", "seriesId": series_id}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        item = resp.get_json()["data"]["menus"]["primary"]["items"][0]
        assert item["url"] == "/series/flagship"

    def test_page_item_resolves_url_from_slug(self, client, admin_token, app):
        page_id = _make_page(app, key="corrections")
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Corrections", "itemType": "page", "pageId": page_id}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        item = resp.get_json()["data"]["menus"]["primary"]["items"][0]
        assert item["url"] == "/corrections"

    def test_group_item_with_no_public_children_is_dropped(self, client, admin_token, app):
        topic_id = _make_topic(app, slug="draft-topic", status="draft")
        client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {
                        "key": "primary",
                        "items": [
                            {
                                "label": "Group",
                                "itemType": "group",
                                "children": [{"label": "Draft Topic", "itemType": "topic", "topicId": topic_id}],
                            }
                        ],
                    }
                ]
            },
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        items = resp.get_json()["data"]["menus"]["primary"]["items"]
        assert items == []

    def test_unpublished_topic_excluded_publicly_but_kept_in_admin(self, client, admin_token, app):
        topic_id = _make_topic(app, slug="draft-only", status="draft")
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Draft Only", "itemType": "topic", "topicId": topic_id}]}]},
            headers=auth_headers(admin_token),
        )
        public = client.get("/api/v1/public/navigation")
        assert public.get_json()["data"]["menus"]["primary"]["items"] == []

        admin_view = client.get("/api/v1/admin/navigation", headers=auth_headers(admin_token))
        primary_menu = next(m for m in admin_view.get_json()["data"] if m["key"] == "primary")
        item = primary_menu["items"][0]
        assert "not currently public" in item["warnings"][0]

    def test_topic_without_existing_topic_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Ghost", "itemType": "topic", "topicId": 999999}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_group_without_url_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Group", "itemType": "group"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200


class TestExternalUrlValidation:
    def test_javascript_scheme_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Evil", "itemType": "external", "url": "javascript:alert(1)"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_data_scheme_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Evil", "itemType": "external", "url": "data:text/html,x"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_valid_https_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Partner", "itemType": "external", "url": "https://example.com"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200


class TestInternalRouteSafety:
    def test_admin_route_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Sneaky", "url": "/admin/users"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_api_route_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Sneaky", "url": "/api/v1/users"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_scheme_relative_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Sneaky", "url": "//evil.example.com"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_normal_internal_route_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Jobs", "url": "/jobs"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200


class TestDepthAndHierarchy:
    def test_two_levels_accepted(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {"key": "primary", "items": [{"label": "Parent", "url": "/p", "children": [{"label": "Child", "url": "/c"}]}]}
                ]
            },
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200

    def test_three_levels_rejected(self, client, admin_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {
                        "key": "primary",
                        "items": [
                            {
                                "label": "A",
                                "url": "/a",
                                "children": [{"label": "B", "url": "/b", "children": [{"label": "C", "url": "/c"}]}],
                            }
                        ],
                    }
                ]
            },
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 422

    def test_reorder_persists(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "First", "url": "/1"}, {"label": "Second", "url": "/2"}]}]},
            headers=auth_headers(admin_token),
        )
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Second", "url": "/2"}, {"label": "First", "url": "/1"}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        items = resp.get_json()["data"]["menus"]["primary"]["items"]
        assert [i["label"] for i in items] == ["Second", "First"]

    def test_updating_one_menu_does_not_touch_others(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {"key": "primary", "items": [{"label": "P", "url": "/p"}]},
                    {"key": "footer_legal", "heading": "Legal", "items": [{"label": "Privacy", "url": "/privacy"}]},
                ]
            },
            headers=auth_headers(admin_token),
        )
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "P2", "url": "/p2"}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/public/navigation")
        legal_items = resp.get_json()["data"]["menus"]["footer_legal"]["items"]
        assert [i["label"] for i in legal_items] == ["Privacy"]


class TestDuplicateDestinationWarning:
    def test_duplicate_top_level_destinations_flagged(self, client, admin_token):
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Jobs", "url": "/jobs"}, {"label": "Careers", "url": "/jobs"}]}]},
            headers=auth_headers(admin_token),
        )
        resp = client.get("/api/v1/admin/navigation", headers=auth_headers(admin_token))
        primary_menu = next(m for m in resp.get_json()["data"] if m["key"] == "primary")
        assert any("Duplicate destination" in w for w in primary_menu["items"][1]["warnings"])


class TestRBAC:
    def test_editor_can_view_and_save(self, client, editor_token):
        get_resp = client.get("/api/v1/admin/navigation", headers=auth_headers(editor_token))
        assert get_resp.status_code == 200
        put_resp = client.put(
            "/api/v1/admin/navigation", json=_basic_payload(), headers=auth_headers(editor_token)
        )
        assert put_resp.status_code == 200

    def test_writer_cannot_view_or_save(self, client, writer_token):
        assert client.get("/api/v1/admin/navigation", headers=auth_headers(writer_token)).status_code == 403
        assert client.put(
            "/api/v1/admin/navigation", json=_basic_payload(), headers=auth_headers(writer_token)
        ).status_code == 403

    def test_no_permission_user_blocked(self, client, no_permission_token):
        assert client.get("/api/v1/admin/navigation", headers=auth_headers(no_permission_token)).status_code == 403

    def test_unauthenticated_rejected(self, client):
        assert client.get("/api/v1/admin/navigation").status_code == 401


class TestAudit:
    def test_publish_writes_audit_entry(self, client, admin_token, app):
        client.put("/api/v1/admin/navigation", json=_basic_payload(), headers=auth_headers(admin_token))
        with app.app_context():
            from app.models.audit import AuditLog

            entry = AuditLog.query.filter_by(action="navigation.publish").order_by(AuditLog.id.desc()).first()
            assert entry is not None
            assert entry.changes["menu_keys"] == ["primary"]


class TestSafeDeleteAndContentProtection:
    def test_removing_topic_nav_item_does_not_delete_topic(self, client, admin_token, app):
        topic_id = _make_topic(app, slug="leadership")
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Leadership", "itemType": "topic", "topicId": topic_id}]}]},
            headers=auth_headers(admin_token),
        )
        # Removing the item from the menu (empty items list) must not touch the Topic row.
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": []}]},
            headers=auth_headers(admin_token),
        )
        with app.app_context():
            from app.models.taxonomy import Topic

            assert Topic.query.get(topic_id) is not None

    def test_removing_page_nav_item_does_not_delete_page(self, client, admin_token, app):
        page_id = _make_page(app, key="corrections")
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Corrections", "itemType": "page", "pageId": page_id}]}]},
            headers=auth_headers(admin_token),
        )
        client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": []}]},
            headers=auth_headers(admin_token),
        )
        with app.app_context():
            from app.models.page import Page

            assert Page.query.get(page_id) is not None


class TestSeedIdempotency:
    def test_seed_never_overwrites_admin_edit(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.demo_seed import seed_demo_content

        with app.app_context():
            seed_demo_content()
            primary = Menu.query.filter_by(key="primary").first()
            first_count = MenuItem.query.filter_by(menu_id=primary.id).count()
            assert first_count > 0

            top_item = MenuItem.query.filter_by(menu_id=primary.id, parent_id=None).first()
            top_item.label = "Admin Edited This Label"
            db.session.commit()

            seed_demo_content()

            reloaded = db.session.get(MenuItem, top_item.id)
            assert reloaded.label == "Admin Edited This Label"
            assert MenuItem.query.filter_by(menu_id=primary.id).count() == first_count
