"""TOTP two-factor authentication (app/services/two_factor.py,
app/api/v1/two_factor.py, the 2FA gate in app/api/v1/auth.py)."""
import pytest

from app.extensions import db
from app.models.audit import AuditLog
from app.models.refresh_session import RefreshSession
from app.models.two_factor import TwoFactorRecoveryCode, UserTwoFactor
from app.models.user import Role, User
from app.services import two_factor
from tests.conftest import CSRF_HEADERS, auth_headers, refresh_cookie_value, refresh_session

PASSWORD = "supersecret1"


@pytest.fixture(autouse=True)
def _production_policy(app):
    # Production default (config.Config); TestingConfig switches it off for
    # the rest of the suite's staff fixtures.
    from config import Config

    app.config["TWO_FACTOR_REQUIRED_ROLES"] = Config.TWO_FACTOR_REQUIRED_ROLES


def _user(client, app, email, role=None):
    client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD, "first_name": "T", "last_name": "F"})
    client.delete("/api/v1/auth/refresh", headers=CSRF_HEADERS)  # registration signs in; start signed out
    if role:
        with app.app_context():
            user = User.query.filter_by(email=email).first()
            user.roles.append(Role.query.filter_by(name=role).first())
            db.session.commit()


def _login(client, email):
    return client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})


def _secret_of(app, email):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        row = db.session.get(UserTwoFactor, user.id)
        return two_factor._decrypt(row.secret_encrypted or row.pending_secret_encrypted)


def _actions(app, email):
    with app.app_context():
        uid = User.query.filter_by(email=email).first().id
        return [a.action for a in AuditLog.query.filter_by(entity_id=str(uid)).order_by(AuditLog.id).all()]


def _enroll_staff(client, app, email, role="editor"):
    _user(client, app, email, role)
    token = _login(client, email).get_json()["data"]["two_factor_token"]
    client.post("/api/v1/auth/2fa/setup/start", json={"token": token})
    secret = _secret_of(app, email)
    res = client.post("/api/v1/auth/2fa/setup/confirm", json={"token": token, "code": two_factor.code_for(secret)})
    assert res.status_code == 200
    return secret, res.get_json()["data"]


def test_production_default_requires_super_admin_admin_and_editor():
    from config import Config, TestingConfig

    assert Config.TWO_FACTOR_REQUIRED_ROLES == ("super_admin", "admin", "editor")
    assert TestingConfig.TWO_FACTOR_REQUIRED_ROLES == ()


