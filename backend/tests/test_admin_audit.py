from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import Permission, Role, User
from app.services.audit import log_action
from app.services.rbac import seed_roles_and_permissions
from tests.conftest import auth_headers


def _register_and_login(client, email="jane@example.com", password="supersecret1"):
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": "Jane", "last_name": "Doe"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.get_json()["data"]["access_token"]


def _grant_role(app, email, role_name):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        role = Role.query.filter_by(name=role_name).first()
        user.roles.append(role)
        db.session.commit()


def _super_admin_headers(client, app, email="admin@example.com"):
    token = _register_and_login(client, email=email)
    _grant_role(app, email, "super_admin")
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return auth_headers(login.get_json()["data"]["access_token"])


def _seed_entries(app, actor_email, count=3, action="article.publish", entity_type="Article"):
    with app.app_context():
        actor = User.query.filter_by(email=actor_email).first()
        for i in range(count):
            log_action(actor, action, entity_type, entity_id=100 + i, changes={"note": f"entry {i}"})


class TestAuditLogAccessControl:
    def test_requires_authentication(self, client):
        resp = client.get("/api/v1/admin/audit")
        assert resp.status_code == 401

    def test_requires_audit_view_permission(self, client, app):
        token = _register_and_login(client)
        _grant_role(app, "jane@example.com", "editor")
        login = client.post("/api/v1/auth/login", json={"email": "jane@example.com", "password": "supersecret1"})
        headers = auth_headers(login.get_json()["data"]["access_token"])
        resp = client.get("/api/v1/admin/audit", headers=headers)
        assert resp.status_code == 403

    def test_super_admin_can_view(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/admin/audit", headers=headers)
        assert resp.status_code == 200

    def test_admin_can_view(self, client, app):
        token = _register_and_login(client, email="plainadmin@example.com")
        _grant_role(app, "plainadmin@example.com", "admin")
        login = client.post("/api/v1/auth/login", json={"email": "plainadmin@example.com", "password": "supersecret1"})
        headers = auth_headers(login.get_json()["data"]["access_token"])
        resp = client.get("/api/v1/admin/audit", headers=headers)
        assert resp.status_code == 200

    def test_no_public_endpoint_exists(self, client):
        # There is deliberately no unauthenticated variant of this route.
        resp = client.get("/api/v1/audit")
        assert resp.status_code == 404

    def test_immutable_no_write_methods(self, client, app):
        headers = _super_admin_headers(client, app)
        for method in ("post", "patch", "put", "delete"):
            resp = getattr(client, method)("/api/v1/admin/audit", headers=headers, json={})
            assert resp.status_code in (404, 405)

        _seed_entries(app, "admin@example.com", count=1)
        with app.app_context():
            row_id = AuditLog.query.first().id
        resp = client.patch(f"/api/v1/admin/audit/{row_id}", headers=headers, json={})
        assert resp.status_code in (404, 405)


class TestAuditLogListing:
    def test_pagination_and_meta_shape(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=5)

        resp = client.get("/api/v1/admin/audit?per_page=2", headers=headers)
        assert resp.status_code == 200
        body = resp.get_json()
        assert len(body["data"]) == 2
        assert body["meta"]["page"] == 1
        assert body["meta"]["per_page"] == 2
        assert body["meta"]["total"] >= 5

    def test_default_ordering_is_newest_first(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=3, action="article.update")

        resp = client.get("/api/v1/admin/audit", headers=headers)
        rows = resp.get_json()["data"]
        timestamps = [r["createdAt"] for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_sort_oldest_reverses_order(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=3, action="article.update")

        resp = client.get("/api/v1/admin/audit?sort=oldest", headers=headers)
        rows = resp.get_json()["data"]
        timestamps = [r["createdAt"] for r in rows]
        assert timestamps == sorted(timestamps)

    def test_response_shape_matches_spec(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=1, action="article.publish", entity_type="Article")

        resp = client.get("/api/v1/admin/audit?action=article.publish", headers=headers)
        row = resp.get_json()["data"][0]
        assert set(["id", "createdAt", "actor", "action", "actionLabel", "category", "entity", "metadata"]) <= set(row)
        assert set(["id", "name", "email"]) <= set(row["actor"])
        assert set(["type", "id", "label"]) <= set(row["entity"])
        assert row["action"] == "article.publish"
        assert row["actionLabel"] == "Published article"
        assert row["category"] == "content"

    def test_filter_by_action(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=2, action="article.publish")
        _seed_entries(app, "admin@example.com", count=2, action="article.update")

        resp = client.get("/api/v1/admin/audit?action=article.update", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) == 2
        assert all(r["action"] == "article.update" for r in rows)

    def test_filter_by_entity_type(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=2, action="settings.update", entity_type="SiteSetting")

        resp = client.get("/api/v1/admin/audit?entityType=SiteSetting", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) == 2
        assert all(r["entity"]["type"] == "SiteSetting" for r in rows)

    def test_filter_by_entity_id(self, client, app):
        headers = _super_admin_headers(client, app)
        with app.app_context():
            actor = User.query.filter_by(email="admin@example.com").first()
            log_action(actor, "article.update", "Article", entity_id=555, changes=None)
            log_action(actor, "article.update", "Article", entity_id=556, changes=None)

        resp = client.get("/api/v1/admin/audit?entityType=Article&entityId=555", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) == 1
        assert rows[0]["entity"]["id"] == "555"

    def test_filter_by_actor(self, client, app):
        headers = _super_admin_headers(client, app)
        _register_and_login(client, email="second@example.com")
        _seed_entries(app, "admin@example.com", count=2, action="article.update")
        _seed_entries(app, "second@example.com", count=1, action="article.update")

        with app.app_context():
            actor_id = User.query.filter_by(email="second@example.com").first().id

        resp = client.get(f"/api/v1/admin/audit?actor={actor_id}&action=article.update", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) == 1
        assert rows[0]["actor"]["id"] == actor_id

    def test_filter_by_category(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=2, action="article.publish", entity_type="Article")
        _seed_entries(app, "admin@example.com", count=1, action="settings.update", entity_type="SiteSetting")

        resp = client.get("/api/v1/admin/audit?category=content", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) >= 2
        assert all(r["category"] == "content" for r in rows)

    def test_invalid_category_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/admin/audit?category=not_a_real_category", headers=headers)
        assert resp.status_code == 422

    def test_filter_by_date_range(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=1, action="article.update")

        far_future = "2099-01-01"
        resp = client.get(f"/api/v1/admin/audit?dateFrom={far_future}", headers=headers)
        assert resp.get_json()["data"] == []

        far_past = "1999-01-01"
        resp2 = client.get(f"/api/v1/admin/audit?dateFrom={far_past}&dateTo={far_future}", headers=headers)
        assert len(resp2.get_json()["data"]) >= 1

    def test_invalid_date_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/admin/audit?dateFrom=not-a-date", headers=headers)
        assert resp.status_code == 422

    def test_search_matches_actor_email(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=1, action="article.update")

        resp = client.get("/api/v1/admin/audit?q=admin@example.com", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) >= 1

    def test_search_matches_action(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=1, action="article.publish")

        resp = client.get("/api/v1/admin/audit?q=publish", headers=headers)
        rows = resp.get_json()["data"]
        assert any(r["action"] == "article.publish" for r in rows)


class TestAuditLogSensitiveDataHandling:
    def test_password_reset_never_exposes_password(self, client, app):
        headers = _super_admin_headers(client, app)
        with app.app_context():
            actor = User.query.filter_by(email="admin@example.com").first()
            log_action(
                actor,
                "user.password_reset",
                "User",
                entity_id=999,
                changes={"temporary_password": "supersecretvalue123"},
            )

        resp = client.get("/api/v1/admin/audit?action=user.password_reset", headers=headers)
        raw = resp.get_data(as_text=True)
        assert "supersecretvalue123" not in raw
        assert "[redacted]" in raw

    def test_nested_sensitive_key_redacted(self, client, app):
        headers = _super_admin_headers(client, app)
        with app.app_context():
            actor = User.query.filter_by(email="admin@example.com").first()
            log_action(
                actor,
                "article.update",
                "Article",
                entity_id=321,
                changes={"credentials": {"api_key": "abc123", "note": "safe value"}},
            )

        resp = client.get("/api/v1/admin/audit?entityType=Article&entityId=321", headers=headers)
        row = resp.get_json()["data"][0]
        assert row["metadata"]["credentials"]["api_key"] == "[redacted]"
        assert row["metadata"]["credentials"]["note"] == "safe value"

    def test_no_password_hash_ever_serialized(self, client, app):
        headers = _super_admin_headers(client, app)
        _seed_entries(app, "admin@example.com", count=1)
        resp = client.get("/api/v1/admin/audit", headers=headers)
        raw = resp.get_data(as_text=True)
        assert "password_hash" not in raw
        assert "$2b$" not in raw


class TestAuditLogSurvivesDeletion:
    def test_deactivated_actor_shows_as_readable_name(self, client, app):
        headers = _super_admin_headers(client, app)
        _register_and_login(client, email="soontodeactivate@example.com")
        _grant_role(app, "soontodeactivate@example.com", "editor")
        _seed_entries(app, "soontodeactivate@example.com", count=1, action="article.update")

        with app.app_context():
            target = User.query.filter_by(email="soontodeactivate@example.com").first()
            target.is_active = False
            db.session.commit()

        resp = client.get("/api/v1/admin/audit?action=article.update", headers=headers)
        rows = resp.get_json()["data"]
        assert len(rows) >= 1
        assert rows[0]["actor"]["name"]

    def test_system_actor_shows_as_system(self, client, app):
        headers = _super_admin_headers(client, app)
        with app.app_context():
            log_action(None, "newsletter_subscribers_exported", "NewsletterSubscriber", entity_id=None, changes={"count": 5})

        resp = client.get("/api/v1/admin/audit?action=newsletter_subscribers_exported", headers=headers)
        rows = resp.get_json()["data"]
        assert rows[0]["actor"]["name"] == "System"
        assert rows[0]["actor"]["id"] is None

    def test_deleted_target_falls_back_to_generic_label(self, client, app):
        headers = _super_admin_headers(client, app)
        with app.app_context():
            actor = User.query.filter_by(email="admin@example.com").first()
            log_action(actor, "article.update", "Article", entity_id=9999999, changes=None)

        resp = client.get("/api/v1/admin/audit?entityType=Article&entityId=9999999", headers=headers)
        row = resp.get_json()["data"][0]
        assert row["entity"]["label"] == "Article #9999999"


class TestAuditLogSecurityEventCoverage:
    def test_role_change_is_captured(self, client, app):
        headers = _super_admin_headers(client, app)
        create = client.post(
            "/api/v1/admin/users",
            json={"email": "roleaudit@example.com", "first_name": "R", "last_name": "A", "role_names": ["editor"]},
            headers=headers,
        )
        user_id = create.get_json()["data"]["id"]
        client.put(f"/api/v1/admin/users/{user_id}/roles", json={"role_names": ["moderator"]}, headers=headers)

        resp = client.get("/api/v1/admin/audit?action=user.roles_update", headers=headers)
        rows = resp.get_json()["data"]
        assert any(r["entity"]["id"] == str(user_id) for r in rows)

    def test_deactivation_is_captured(self, client, app):
        headers = _super_admin_headers(client, app)
        create = client.post(
            "/api/v1/admin/users",
            json={"email": "deactaudit@example.com", "first_name": "D", "last_name": "A", "role_names": ["editor"]},
            headers=headers,
        )
        user_id = create.get_json()["data"]["id"]
        client.patch(f"/api/v1/admin/users/{user_id}/status", json={"is_active": False}, headers=headers)

        resp = client.get("/api/v1/admin/audit?action=user.deactivate", headers=headers)
        rows = resp.get_json()["data"]
        assert any(r["entity"]["id"] == str(user_id) for r in rows)

    def test_site_settings_update_is_captured(self, client, app):
        headers = _super_admin_headers(client, app)
        client.put(
            "/api/v1/admin/settings",
            json={"settings": {"site_identity": {"siteName": "WSF Updated"}}},
            headers=headers,
        )

        resp = client.get("/api/v1/admin/audit?action=settings.update", headers=headers)
        assert len(resp.get_json()["data"]) >= 1


class TestSeedIdempotency:
    def test_audit_view_permission_seeded_idempotently(self, app):
        with app.app_context():
            before_roles = Role.query.count()
            before_permissions = Permission.query.count()
            seed_roles_and_permissions()
            seed_roles_and_permissions()
            assert Role.query.count() == before_roles
            assert Permission.query.count() == before_permissions
            assert Permission.query.filter_by(name="audit.view").first() is not None

    def test_admin_role_has_audit_view(self, app):
        with app.app_context():
            admin_role = Role.query.filter_by(name="admin").first()
            perm_names = {p.name for p in admin_role.permissions}
            assert "audit.view" in perm_names

    def test_writer_role_lacks_audit_view(self, app):
        with app.app_context():
            role = Role.query.filter_by(name="editor").first()
            if role is not None:
                perm_names = {p.name for p in role.permissions}
                assert "audit.view" not in perm_names
