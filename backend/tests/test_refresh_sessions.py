"""HttpOnly refresh-cookie sessions (app/services/refresh_sessions.py,
app/api/v1/auth.py RefreshResource)."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.refresh_session import RefreshSession
from app.services.refresh_sessions import hash_token
from tests.conftest import CSRF_HEADERS, REFRESH_PATH, auth_headers, refresh_cookie_value, refresh_session

USER = {"email": "cookie-user@example.com", "password": "supersecret1", "first_name": "C", "last_name": "U"}


def _login(client, register=True):
    if register:
        assert client.post("/api/v1/auth/register", json=USER).status_code == 201
    res = client.post("/api/v1/auth/login", json={"email": USER["email"], "password": USER["password"]})
    assert res.status_code == 200
    return res


def _set_cookie_header(res):
    return next(v for k, v in res.headers.items() if k == "Set-Cookie" and v.startswith("wsf_refresh="))


def test_sign_in_sets_httponly_strict_secure_cookie_scoped_to_refresh(client):
    res = _login(client)
    header = _set_cookie_header(res)
    for attr in ("HttpOnly", "Secure", "SameSite=Strict", f"Path={REFRESH_PATH}"):
        assert attr in header, attr
    max_age = int(header.split("Max-Age=")[1].split(";")[0])
    assert 30 * 86400 - 60 <= max_age <= 30 * 86400
    data = res.get_json()["data"]
    assert data["access_token"] and "refresh_token" not in data  # nothing long-lived reaches JavaScript


def test_register_signs_in_with_a_cookie_too(client):
    res = client.post("/api/v1/auth/register", json=USER)
    assert res.status_code == 201 and "refresh_token" not in res.get_json()["data"]
    assert "HttpOnly" in _set_cookie_header(res)


def test_only_a_hash_of_the_cookie_is_stored(client, app):
    _login(client)
    raw = refresh_cookie_value(client)
    with app.app_context():
        row = RefreshSession.query.filter_by(token_hash=hash_token(raw)).one()
        assert row.token_hash != raw and len(row.token_hash) == 64
        assert RefreshSession.query.filter_by(token_hash=raw).count() == 0


def test_silent_refresh_returns_user_and_new_access_token(client):
    _login(client)
    res = refresh_session(client)
    assert res.status_code == 200
    data = res.get_json()["data"]
    assert data["user"]["email"] == USER["email"]
    assert client.get("/api/v1/auth/me", headers=auth_headers(data["access_token"])).status_code == 200


def test_no_cookie_is_a_normal_signed_out_answer(client):
    res = refresh_session(client)
    assert res.status_code == 200 and res.get_json()["data"] is None


def test_csrf_header_and_origin_are_required(client):
    _login(client)
    assert refresh_session(client, headers={"Origin": "http://localhost"}).status_code == 403
    no_origin = refresh_session(client, headers={"X-WSF-CSRF": "1"})
    assert no_origin.status_code == 403 and no_origin.get_json()["error"]["code"] == "missing_origin"
    evil = refresh_session(client, headers={"X-WSF-CSRF": "1", "Origin": "https://evil.example"})
    assert evil.status_code == 403 and evil.get_json()["error"]["code"] == "origin_not_allowed"
    # Referer is accepted when a browser omits Origin.
    assert refresh_session(client, headers={"X-WSF-CSRF": "1", "Referer": "http://localhost/account"}).status_code == 200
    # Sign-out is protected the same way.
    assert client.delete(REFRESH_PATH, headers={"Origin": "http://localhost"}).status_code == 403


def test_sign_out_revokes_server_side_clears_cookie_and_blocks_access_token(client, app):
    res = _login(client)
    access = res.get_json()["data"]["access_token"]
    cookie = refresh_cookie_value(client)
    out = client.delete(REFRESH_PATH, headers={**CSRF_HEADERS, **auth_headers(access)})
    assert out.status_code == 200
    cleared = _set_cookie_header(out)
    assert "Max-Age=0" in cleared or "expires=Thu, 01 Jan 1970" in cleared
    with app.app_context():
        row = RefreshSession.query.filter_by(token_hash=hash_token(cookie)).one()
        assert row.revoked_at is not None and row.revoked_reason == "sign_out"
    # The old cookie value can't be replayed, and the access token is blocked.
    replay = refresh_session(client, cookie)
    assert replay.status_code == 401 and replay.get_json()["error"]["code"] == "session_revoked"
    assert client.get("/api/v1/auth/me", headers=auth_headers(access)).status_code == 401


def test_sign_out_works_with_an_expired_or_missing_access_token(client):
    _login(client)
    assert client.delete(REFRESH_PATH, headers={**CSRF_HEADERS, "Authorization": "Bearer not-a-jwt"}).status_code == 200
    assert refresh_session(client).get_json()["data"] is None  # cookie gone


def test_expired_session_is_refused_and_cookie_cleared(client, app):
    _login(client)
    cookie = refresh_cookie_value(client)
    with app.app_context():
        row = RefreshSession.query.filter_by(token_hash=hash_token(cookie)).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.session.commit()
    res = refresh_session(client)
    assert res.status_code == 401 and res.get_json()["error"]["code"] == "session_expired"
    assert "wsf_refresh=;" in _set_cookie_header(res)


def test_credential_change_ends_sessions(client, app):
    from app.models.user import User

    _login(client)
    with app.app_context():
        user = User.query.filter_by(email=USER["email"]).first()
        user.auth_version += 1
        db.session.commit()
    res = refresh_session(client)
    assert res.status_code == 401 and res.get_json()["error"]["code"] == "session_credentials_changed"


def test_each_sign_in_is_its_own_session(client, app):
    _login(client)
    first = refresh_cookie_value(client)
    _login(client, register=False)
    second = refresh_cookie_value(client)
    assert first != second
    client.delete(REFRESH_PATH, headers=CSRF_HEADERS)  # signs out the second only
    assert refresh_session(client, first).status_code == 200
