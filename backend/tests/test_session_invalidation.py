"""Security-state changes end every credential issued before them
(app/services/refresh_sessions.py invalidate_user_sessions): role changes,
deactivation, administrator password reset, two-factor enabled or reset.
Access tokens die through User.auth_version (app/auth/jwt_callbacks.py);
refresh sessions are revoked."""
import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.refresh_session import RefreshSession
from app.models.user import Role, User
from app.services import two_factor
from app.services.refresh_sessions import hash_token
from tests.conftest import CSRF_HEADERS, auth_headers, refresh_cookie_value, refresh_session

PASSWORD = "supersecret1"
EDITOR_ONLY = "/api/v1/redirects"  # @permission_required("articles.manage")


@pytest.fixture(autouse=True)
def _production_policy(app):
    app.config["TWO_FACTOR_REQUIRED_ROLES"] = ("super_admin", "editor")


@pytest.fixture()
def admin_headers(app):
    """A Super Admin actor. Its token is minted directly: the actor's own
    sign-in (and 2FA) is not what these tests exercise."""
    with app.app_context():
        admin = User(email="actor@example.invalid", first_name="A", last_name="S", is_active=True)
        admin.set_password(PASSWORD)
        admin.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.add(admin)
        db.session.commit()
        return auth_headers(create_access_token(identity=admin))


def _member(client, email):
    """Signs a new member in (no 2FA). Returns (access token, refresh cookie, user id)."""
    res = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD,
                                                     "first_name": "M", "last_name": "B"})
    assert res.status_code == 201
    body = res.get_json()["data"]
    return body["access_token"], refresh_cookie_value(client), body["user"]["id"]


def _me(client, token):
    return client.get("/api/v1/auth/me", headers=auth_headers(token))


def _session_row(app, cookie):
    with app.app_context():
        return RefreshSession.query.filter_by(token_hash=hash_token(cookie)).one()


def _set_roles(client, admin_headers, user_id, roles):
    return client.put(f"/api/v1/admin/users/{user_id}/roles", json={"role_names": roles}, headers=admin_headers)


def _login(client, email, password=PASSWORD):
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


