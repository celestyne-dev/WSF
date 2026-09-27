from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import Permission, Role, User
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


def _create_staff(client, headers, email="staff@example.com", role_names=None, is_active=True):
    return client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "first_name": "Staff",
            "last_name": "Member",
            "role_names": role_names or ["editor"],
            "is_active": is_active,
        },
        headers=headers,
    )


class TestUserListRequiresAuth:
    def test_list_requires_authentication(self, client):
        resp = client.get("/api/v1/admin/users")
        assert resp.status_code == 401

    def test_list_requires_permission(self, client, app):
        token = _register_and_login(client)
        resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_super_admin_can_list(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/admin/users", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["meta"]["total"] >= 1

    def test_detail_requires_permission(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers)
        user_id = create.get_json()["data"]["id"]

        token = _register_and_login(client, email="nobody@example.com")
        resp = client.get(f"/api/v1/admin/users/{user_id}", headers=auth_headers(token))
        assert resp.status_code == 403


class TestUserCreation:
    def test_super_admin_can_create_staff_user(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = _create_staff(client, headers, email="new.editor@example.com", role_names=["editor"])
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert body["email"] == "new.editor@example.com"
        assert "temporary_password" in body
        assert len(body["temporary_password"]) >= 12
        assert "password_hash" not in body
        assert [r["name"] for r in body["roles"]] == ["editor"]

    def test_created_password_actually_works(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="pwtest@example.com")
        temp_password = create.get_json()["data"]["temporary_password"]

        login = client.post("/api/v1/auth/login", json={"email": "pwtest@example.com", "password": temp_password})
        assert login.status_code == 200

    def test_password_hash_never_serialized(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = _create_staff(client, headers, email="hashcheck@example.com")
        raw = resp.get_data(as_text=True)
        assert "password_hash" not in raw
        assert "$2b$" not in raw  # bcrypt hash prefix must never leak

    def test_duplicate_email_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        _create_staff(client, headers, email="dupe@example.com")
        resp = _create_staff(client, headers, email="dupe@example.com")
        assert resp.status_code == 409

    def test_duplicate_email_case_insensitive(self, client, app):
        headers = _super_admin_headers(client, app)
        _create_staff(client, headers, email="Case@Example.com")
        resp = _create_staff(client, headers, email="case@example.com")
        assert resp.status_code == 409

    def test_email_normalized_to_lowercase(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = _create_staff(client, headers, email="MixedCase@Example.com")
        assert resp.get_json()["data"]["email"] == "mixedcase@example.com"

    def test_unknown_role_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = _create_staff(client, headers, email="badrole@example.com", role_names=["not_a_real_role"])
        assert resp.status_code == 422

    def test_creation_requires_users_manage(self, client, app):
        # "editor" carries no users.manage — a fresh editor-only account
        # must not be able to create staff users.
        token = _register_and_login(client, email="editor2@example.com")
        _grant_role(app, "editor2@example.com", "editor")
        login = client.post("/api/v1/auth/login", json={"email": "editor2@example.com", "password": "supersecret1"})
        editor_headers = auth_headers(login.get_json()["data"]["access_token"])
        resp = _create_staff(client, editor_headers, email="blocked@example.com")
        assert resp.status_code == 403

    def test_only_super_admin_can_grant_super_admin_at_creation(self, client, app):
        headers = _super_admin_headers(client, app, email="root1@example.com")
        # A plain admin (users.manage, roles.manage, but not super_admin)
        token = _register_and_login(client, email="plainadmin@example.com")
        _grant_role(app, "plainadmin@example.com", "admin")
        login = client.post("/api/v1/auth/login", json={"email": "plainadmin@example.com", "password": "supersecret1"})
        admin_headers = auth_headers(login.get_json()["data"]["access_token"])

        resp = _create_staff(client, admin_headers, email="escalated@example.com", role_names=["super_admin"])
        assert resp.status_code == 403

        ok = _create_staff(client, headers, email="escalated2@example.com", role_names=["super_admin"])
        assert ok.status_code == 201


class TestUserUpdate:
    def test_update_identity(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="rename@example.com")
        user_id = create.get_json()["data"]["id"]

        resp = client.patch(f"/api/v1/admin/users/{user_id}", json={"first_name": "Renamed"}, headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["first_name"] == "Renamed"

    def test_update_email_duplicate_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        _create_staff(client, headers, email="taken@example.com")
        create2 = _create_staff(client, headers, email="movable@example.com")
        user_id = create2.get_json()["data"]["id"]

        resp = client.patch(f"/api/v1/admin/users/{user_id}", json={"email": "taken@example.com"}, headers=headers)
        assert resp.status_code == 409

    def test_update_requires_users_manage(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="target@example.com")
        user_id = create.get_json()["data"]["id"]

        token = _register_and_login(client, email="nobody2@example.com")
        resp = client.patch(f"/api/v1/admin/users/{user_id}", json={"first_name": "X"}, headers=auth_headers(token))
        assert resp.status_code == 403


class TestActivationDeactivation:
    def test_deactivate_and_reactivate(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="togglable@example.com")
        user_id = create.get_json()["data"]["id"]

        deactivate = client.patch(f"/api/v1/admin/users/{user_id}/status", json={"is_active": False}, headers=headers)
        assert deactivate.status_code == 200
        assert deactivate.get_json()["data"]["is_active"] is False

        reactivate = client.patch(f"/api/v1/admin/users/{user_id}/status", json={"is_active": True}, headers=headers)
        assert reactivate.status_code == 200
        assert reactivate.get_json()["data"]["is_active"] is True

    def test_cannot_deactivate_own_account(self, client, app):
        headers = _super_admin_headers(client, app, email="self1@example.com")
        with app.app_context():
            me = User.query.filter_by(email="self1@example.com").first()
            my_id = me.id

        resp = client.patch(f"/api/v1/admin/users/{my_id}/status", json={"is_active": False}, headers=headers)
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "self_action_forbidden"

    def test_deactivated_user_cannot_use_still_valid_token(self, client, app):
        """The critical section-9/10/25 behavior: a JWT issued before
        deactivation, still cryptographically valid and unexpired, must
        stop working on the very next protected request once is_active
        flips to False — no blacklist entry required, since
        _require_active_user() re-reads the account fresh every request.
        """
        token = _register_and_login(client, email="soontodeactivate@example.com")
        _grant_role(app, "soontodeactivate@example.com", "editor")

        me = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert me.status_code == 200

        admin_headers = _super_admin_headers(client, app, email="deactivator@example.com")
        with app.app_context():
            target = User.query.filter_by(email="soontodeactivate@example.com").first()
            target_id = target.id
        client.patch(f"/api/v1/admin/users/{target_id}/status", json={"is_active": False}, headers=admin_headers)

        me_again = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert me_again.status_code == 403

    def test_deactivated_user_cannot_refresh(self, client, app):
        client.post(
            "/api/v1/auth/register",
            json={"email": "refreshvictim@example.com", "password": "supersecret1", "first_name": "R", "last_name": "V"},
        )
        login = client.post("/api/v1/auth/login", json={"email": "refreshvictim@example.com", "password": "supersecret1"})
        refresh_token = login.get_json()["data"]["refresh_token"]

        admin_headers = _super_admin_headers(client, app, email="deactivator2@example.com")
        with app.app_context():
            target = User.query.filter_by(email="refreshvictim@example.com").first()
            target_id = target.id
        client.patch(f"/api/v1/admin/users/{target_id}/status", json={"is_active": False}, headers=admin_headers)

        resp = client.post("/api/v1/auth/refresh", headers=auth_headers(refresh_token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "account_inactive"


class TestLastSuperAdminProtection:
    def test_cannot_deactivate_last_active_super_admin(self, client, app):
        # A second super_admin (different from `actor`) is needed since an
        # admin can never target their own account at all (self-action is
        # blocked first) — this proves the LAST-super-admin rule fires for
        # a genuine cross-admin attempt, not just the self-block.
        actor_headers = _super_admin_headers(client, app, email="actor@example.com")
        target_headers = _super_admin_headers(client, app, email="lonely_root@example.com")
        with app.app_context():
            target = User.query.filter_by(email="lonely_root@example.com").first()
            # Demote the actor to plain "admin" (still has users.manage, so
            # the request reaches the last-super-admin check rather than
            # being turned away earlier by the permission decorator) so
            # `lonely_root` becomes the ONLY active super_admin left.
            actor = User.query.filter_by(email="actor@example.com").first()
            actor.roles = [r for r in actor.roles if r.name != "super_admin"]
            admin_role = Role.query.filter_by(name="admin").first()
            actor.roles.append(admin_role)
            db.session.commit()
            target_id = target.id

        # Re-login the actor so their token carries no stale assumptions
        # (not required for authorization, since checks are DB-live, but
        # keeps this test's headers accurate to the new state).
        login = client.post("/api/v1/auth/login", json={"email": "actor@example.com", "password": "supersecret1"})
        actor_headers = auth_headers(login.get_json()["data"]["access_token"])

        resp = client.patch(f"/api/v1/admin/users/{target_id}/status", json={"is_active": False}, headers=actor_headers)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "last_super_admin"

    def test_can_deactivate_super_admin_when_another_remains(self, client, app):
        actor_headers = _super_admin_headers(client, app, email="actor2@example.com")
        _super_admin_headers(client, app, email="second_root@example.com")
        with app.app_context():
            target = User.query.filter_by(email="second_root@example.com").first()
            target_id = target.id

        resp = client.patch(f"/api/v1/admin/users/{target_id}/status", json={"is_active": False}, headers=actor_headers)
        assert resp.status_code == 200

    def test_cannot_remove_super_admin_role_from_last_active_super_admin(self, client, app):
        actor_headers = _super_admin_headers(client, app, email="actor3@example.com")
        target_headers = _super_admin_headers(client, app, email="only_root@example.com")
        with app.app_context():
            # Demote actor3 to plain "admin" (keeps roles.manage, so the
            # request reaches the last-super-admin check) so only_root
            # becomes the ONLY active super_admin left.
            actor = User.query.filter_by(email="actor3@example.com").first()
            actor.roles = [r for r in actor.roles if r.name != "super_admin"]
            admin_role = Role.query.filter_by(name="admin").first()
            actor.roles.append(admin_role)
            db.session.commit()
            target = User.query.filter_by(email="only_root@example.com").first()
            target_id = target.id

        login = client.post("/api/v1/auth/login", json={"email": "actor3@example.com", "password": "supersecret1"})
        actor_headers = auth_headers(login.get_json()["data"]["access_token"])

        resp = client.put(f"/api/v1/admin/users/{target_id}/roles", json={"role_names": ["editor"]}, headers=actor_headers)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "last_super_admin"


class TestSelfLockoutProtection:
    def test_cannot_change_own_roles(self, client, app):
        headers = _super_admin_headers(client, app, email="selfrole@example.com")
        with app.app_context():
            me = User.query.filter_by(email="selfrole@example.com").first()
            my_id = me.id

        resp = client.put(f"/api/v1/admin/users/{my_id}/roles", json={"role_names": ["editor"]}, headers=headers)
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "self_action_forbidden"


class TestRoleAssignment:
    def test_assign_and_replace_roles(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="rolechange@example.com", role_names=["editor"])
        user_id = create.get_json()["data"]["id"]

        resp = client.put(
            f"/api/v1/admin/users/{user_id}/roles", json={"role_names": ["moderator", "analyst"]}, headers=headers
        )
        assert resp.status_code == 200
        role_names = sorted(r["name"] for r in resp.get_json()["data"]["roles"])
        assert role_names == ["analyst", "moderator"]

    def test_invalid_role_name_rejected(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="badrole2@example.com")
        user_id = create.get_json()["data"]["id"]

        resp = client.put(f"/api/v1/admin/users/{user_id}/roles", json={"role_names": ["ceo_of_everything"]}, headers=headers)
        assert resp.status_code == 422

    def test_role_assignment_requires_roles_manage_permission(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="targetforrole@example.com")
        user_id = create.get_json()["data"]["id"]

        token = _register_and_login(client, email="norole@example.com")
        resp = client.put(f"/api/v1/admin/users/{user_id}/roles", json={"role_names": ["editor"]}, headers=auth_headers(token))
        assert resp.status_code == 403

    def test_only_super_admin_can_grant_super_admin_via_role_update(self, client, app):
        _super_admin_headers(client, app, email="root_grantor@example.com")
        token = _register_and_login(client, email="plainadmin2@example.com")
        _grant_role(app, "plainadmin2@example.com", "admin")
        login = client.post("/api/v1/auth/login", json={"email": "plainadmin2@example.com", "password": "supersecret1"})
        admin_headers = auth_headers(login.get_json()["data"]["access_token"])

        create = _create_staff(client, admin_headers, email="promoteme@example.com", role_names=["editor"])
        user_id = create.get_json()["data"]["id"]

        resp = client.put(f"/api/v1/admin/users/{user_id}/roles", json={"role_names": ["super_admin"]}, headers=admin_headers)
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "super_admin_required"


class TestStaleRoleToken:
    def test_role_removed_after_login_immediately_denies_privileged_action(self, client, app):
        """The stale-role-token behavior spec section 23/24 requires:
        permission checks must re-resolve the CURRENT DB role set on every
        request, never trust the JWT's own `roles` claim (which is only
        informational — see app/auth/jwt_callbacks.py additional_claims_loader).
        """
        actor_headers = _super_admin_headers(client, app, email="roleremover@example.com")
        token = _register_and_login(client, email="willloserole@example.com")
        _grant_role(app, "willloserole@example.com", "admin")

        login = client.post("/api/v1/auth/login", json={"email": "willloserole@example.com", "password": "supersecret1"})
        privileged_token = login.get_json()["data"]["access_token"]

        still_privileged = client.get("/api/v1/admin/users", headers=auth_headers(privileged_token))
        assert still_privileged.status_code == 200

        with app.app_context():
            target = User.query.filter_by(email="willloserole@example.com").first()
            target_id = target.id
        client.put(f"/api/v1/admin/users/{target_id}/roles", json={"role_names": []}, headers=actor_headers)

        # Same still-unexpired, still-cryptographically-valid access token —
        # only the DB role set changed. Must now be denied.
        now_denied = client.get("/api/v1/admin/users", headers=auth_headers(privileged_token))
        assert now_denied.status_code == 403


class TestPasswordReset:
    def test_admin_can_reset_password(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="forgetful@example.com")
        user_id = create.get_json()["data"]["id"]

        resp = client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=headers)
        assert resp.status_code == 200
        new_password = resp.get_json()["data"]["temporary_password"]
        assert new_password

        login = client.post("/api/v1/auth/login", json={"email": "forgetful@example.com", "password": new_password})
        assert login.status_code == 200

    def test_password_reset_requires_users_manage(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="notyours@example.com")
        user_id = create.get_json()["data"]["id"]

        token = _register_and_login(client, email="rando@example.com")
        resp = client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_password_reset_not_audited_with_password_value(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="auditcheck@example.com")
        user_id = create.get_json()["data"]["id"]
        new_password = client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=headers).get_json()["data"][
            "temporary_password"
        ]

        with app.app_context():
            entries = AuditLog.query.filter_by(action="user.password_reset").all()
            assert len(entries) == 1
            assert new_password not in str(entries[0].changes)


class TestRolesAndPermissionsApi:
    def test_list_roles_includes_user_counts(self, client, app):
        headers = _super_admin_headers(client, app)
        _create_staff(client, headers, email="counted@example.com", role_names=["editor"])

        resp = client.get("/api/v1/admin/roles", headers=headers)
        assert resp.status_code == 200
        roles = {r["name"]: r for r in resp.get_json()["data"]}
        assert roles["editor"]["user_count"] >= 1
        assert "permissions" in roles["editor"]

    def test_role_detail(self, client, app):
        headers = _super_admin_headers(client, app)
        with app.app_context():
            role = Role.query.filter_by(name="editor").first()
            role_id = role.id

        resp = client.get(f"/api/v1/admin/roles/{role_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.get_json()["data"]["name"] == "editor"

    def test_permissions_list_is_read_only_reference(self, client, app):
        headers = _super_admin_headers(client, app)
        resp = client.get("/api/v1/admin/permissions", headers=headers)
        assert resp.status_code == 200
        names = [p["name"] for p in resp.get_json()["data"]]
        assert "users.manage" in names
        assert "roles.manage" in names
        assert "users.view" in names

    def test_roles_and_permissions_require_view_permission(self, client, app):
        token = _register_and_login(client, email="noview@example.com")
        assert client.get("/api/v1/admin/roles", headers=auth_headers(token)).status_code == 403
        assert client.get("/api/v1/admin/permissions", headers=auth_headers(token)).status_code == 403


class TestAuditLogging:
    def test_user_creation_is_audited(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="audited@example.com")
        user_id = create.get_json()["data"]["id"]

        with app.app_context():
            entry = AuditLog.query.filter_by(action="user.create", entity_id=str(user_id)).first()
            assert entry is not None
            assert "audited@example.com" in str(entry.changes)

    def test_role_change_is_audited_with_actor_and_target(self, client, app):
        headers = _super_admin_headers(client, app, email="auditor@example.com")
        create = _create_staff(client, headers, email="roleaudited@example.com", role_names=["editor"])
        user_id = create.get_json()["data"]["id"]
        client.put(f"/api/v1/admin/users/{user_id}/roles", json={"role_names": ["moderator"]}, headers=headers)

        with app.app_context():
            actor = User.query.filter_by(email="auditor@example.com").first()
            entry = AuditLog.query.filter_by(action="user.roles_update", entity_id=str(user_id)).first()
            assert entry is not None
            assert entry.user_id == actor.id
            assert entry.entity_id == str(user_id)


class TestSeedIdempotency:
    def test_seed_roles_and_permissions_is_idempotent(self, app):
        from app.services.rbac import seed_roles_and_permissions

        with app.app_context():
            before_roles = Role.query.count()
            before_permissions = Permission.query.count()
            seed_roles_and_permissions()
            seed_roles_and_permissions()
            assert Role.query.count() == before_roles
            assert Permission.query.count() == before_permissions

    def test_reseeding_does_not_touch_user_role_assignments(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="reseedcheck@example.com", role_names=["moderator"])
        user_id = create.get_json()["data"]["id"]

        from app.services.rbac import seed_roles_and_permissions

        with app.app_context():
            seed_roles_and_permissions()

        detail = client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
        assert [r["name"] for r in detail.get_json()["data"]["roles"]] == ["moderator"]
