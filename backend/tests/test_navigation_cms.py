import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {"email": "nav-admin@example.com", "password": "supersecret1", "first_name": "Nav", "last_name": "Admin"}
EDITOR_PAYLOAD = {"email": "nav-editor@example.com", "password": "supersecret1", "first_name": "Nav", "last_name": "Editor"}
WRITER_PAYLOAD = {"email": "nav-writer@example.com", "password": "supersecret1", "first_name": "Nav", "last_name": "Writer"}
NO_PERMISSION_PAYLOAD = {"email": "nav-nobody@example.com", "password": "supersecret1", "first_name": "No", "last_name": "Permission"}
NAVIGATION_MANAGER_PAYLOAD = {
    "email": "nav-manager-only@example.com",
    "password": "supersecret1",
    "first_name": "Nav",
    "last_name": "ManagerOnly",
}
FOOTER_MANAGER_PAYLOAD = {
    "email": "footer-manager-only@example.com",
    "password": "supersecret1",
    "first_name": "Footer",
    "last_name": "ManagerOnly",
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


@pytest.fixture()
def navigation_manager_token(client, app):
    # "navigation_manager" grants navigation.manage/navigation.publish
    # ONLY (see app/services/rbac.py) — no footer.* — the exact shape the
    # footer-ownership boundary test needs: navigation.manage alone.
    return _register_with_role(client, app, NAVIGATION_MANAGER_PAYLOAD, "navigation_manager")


@pytest.fixture()
def footer_manager_token(client, app):
    # "footer_manager" grants footer.manage/footer.publish ONLY — no
    # navigation.* — so this fixture can never reach AdminNavigationResource
    # at all; it's used only to prove Footer CMS's own endpoint still works.
    return _register_with_role(client, app, FOOTER_MANAGER_PAYLOAD, "footer_manager")


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


class TestDefaultNavigationHealing:
    """Regression coverage for the public-header bug where "primary"/
    "secondary" were seeded once, early, and permanently missed every
    top-level section added afterwards (Topics/Events/Community/Shop/
    Partner With Us) because the old create-only seed guard
    (_seed_menu_if_empty) never adds anything to a menu that already has
    at least one item. seed_default_navigation() must heal that in place.
    """

    def test_heals_a_menu_stuck_at_an_old_partial_snapshot(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        about_page_id = _make_page(app, key="about")

        with app.app_context():
            # Reproduce the exact reported regression: a "primary"/
            # "secondary" that only has the sections that existed at the
            # time it was first (and only) ever seeded.
            primary = Menu(key="primary")
            secondary = Menu(key="secondary")
            db.session.add_all([primary, secondary])
            db.session.flush()
            for index, (label, url) in enumerate([("Stories", "/topics"), ("People", "/people"), ("Opportunities", "/opportunities"), ("Resources", "/resources")]):
                db.session.add(MenuItem(menu_id=primary.id, label=label, item_type="route", url=url, sort_order=index))
            db.session.add(MenuItem(menu_id=secondary.id, label="Newsletter", item_type="route", url="/newsletter", sort_order=0))
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="page", page_id=about_page_id, sort_order=1))
            db.session.commit()

            seed_default_navigation()

            primary_labels = [
                it.label
                for it in MenuItem.query.filter_by(menu_id=primary.id, parent_id=None).order_by(MenuItem.sort_order).all()
            ]
            secondary_labels = [
                it.label
                for it in MenuItem.query.filter_by(menu_id=secondary.id, parent_id=None)
                .order_by(MenuItem.sort_order)
                .all()
            ]

        assert primary_labels == [
            "Stories",
            "Topics",
            "People",
            "Opportunities",
            "Resources",
            "Events",
            "Community",
            "Shop",
        ]
        # "Newsletter" (not "WSF Weekly Newsletter") is exactly the stale
        # label this regression produces — healing adds the missing
        # "Partner With Us" destination without renaming the item that's
        # already there (see the "never touches an existing match" test
        # below for why that label is never silently corrected here).
        assert secondary_labels == ["Newsletter", "Partner With Us", "About"]

    def test_never_touches_an_item_that_already_points_at_a_canonical_destination(self, app):
        """A relabel is indistinguishable, from stored data alone, between
        "this came from an old/incomplete seed" and "an admin deliberately
        renamed it" — so healing must never overwrite a label on a match,
        only add what's genuinely missing (see AdminNavigation for how an
        administrator corrects a stale label instead).
        """
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="Our Newsletter", item_type="route", url="/newsletter", sort_order=0))
            db.session.commit()

            seed_default_navigation()

            items = MenuItem.query.filter_by(menu_id=secondary.id, parent_id=None).order_by(MenuItem.sort_order).all()

        assert [it.label for it in items] == ["Our Newsletter", "Partner With Us", "About"]

    def test_idempotent_second_run_is_a_no_op(self, app):
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        with app.app_context():
            seed_default_navigation()
            primary = Menu.query.filter_by(key="primary").first()
            first_ids = [
                it.id for it in MenuItem.query.filter_by(menu_id=primary.id, parent_id=None).order_by(MenuItem.sort_order).all()
            ]

            seed_default_navigation()

            second_ids = [
                it.id for it in MenuItem.query.filter_by(menu_id=primary.id, parent_id=None).order_by(MenuItem.sort_order).all()
            ]

        assert first_ids == second_ids

    def test_safe_on_a_completely_empty_database(self, app):
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        with app.app_context():
            assert Menu.query.filter_by(key="primary").first() is None
            seed_default_navigation()
            primary = Menu.query.filter_by(key="primary").first()
            labels = [
                it.label for it in MenuItem.query.filter_by(menu_id=primary.id, parent_id=None).order_by(MenuItem.sort_order).all()
            ]

        assert labels == [
            "Stories",
            "Topics",
            "People",
            "Opportunities",
            "Resources",
            "Events",
            "Community",
            "Shop",
        ]

    def test_topics_group_reflects_real_published_topics_not_hardcoded_demo_slugs(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.models.taxonomy import Topic
        from app.services.navigation import seed_default_navigation

        with app.app_context():
            topic = Topic(slug="new-topic", name="Brand New Topic", status="published")
            db.session.add(topic)
            db.session.commit()

            seed_default_navigation()

            primary = Menu.query.filter_by(key="primary").first()
            topics_group = MenuItem.query.filter_by(menu_id=primary.id, item_type="group", label="Topics").first()
            child_labels = [c.label for c in topics_group.children]

        assert child_labels == ["Brand New Topic"]

    def test_public_navigation_endpoint_reflects_the_healed_full_header(self, client, app):
        from app.services.navigation import seed_default_navigation

        with app.app_context():
            seed_default_navigation()

        resp = client.get("/api/v1/public/navigation")
        menus = resp.get_json()["data"]["menus"]
        primary_labels = [i["label"] for i in menus["primary"]["items"]]
        secondary_labels = [i["label"] for i in menus["secondary"]["items"]]

        # "Topics" is dropped entirely from the public response (per
        # serialize_public_menu_item) since no Topic has been published in
        # this test's otherwise-empty database — every other section still
        # renders regardless of that.
        assert primary_labels == ["Stories", "People", "Opportunities", "Resources", "Events", "Community", "Shop"]
        assert secondary_labels == ["WSF Weekly Newsletter", "Partner With Us"]

    def test_seed_navigation_cli_command_heals_and_persists(self, app):
        with app.app_context():
            from app.extensions import db
            from app.models.cms import Menu, MenuItem

            primary = Menu(key="primary")
            db.session.add(primary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=primary.id, label="Stories", item_type="route", url="/topics", sort_order=0))
            db.session.commit()

            runner = app.test_cli_runner()
            result = runner.invoke(args=["seed-navigation"])
            assert result.exit_code == 0

            labels = [
                it.label for it in MenuItem.query.filter_by(menu_id=primary.id, parent_id=None).order_by(MenuItem.sort_order).all()
            ]

        assert "Shop" in labels
        assert "Community" in labels


