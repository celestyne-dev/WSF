from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import Role, User
from tests.conftest import auth_headers

REGISTER_PAYLOAD = {
    "email": "selfreg@example.com",
    "password": "supersecret1",
    "first_name": "Self",
    "last_name": "Reg",
}


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


def _create_staff(client, headers, email="staff@example.com", role_names=None):
    return client.post(
        "/api/v1/admin/users",
        json={
            "email": email,
            "first_name": "Staff",
            "last_name": "Member",
            "role_names": role_names or ["community_manager"],
            "is_active": True,
        },
        headers=headers,
    )


def _create_staff_and_login(client, app, email, role_names=None):
    """Mirrors the real flow: admin creates (or resets) the account, admin's
    own request never sees the password again, and the new staff member's
    first login is with that one-time temporary password.
    """
    headers = _super_admin_headers(client, app, email=f"owner_{email}")
    create = _create_staff(client, headers, email=email, role_names=role_names)
    temporary_password = create.get_json()["data"]["temporary_password"]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": temporary_password})
    return login.get_json()["data"]["access_token"], temporary_password


class TestMustChangePasswordFlag:
    def test_public_registration_does_not_require_password_change(self, client):
        resp = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
        assert resp.status_code == 201
        assert resp.get_json()["data"]["user"]["must_change_password"] is False

    def test_new_staff_account_requires_password_change(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="newstaff@example.com")
        assert create.status_code == 201
        assert create.get_json()["data"]["must_change_password"] is True

    def test_admin_reset_sets_must_change_password_true(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="resetme@example.com")
        user_id = create.get_json()["data"]["id"]

        # Simulate a staff member who already completed her own change —
        # the reset below must flip the flag back on regardless.
        with app.app_context():
            user = User.query.filter_by(email="resetme@example.com").first()
            user.must_change_password = False
            db.session.commit()

        resp = client.post(f"/api/v1/admin/users/{user_id}/reset-password", headers=headers)
        assert resp.status_code == 200

        detail = client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
        assert detail.get_json()["data"]["must_change_password"] is True

    def test_login_with_temporary_password_reports_required_change(self, client, app):
        headers = _super_admin_headers(client, app)
        create = _create_staff(client, headers, email="tempuser@example.com")
        temporary_password = create.get_json()["data"]["temporary_password"]

        login = client.post(
            "/api/v1/auth/login", json={"email": "tempuser@example.com", "password": temporary_password}
        )
        assert login.status_code == 200
        assert login.get_json()["data"]["user"]["must_change_password"] is True


class TestForcedChangeEnforcement:
    def test_forced_change_user_cannot_access_protected_endpoint(self, client, app):
        token, _ = _create_staff_and_login(client, app, "locked@example.com", role_names=["community_manager"])

        resp = client.get("/api/v1/community/members", headers=auth_headers(token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "password_change_required"

    def test_forced_change_user_can_call_me(self, client, app):
        token, _ = _create_staff_and_login(client, app, "canme@example.com")

        resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["must_change_password"] is True

    def test_forced_change_user_can_refresh(self, client, app):
        headers = _super_admin_headers(client, app, email="owner_canrefresh@example.com")
        create = _create_staff(client, headers, email="canrefresh@example.com")
        temporary_password = create.get_json()["data"]["temporary_password"]
        login = client.post(
            "/api/v1/auth/login", json={"email": "canrefresh@example.com", "password": temporary_password}
        )
        refresh_token = login.get_json()["data"]["refresh_token"]

        resp = client.post("/api/v1/auth/refresh", headers=auth_headers(refresh_token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["access_token"]


class TestChangePasswordEndpoint:
    def test_wrong_current_password_rejected(self, client, app):
        token, _ = _create_staff_and_login(client, app, "wrongcur@example.com")
        resp = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "totally-wrong", "new_password": "newsecret1", "confirm_password": "newsecret1"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "invalid_credentials"

    def test_new_password_mismatch_rejected(self, client, app):
        token, temporary_password = _create_staff_and_login(client, app, "mismatch@example.com")
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temporary_password,
                "new_password": "newsecret1",
                "confirm_password": "different1",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "password_mismatch"

    def test_too_short_new_password_rejected(self, client, app):
        token, temporary_password = _create_staff_and_login(client, app, "tooshort@example.com")
        resp = client.post(
            "/api/v1/auth/change-password",
            json={"current_password": temporary_password, "new_password": "short", "confirm_password": "short"},
            headers=auth_headers(token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "validation_error"

    def test_same_current_and_new_password_rejected(self, client, app):
        token, temporary_password = _create_staff_and_login(client, app, "samepw@example.com")
        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temporary_password,
                "new_password": temporary_password,
                "confirm_password": temporary_password,
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "password_unchanged"

    def test_inactive_user_cannot_change_password(self, client, app):
        token, temporary_password = _create_staff_and_login(client, app, "inactiveflow@example.com")
        with app.app_context():
            user = User.query.filter_by(email="inactiveflow@example.com").first()
            user.is_active = False
            db.session.commit()

        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temporary_password,
                "new_password": "mynewsecret1",
                "confirm_password": "mynewsecret1",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "forbidden"

    def test_temporary_password_never_in_audit_metadata(self, client, app):
        token, temporary_password = _create_staff_and_login(client, app, "auditcheck2@example.com")
        client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temporary_password,
                "new_password": "mynewsecret1",
                "confirm_password": "mynewsecret1",
            },
            headers=auth_headers(token),
        )
        with app.app_context():
            entries = AuditLog.query.filter_by(action="user.password_change").all()
            assert len(entries) == 1
            assert temporary_password not in str(entries[0].changes)
            assert "mynewsecret1" not in str(entries[0].changes)

    def test_successful_password_change_full_flow(self, client, app):
        token, temporary_password = _create_staff_and_login(
            client, app, "fullflow@example.com", role_names=["community_manager"]
        )

        with app.app_context():
            old_hash = User.query.filter_by(email="fullflow@example.com").first().password_hash

        resp = client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": temporary_password,
                "new_password": "mynewsecret1",
                "confirm_password": "mynewsecret1",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["must_change_password"] is False

        with app.app_context():
            user = User.query.filter_by(email="fullflow@example.com").first()
            assert user.password_hash != old_hash
            assert user.must_change_password is False

        # Old temporary password no longer works.
        old_login = client.post(
            "/api/v1/auth/login", json={"email": "fullflow@example.com", "password": temporary_password}
        )
        assert old_login.status_code == 401

        # New password works, and no longer reports a required change.
        new_login = client.post(
            "/api/v1/auth/login", json={"email": "fullflow@example.com", "password": "mynewsecret1"}
        )
        assert new_login.status_code == 200
        assert new_login.get_json()["data"]["user"]["must_change_password"] is False

        # Same still-unexpired access token issued back at the forced-change
        # login — no re-login required — now reaches the protected CMS
        # endpoint her role (community_manager) grants.
        resp2 = client.get("/api/v1/community/members", headers=auth_headers(token))
        assert resp2.status_code == 200