@pytest.mark.parametrize("role", ["editor", "super_admin"])
def test_promotion_to_a_2fa_role_ends_old_credentials_and_forces_2fa(client, app, admin_headers, role):
    token, cookie, uid = _member(client, f"promoted-{role}@example.invalid")
    assert _me(client, token).status_code == 200

    assert _set_roles(client, admin_headers, uid, ["member", role]).status_code == 200

    # The old access token can't use the new privileges (or anything else).
    for path in (EDITOR_ONLY, "/api/v1/auth/me"):
        res = client.get(path, headers=auth_headers(token))
        assert res.status_code == 401 and res.get_json()["error"]["code"] == "token_revoked"
    # The old refresh session is revoked, with the reason recorded.
    assert _session_row(app, cookie).revoked_reason == "roles_changed"
    res = refresh_session(client, cookie)
    assert res.status_code == 401 and res.get_json()["error"]["code"] == "session_revoked"
    # The next password sign-in requires two-factor set-up; no session yet.
    client.delete("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    data = _login(client, f"promoted-{role}@example.invalid").get_json()["data"]
    assert data["two_factor"] == "setup" and "access_token" not in data
    assert refresh_cookie_value(client) is None


def test_any_real_role_change_ends_old_credentials(client, app, admin_headers):
    token, cookie, uid = _member(client, "rolechange@example.invalid")
    with app.app_context():
        assert Role.query.filter_by(name="author").first() is not None
        before = db.session.get(User, uid).auth_version
    assert _set_roles(client, admin_headers, uid, ["member", "author"]).status_code == 200
    assert _me(client, token).get_json()["error"]["code"] == "token_revoked"
    assert refresh_session(client, cookie).status_code == 401
    with app.app_context():
        assert db.session.get(User, uid).auth_version == before + 1


def test_demotion_also_ends_old_credentials(client, app, admin_headers):
    token, cookie, uid = _member(client, "demoted@example.invalid")
    assert _set_roles(client, admin_headers, uid, ["member", "author"]).status_code == 200
    new_token = _login(client, "demoted@example.invalid").get_json()["data"]["access_token"]
    assert _set_roles(client, admin_headers, uid, ["member"]).status_code == 200
    assert _me(client, new_token).get_json()["error"]["code"] == "token_revoked"


def test_re_saving_the_same_role_set_keeps_sessions(client, app, admin_headers):
    token, cookie, uid = _member(client, "sameroles@example.invalid")
    with app.app_context():
        before = db.session.get(User, uid).auth_version
    # Same set, different order and a duplicate: not a change.
    assert _set_roles(client, admin_headers, uid, ["member", "member"]).status_code == 200
    assert _me(client, token).status_code == 200
    assert _session_row(app, cookie).revoked_at is None
    assert refresh_session(client, cookie).status_code == 200
    with app.app_context():
        assert db.session.get(User, uid).auth_version == before


def test_deactivated_access_token_never_comes_back(client, app, admin_headers):
    token, cookie, uid = _member(client, "deactivated@example.invalid")
    status = lambda active: client.patch(f"/api/v1/admin/users/{uid}/status", json={"is_active": active},  # noqa: E731
                                         headers=admin_headers)
    assert status(False).status_code == 200
    assert _me(client, token).status_code == 401
    assert _session_row(app, cookie).revoked_reason == "deactivated"
    with app.app_context():
        version = db.session.get(User, uid).auth_version
    assert status(True).status_code == 200
    # Reactivated before the old token expired: it still doesn't work.
    res = _me(client, token)
    assert res.status_code == 401 and res.get_json()["error"]["code"] == "token_revoked"
    assert refresh_session(client, cookie).status_code == 401
    with app.app_context():
        assert db.session.get(User, uid).auth_version == version  # reactivation bumps nothing
    # A new sign-in works normally.
    res = _login(client, "deactivated@example.invalid")
    assert res.status_code == 200 and _me(client, res.get_json()["data"]["access_token"]).status_code == 200


def test_admin_password_reset_ends_old_credentials(client, app, admin_headers):
    token, cookie, uid = _member(client, "adminreset@example.invalid")
    res = client.post(f"/api/v1/admin/users/{uid}/reset-password", headers=admin_headers)
    temporary = res.get_json()["data"]["temporary_password"]
    assert _me(client, token).get_json()["error"]["code"] == "token_revoked"
    assert _session_row(app, cookie).revoked_reason == "admin_password_reset"
    assert refresh_session(client, cookie).status_code == 401
    assert _login(client, "adminreset@example.invalid").status_code == 401  # old password gone
    # The temporary password signs in, still under must-change-password.
    res = _login(client, "adminreset@example.invalid", temporary)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["user"]["must_change_password"] is True
    change = client.post("/api/v1/auth/change-password", headers=auth_headers(data["access_token"]),
                         json={"current_password": temporary, "new_password": "brandnewpass1",
                               "confirm_password": "brandnewpass1"})
    assert change.status_code == 200 and change.get_json()["data"]["must_change_password"] is False


def test_admin_two_factor_reset_ends_old_credentials(client, app, admin_headers):
    token, cookie, uid = _member(client, "tfareset@example.invalid")
    assert client.post(f"/api/v1/admin/users/{uid}/two-factor/reset", headers=admin_headers).status_code == 200
    assert _me(client, token).get_json()["error"]["code"] == "token_revoked"
    assert _session_row(app, cookie).revoked_reason == "two_factor_reset"


def _secret(app, uid):
    from app.models.two_factor import UserTwoFactor

    with app.app_context():
        row = db.session.get(UserTwoFactor, uid)
        return two_factor._decrypt(row.secret_encrypted or row.pending_secret_encrypted)


def test_member_turning_on_2fa_ends_pre_2fa_sessions_and_reissues_this_one(client, app):
    email = "optional2fa@example.invalid"
    token, cookie, uid = _member(client, email)
    # A second browser signed in before 2FA was turned on.
    other = app.test_client()
    other_res = other.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    other_token, other_cookie = other_res.get_json()["data"]["access_token"], refresh_cookie_value(other)

    client.post("/api/v1/auth/2fa/setup/start", json={}, headers=auth_headers(token))
    res = client.post("/api/v1/auth/2fa/setup/confirm", json={"code": two_factor.code_for(_secret(app, uid))},
                      headers=auth_headers(token))
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert len(data["recovery_codes"]) == 10
    new_cookie = refresh_cookie_value(client)
    assert new_cookie and new_cookie != cookie

    # Every pre-2FA credential is dead, in both browsers.
    for old in (token, other_token):
        assert _me(client, old).get_json()["error"]["code"] == "token_revoked"
    for old in (cookie, other_cookie):
        assert _session_row(app, old).revoked_reason == "two_factor_enabled"
        assert refresh_session(app.test_client(), old).status_code == 401
    # This browser carries on with a new two-factor-verified session.
    assert _me(client, data["access_token"]).status_code == 200
    row = _session_row(app, new_cookie)
    assert row.two_factor_verified is True and row.revoked_at is None
    assert refresh_session(client, new_cookie).status_code == 200
    # The other browser must sign in again, and now gets the challenge.
    again = other.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD}).get_json()["data"]
    assert again["two_factor"] == "challenge" and "access_token" not in again


def test_refresh_rejects_an_unverified_session_of_a_member_with_2fa_on(client, app):
    """Defence in depth for the refresh rule: even a session that somehow
    escaped invalidation can't mint tokens once 2FA is on."""
    token, cookie, uid = _member(client, "rule@example.invalid")
    from app.models.two_factor import UserTwoFactor
    from datetime import datetime, timezone

    with app.app_context():
        db.session.add(UserTwoFactor(user_id=uid, secret_encrypted=two_factor._encrypt(two_factor.generate_secret()),
                                     enabled_at=datetime.now(timezone.utc)))
        db.session.commit()
    res = refresh_session(client, cookie)
    assert res.status_code == 401 and res.get_json()["error"]["code"] == "session_two_factor_required"
    assert _session_row(app, cookie).revoked_reason == "two_factor_required"


def test_create_superadmin_cli_on_an_existing_account_ends_old_credentials(client, app):
    token, cookie, uid = _member(client, "cli-promoted@example.invalid")
    res = app.test_cli_runner().invoke(args=["create-superadmin", "--email", "cli-promoted@example.invalid",
                                             "--password", "anothersecret1"])
    assert "Super admin ready" in res.output
    assert _me(client, token).get_json()["error"]["code"] == "token_revoked"
    assert _session_row(app, cookie).revoked_reason == "superadmin_cli"
    assert _login(client, "cli-promoted@example.invalid", "anothersecret1").get_json()["data"]["two_factor"] == "setup"