class TestEffectiveDestinationHealingAndAboutDuplicateRepair:
    """Regression coverage for the duplicate-About bug: a legacy secondary
    item (item_type="route", url="/about") and the canonical Page-backed
    About item (item_type="page", page_id=<the About page>) both resolve
    publicly to "/about", but the old healer compared identity by
    (item_type, raw field) rather than effective destination, so it never
    recognized the legacy route item as already satisfying the canonical
    About destination and added a second one on every `flask
    seed-navigation` run. See _canonical_item_key()/_existing_item_key()
    (effective-destination identity) and _dedupe_canonical_destinations()
    (the narrowly-scoped repair for a database that already has both).
    """

    def _secondary_items(self):
        from app.models.cms import Menu, MenuItem

        secondary = Menu.query.filter_by(key="secondary").first()
        return MenuItem.query.filter_by(menu_id=secondary.id, parent_id=None).order_by(MenuItem.sort_order).all()

    def test_legacy_route_about_satisfies_canonical_page_backed_about(self, app):
        """The exact reported sequence: a legacy route About item already
        exists, the system About Page exists, and healing must recognize
        the legacy item as already satisfying the canonical destination —
        never adding a second About item.
        """
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="route", url="/about", sort_order=0))
            db.session.commit()

            seed_default_navigation()

            items = self._secondary_items()
            about_items = [it for it in items if it.effective_url() == "/about"]

        assert len(about_items) == 1
        kept = about_items[0]
        assert kept.label == "About"
        assert kept.item_type == "route"
        assert kept.url == "/about"

    def test_custom_relabel_of_legacy_about_survives_healing(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="About WSF", item_type="route", url="/about", sort_order=0))
            db.session.commit()

            seed_default_navigation()

            items = self._secondary_items()
            about_items = [it for it in items if it.effective_url() == "/about"]

        assert len(about_items) == 1
        assert about_items[0].label == "About WSF"
        assert about_items[0].item_type == "route"

    def test_missing_partner_with_us_still_added_alongside_legacy_about(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="Newsletter", item_type="route", url="/newsletter", sort_order=0))
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="route", url="/about", sort_order=1))
            db.session.commit()

            seed_default_navigation()

            items = self._secondary_items()
            labels = [it.label for it in items]
            dests = [it.effective_url() for it in items]

        assert "Partner With Us" in labels
        assert dests.count("/about") == 1
        assert dests.count("/newsletter") == 1

    def test_newsletter_item_remains_intact(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="WSF Weekly Newsletter", item_type="route", url="/newsletter", sort_order=0))
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="route", url="/about", sort_order=1))
            db.session.commit()

            seed_default_navigation()

            items = self._secondary_items()

        newsletter_items = [it for it in items if it.effective_url() == "/newsletter"]
        assert len(newsletter_items) == 1
        assert newsletter_items[0].label == "WSF Weekly Newsletter"

    def test_fresh_empty_database_seeds_with_no_about_duplicate(self, app):
        from app.services.navigation import seed_default_navigation

        with app.app_context():
            seed_default_navigation()
            items = self._secondary_items()
            dests = [it.effective_url() for it in items]

        assert dests.count("/about") == 0  # no system About page seeded in this test — About is simply omitted, not duplicated
        assert "Partner With Us" in [it.label for it in items]

    def test_fresh_empty_database_with_about_page_seeds_exactly_one_about(self, app):
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            seed_default_navigation()
            items = self._secondary_items()
            dests = [it.effective_url() for it in items]

        assert dests.count("/about") == 1

    def test_already_duplicated_legacy_route_and_page_backed_about_is_repaired(self, app):
        """The literal already-broken database state this task reports:
        BOTH a legacy route item and a canonical Page-backed item already
        exist for About (e.g. from a previous buggy `flask seed-navigation`
        run). Re-running the healer must collapse this back down to a
        single About destination, preferring the item that existed first.
        """
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        about_page_id = _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="Newsletter", item_type="route", url="/newsletter", sort_order=0))
            legacy_about = MenuItem(menu_id=secondary.id, label="About", item_type="route", url="/about", sort_order=1)
            db.session.add(legacy_about)
            db.session.add(MenuItem(menu_id=secondary.id, label="Partner With Us", item_type="route", url="/partnerships", sort_order=2))
            db.session.flush()
            legacy_about_id = legacy_about.id
            # The duplicate the old (pre-fix) healer would have produced.
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="page", page_id=about_page_id, sort_order=3))
            db.session.commit()

            assert len([it for it in self._secondary_items() if it.effective_url() == "/about"]) == 2

            seed_default_navigation()

            items = self._secondary_items()
            about_items = [it for it in items if it.effective_url() == "/about"]

        assert len(about_items) == 1
        # The older item (lower id — existed first) is the one preserved.
        assert about_items[0].id == legacy_about_id
        assert about_items[0].item_type == "route"
        assert about_items[0].url == "/about"

    def test_repair_is_idempotent_on_rerun(self, app):
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        about_page_id = _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="route", url="/about", sort_order=0))
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="page", page_id=about_page_id, sort_order=1))
            db.session.commit()

            seed_default_navigation()
            first_ids = sorted(it.id for it in self._secondary_items())

            seed_default_navigation()
            second_ids = sorted(it.id for it in self._secondary_items())

        assert first_ids == second_ids

    def test_unrelated_custom_duplicate_destination_not_deleted(self, app):
        """Two admin-created custom links that happen to share a
        destination the canonical set never defines (not About, not any
        other seeded section) are not this regression and must survive
        healing untouched — the narrow repair only ever acts on a
        destination that is part of the menu's own canonical set.
        """
        from app.extensions import db
        from app.models.cms import Menu, MenuItem
        from app.services.navigation import seed_default_navigation

        _make_page(app, key="about")

        with app.app_context():
            secondary = Menu(key="secondary")
            db.session.add(secondary)
            db.session.flush()
            db.session.add(MenuItem(menu_id=secondary.id, label="About", item_type="route", url="/about", sort_order=0))
            db.session.add(MenuItem(menu_id=secondary.id, label="Custom Link A", item_type="route", url="/custom-landing", sort_order=1))
            db.session.add(MenuItem(menu_id=secondary.id, label="Custom Link B", item_type="route", url="/custom-landing", sort_order=2))
            db.session.commit()

            seed_default_navigation()

            items = self._secondary_items()
            custom_items = [it for it in items if it.effective_url() == "/custom-landing"]

        assert len(custom_items) == 2
        assert {it.label for it in custom_items} == {"Custom Link A", "Custom Link B"}