def test_totp_matches_rfc_6238_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890"
    assert two_factor._code_at(secret, 59 // 30) == "287082"
    assert two_factor._code_at(secret, 1111111109 // 30) == "081804"


def test_required_staff_without_2fa_gets_setup_not_a_session(client, app):
    _user(client, app, "editor1@example.com", "editor")
    res = _login(client, "editor1@example.com")
    data = res.get_json()["data"]
    assert data["two_factor"] == "setup" and data["two_factor_token"]
    assert "access_token" not in data and "Set-Cookie" not in res.headers
    assert refresh_session(client).get_json()["data"] is None


def test_staff_enrollment_signs_in_with_recovery_codes_and_qr(client, app):
    _user(client, app, "editor2@example.com", "editor")
    token = _login(client, "editor2@example.com").get_json()["data"]["two_factor_token"]
    start = client.post("/api/v1/auth/2fa/setup/start", json={"token": token}).get_json()["data"]
    assert start["otpauth_uri"].startswith("otpauth://totp/Women%20Shaping%20Futures:editor2%40example.com?secret=")
    assert start["qr_svg"].startswith("data:image/svg+xml;base64,") and len(start["secret"]) >= 32
    bad = client.post("/api/v1/auth/2fa/setup/confirm", json={"token": token, "code": "000000"})
    assert bad.status_code == 422
    res = client.post("/api/v1/auth/2fa/setup/confirm",
                      json={"token": token, "code": two_factor.code_for(start["secret"])})
    assert res.status_code == 200
    body = res.get_json()["data"]
    assert body["access_token"] and len(body["recovery_codes"]) == 10
    assert refresh_cookie_value(client) and refresh_session(client).status_code == 200
    with app.app_context():
        row = UserTwoFactor.query.one()
        assert row.secret_encrypted and start["secret"] not in row.secret_encrypted  # encrypted at rest
        hashes = [c.code_hash for c in TwoFactorRecoveryCode.query.all()]
        assert all(code not in hashes for code in body["recovery_codes"])  # only hashes stored
        assert RefreshSession.query.filter_by(two_factor_verified=True).count() == 1
    assert {"2fa.setup_required", "2fa.setup_started", "2fa.enabled", "user.login"} <= set(_actions(app, "editor2@example.com"))


def test_challenge_wrong_code_replay_and_recovery_codes(client, app):
    secret, enrolled = _enroll_staff(client, app, "editor3@example.com")
    client.delete("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    token = _login(client, "editor3@example.com").get_json()["data"]["two_factor_token"]
    assert _login(client, "editor3@example.com").get_json()["data"]["two_factor"] == "challenge"
    assert client.post("/api/v1/auth/2fa/challenge", json={"token": token, "code": "123456"}).status_code == 401
    # The code used at enrollment can't be used again (replay).
    replay = client.post("/api/v1/auth/2fa/challenge", json={"token": token, "code": two_factor.code_for(secret)})
    assert replay.status_code == 401
    code = enrolled["recovery_codes"][0]
    ok = client.post("/api/v1/auth/2fa/challenge", json={"token": token, "recovery_code": code.upper()})
    assert ok.status_code == 200 and ok.get_json()["data"]["recovery_codes_remaining"] == 9
    again = client.post("/api/v1/auth/2fa/challenge", json={"token": token, "recovery_code": code})
    assert again.status_code == 401 and again.get_json()["error"]["code"] == "invalid_recovery_code"
    actions = _actions(app, "editor3@example.com")
    assert "2fa.challenge_failed" in actions and "2fa.recovery_code_used" in actions


def test_challenge_with_a_fresh_code_signs_in(client, app, monkeypatch):
    secret, _ = _enroll_staff(client, app, "editor4@example.com")
    client.delete("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    token = _login(client, "editor4@example.com").get_json()["data"]["two_factor_token"]
    import time as _time

    later = _time.time() + 60  # two steps later: a code never used before
    monkeypatch.setattr(two_factor.time, "time", lambda: later)
    res = client.post("/api/v1/auth/2fa/challenge", json={"token": token, "code": two_factor.code_for(secret, later)})
    assert res.status_code == 200 and res.get_json()["data"]["access_token"]
    assert "2fa.challenge_passed" in _actions(app, "editor4@example.com")


def test_challenge_is_rate_limited(client, app):
    _enroll_staff(client, app, "editor5@example.com")
    token = _login(client, "editor5@example.com").get_json()["data"]["two_factor_token"]
    codes = [client.post("/api/v1/auth/2fa/challenge", json={"token": token, "code": "000000"}).status_code
             for _ in range(6)]
    assert codes[:5] == [401] * 5 and codes[5] == 429


def test_bad_or_stale_tokens_are_refused(client, app):
    _user(client, app, "editor6@example.com", "editor")
    token = _login(client, "editor6@example.com").get_json()["data"]["two_factor_token"]
    assert client.post("/api/v1/auth/2fa/challenge", json={"token": token + "x", "code": "1"}).status_code == 401
    # A set-up token is not a challenge token.
    assert client.post("/api/v1/auth/2fa/challenge", json={"token": token, "code": "123456"}).status_code == 401
    with app.app_context():
        user = User.query.filter_by(email="editor6@example.com").first()
        user.auth_version += 1  # password reset after the token was issued
        db.session.commit()
    res = client.post("/api/v1/auth/2fa/setup/start", json={"token": token})
    assert res.status_code == 401


def test_member_optional_2fa_enable_challenge_disable(client, app, monkeypatch):
    client.post("/api/v1/auth/register", json={"email": "member@example.com", "password": PASSWORD,
                                               "first_name": "M", "last_name": "M"})
    access = _login(client, "member@example.com").get_json()["data"]["access_token"]  # no 2FA needed
    h = auth_headers(access)
    assert client.get("/api/v1/auth/2fa", headers=h).get_json()["data"] == {
        "enabled": False, "required": False, "recovery_codes_remaining": 0}
    secret = client.post("/api/v1/auth/2fa/setup/start", json={}, headers=h).get_json()["data"]["secret"]
    res = client.post("/api/v1/auth/2fa/setup/confirm", json={"code": two_factor.code_for(secret)}, headers=h)
    assert res.status_code == 200 and len(res.get_json()["data"]["recovery_codes"]) == 10
    # Turning 2FA on ends the pre-2FA token; this browser gets a new one.
    assert client.get("/api/v1/auth/2fa", headers=h).status_code == 401
    h = auth_headers(res.get_json()["data"]["access_token"])
    assert _login(client, "member@example.com").get_json()["data"]["two_factor"] == "challenge"
    import time as _time

    later = _time.time() + 60
    monkeypatch.setattr(two_factor.time, "time", lambda: later)
    assert client.post("/api/v1/auth/2fa/disable", json={"password": "wrong", "code": two_factor.code_for(secret, later)},
                       headers=h).status_code == 422
    assert client.post("/api/v1/auth/2fa/disable", json={"password": PASSWORD, "code": two_factor.code_for(secret, later)},
                       headers=h).status_code == 200
    assert "access_token" in _login(client, "member@example.com").get_json()["data"]
    assert "2fa.disabled" in _actions(app, "member@example.com")


def test_required_staff_cannot_turn_2fa_off(client, app):
    secret, enrolled = _enroll_staff(client, app, "editor7@example.com")
    h = auth_headers(enrolled["access_token"])
    res = client.post("/api/v1/auth/2fa/disable", json={"password": PASSWORD, "code": "000000"}, headers=h)
    assert res.status_code == 403 and res.get_json()["error"]["code"] == "two_factor_required"


def test_session_without_2fa_cannot_refresh_after_a_required_role_is_granted(client, app):
    client.post("/api/v1/auth/register", json={"email": "promoted@example.com", "password": PASSWORD,
                                               "first_name": "P", "last_name": "R"})
    assert refresh_session(client).status_code == 200
    with app.app_context():
        user = User.query.filter_by(email="promoted@example.com").first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    res = refresh_session(client)
    assert res.status_code == 401 and res.get_json()["error"]["code"] == "session_two_factor_required"


def test_super_admin_can_reset_another_accounts_2fa(client, app):
    _, admin = _enroll_staff(client, app, "chief@example.com", "super_admin")
    admin_h = auth_headers(admin["access_token"])
    client.delete("/api/v1/auth/refresh", headers=CSRF_HEADERS)
    _enroll_staff(client, app, "editor8@example.com")
    editor_cookie = refresh_cookie_value(client)
    with app.app_context():
        editor_id = User.query.filter_by(email="editor8@example.com").first().id
    res = client.post(f"/api/v1/admin/users/{editor_id}/two-factor/reset", headers=admin_h)
    assert res.status_code == 200 and res.get_json()["data"] == {"user_id": editor_id, "enabled": False, "required": True}
    assert refresh_session(client, editor_cookie).status_code == 401  # sessions ended
    assert _login(client, "editor8@example.com").get_json()["data"]["two_factor"] == "setup"  # must enroll again
    assert "2fa.reset_by_admin" in _actions(app, "editor8@example.com")


def test_only_a_super_admin_can_reset(client, app):
    _, editor = _enroll_staff(client, app, "editor9@example.com")
    with app.app_context():
        target = User.query.filter_by(email="editor9@example.com").first().id
    res = client.post(f"/api/v1/admin/users/{target}/two-factor/reset", headers=auth_headers(editor["access_token"]))
    assert res.status_code == 403


def test_production_requires_a_valid_encryption_key():
    from config import require_production_settings
    from tests.test_production_config import _bare_app

    with pytest.raises(RuntimeError, match="TWO_FACTOR_ENCRYPTION_KEY is not set"):
        require_production_settings(_bare_app(TWO_FACTOR_ENCRYPTION_KEY=None))
    with pytest.raises(RuntimeError, match="not a valid Fernet key"):
        require_production_settings(_bare_app(TWO_FACTOR_ENCRYPTION_KEY="short"))