class TestFooterOwnershipBoundary:
    """Footer-owned footer_* Menu groups (footer_explore/footer_opportunity/
    footer_wsf/footer_legal, and any other footer_* key — see
    app/services/footer.py's FOOTER_MENU_KEY_PREFIX) must never be
    writable through PUT /admin/navigation by a caller who holds only
    navigation.manage/navigation.publish — that would silently bypass
    Footer CMS's own footer.manage/footer.publish gate on the exact same
    underlying Menu rows. See AdminNavigationResource.put's docstring in
    app/api/v1/admin.py for the enforcement this covers.
    """

    def test_navigation_manage_alone_cannot_mutate_a_footer_menu(self, client, navigation_manager_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "footer_legal", "heading": "Legal", "items": [{"label": "Hacked", "url": "/hacked"}]}]},
            headers=auth_headers(navigation_manager_token),
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "forbidden"

    def test_navigation_manage_alone_cannot_mutate_any_footer_prefixed_key(self, client, navigation_manager_token):
        # Not just the four seeded groups — the boundary is the footer_*
        # prefix itself, including an admin-created custom footer group.
        for key in ["footer_explore", "footer_opportunity", "footer_wsf", "footer_custom_1"]:
            resp = client.put(
                "/api/v1/admin/navigation",
                json={"menus": [{"key": key, "items": []}]},
                headers=auth_headers(navigation_manager_token),
            )
            assert resp.status_code == 403, key

    def test_rejected_request_persists_nothing_even_when_bundled_with_an_owned_menu(self, client, navigation_manager_token):
        # A payload that bundles a legitimate "primary" update together
        # with a footer_* key the caller can't touch must be rejected as a
        # whole — never a partial save that quietly applies the primary
        # half while "silently" refusing the footer half.
        resp = client.put(
            "/api/v1/admin/navigation",
            json={
                "menus": [
                    {"key": "primary", "items": [{"label": "Should Not Save", "url": "/nope"}]},
                    {"key": "footer_legal", "heading": "Legal", "items": [{"label": "Hacked", "url": "/hacked"}]},
                ]
            },
            headers=auth_headers(navigation_manager_token),
        )
        assert resp.status_code == 403

        public = client.get("/api/v1/public/navigation")
        primary_items = public.get_json()["data"]["menus"].get("primary", {}).get("items", [])
        assert [i["label"] for i in primary_items] != ["Should Not Save"]

    def test_direct_api_request_cannot_bypass_the_boundary(self, client, navigation_manager_token):
        # There is exactly one PUT endpoint for Navigation CMS — this hits
        # it directly, with a minimal payload, bypassing any frontend-only
        # restriction entirely. The server-side check is what must hold.
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "footer_explore", "items": []}]},
            headers=auth_headers(navigation_manager_token),
        )
        assert resp.status_code == 403

    def test_navigation_owned_menu_still_saves_with_navigation_manage_alone(self, client, navigation_manager_token):
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "primary", "items": [{"label": "Jobs", "url": "/jobs"}]}]},
            headers=auth_headers(navigation_manager_token),
        )
        assert resp.status_code == 200
        public = client.get("/api/v1/public/navigation")
        assert [i["label"] for i in public.get_json()["data"]["menus"]["primary"]["items"]] == ["Jobs"]

    def test_footer_manage_alone_can_still_save_footer_via_its_own_endpoint(self, client, footer_manager_token):
        resp = client.put(
            "/api/v1/admin/footer",
            json={
                "groups": [{"heading": "Legal", "visible": True, "items": [{"label": "Privacy", "itemType": "route", "url": "/privacy"}]}],
                "socialLinks": [],
                "settings": {},
            },
            headers=auth_headers(footer_manager_token),
        )
        assert resp.status_code == 200

    def test_footer_manager_cannot_reach_navigation_endpoint_at_all(self, client, footer_manager_token):
        # footer_manager holds no navigation.* permission — confirms the
        # two roles stay genuinely separate, not just footer_* key-scoped.
        resp = client.put(
            "/api/v1/admin/navigation",
            json=_basic_payload(),
            headers=auth_headers(footer_manager_token),
        )
        assert resp.status_code == 403

    def test_user_with_both_permissions_can_still_update_footer_via_navigation_endpoint(self, client, admin_token):
        # admin holds both navigation.* and footer.* — the boundary must
        # not regress a legitimately dual-permissioned caller.
        resp = client.put(
            "/api/v1/admin/navigation",
            json={"menus": [{"key": "footer_legal", "heading": "Legal", "items": [{"label": "Privacy", "url": "/privacy"}]}]},
            headers=auth_headers(admin_token),
        )
        assert resp.status_code == 200
        public = client.get("/api/v1/public/navigation")
        assert [i["label"] for i in public.get_json()["data"]["menus"]["footer_legal"]["items"]] == ["Privacy"]
