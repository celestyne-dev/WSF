import jwt as pyjwt
from datetime import datetime, timezone

from tests.conftest import auth_headers

REGISTER_PAYLOAD = {
    "email": "jane@example.com",
    "password": "supersecret1",
    "first_name": "Jane",
    "last_name": "Doe",
    "country_code": "US",
}


def test_register_login_me_flow(client):
    resp = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["success"] is True
    access_token = body["data"]["access_token"]
    assert body["data"]["user"]["email"] == "jane@example.com"
    assert "password_hash" not in body["data"]["user"]

    me = client.get("/api/v1/auth/me", headers=auth_headers(access_token))
    assert me.status_code == 200
    assert me.get_json()["data"]["email"] == "jane@example.com"

    login = client.post(
        "/api/v1/auth/login", json={"email": "jane@example.com", "password": "supersecret1"}
    )
    assert login.status_code == 200
    assert login.get_json()["data"]["access_token"]


def test_register_duplicate_email_is_rejected(client):
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    resp = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    assert resp.status_code == 409
    assert resp.get_json()["success"] is False


def test_register_missing_fields_returns_validation_error(client):
    resp = client.post("/api/v1/auth/register", json={"email": "bad-email"})
    assert resp.status_code == 422
    body = resp.get_json()
    assert body["success"] is False
    assert "email" in body["error"]["details"]
    assert "password" in body["error"]["details"]


def test_login_invalid_credentials(client):
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "wrong"}
    )
    assert resp.status_code == 401
    assert resp.get_json()["success"] is False


def test_logout_revokes_token(client):
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login", json={"email": "jane@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    logout = client.post("/api/v1/auth/logout", headers=auth_headers(token))
    assert logout.status_code == 200

    me = client.get("/api/v1/auth/me", headers=auth_headers(token))
    assert me.status_code == 401


def test_admin_endpoint_requires_permission(client):
    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login", json={"email": "jane@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
    assert resp.status_code == 403


def test_admin_endpoint_allows_super_admin(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email="jane@example.com").first()
        role = Role.query.filter_by(name="super_admin").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": "jane@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["total"] == 1


def _resign_with_shifted_iat(app, access_token, seconds_ahead):
    """Re-signs a real, otherwise-untouched access token with its `iat`
    claim moved `seconds_ahead` into the future, using the app's own
    secret/algorithm — deterministically reproduces the clock-skew window
    that trips PyJWT's zero-tolerance iat check, without any sleep or
    timing race.
    """
    with app.app_context():
        secret = app.config["JWT_SECRET_KEY"]
        algorithm = app.config["JWT_ALGORITHM"]
        payload = pyjwt.decode(access_token, secret, algorithms=[algorithm])
        payload["iat"] = int(datetime.now(timezone.utc).timestamp()) + seconds_ahead
        return pyjwt.encode(payload, secret, algorithm=algorithm)


def test_freshly_issued_token_tolerates_small_clock_skew(client, app):
    """Regression for the intermittent 422 "The token is not yet valid
    (iat)" seen when a token issued by /auth/login or /auth/register is
    immediately used on a protected endpoint. PyJWT's iat check rejects a
    token whenever its iat is even a fraction of a second ahead of the
    decoding process's own clock read (`iat > now + leeway`), and with
    the default zero leeway, ordinary sub-second scheduling/clock jitter
    between the encode and decode calls is enough to trip it. A 1-second
    future iat — comfortably inside JWT_DECODE_LEEWAY (2s) — must still
    be accepted.
    """
    resp = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    access_token = resp.get_json()["data"]["access_token"]

    skewed_token = _resign_with_shifted_iat(app, access_token, seconds_ahead=1)

    me = client.get("/api/v1/auth/me", headers=auth_headers(skewed_token))
    assert me.status_code == 200
    assert me.get_json()["data"]["email"] == "jane@example.com"


def test_iat_beyond_configured_leeway_is_still_rejected(client, app):
    """Confirms the fix is a small, bounded tolerance rather than iat
    verification being disabled: an iat clearly past JWT_DECODE_LEEWAY
    (2s) — 10s here — must still be rejected exactly as before.
    """
    resp = client.post("/api/v1/auth/register", json=REGISTER_PAYLOAD)
    access_token = resp.get_json()["data"]["access_token"]

    skewed_token = _resign_with_shifted_iat(app, access_token, seconds_ahead=10)

    me = client.get("/api/v1/auth/me", headers=auth_headers(skewed_token))
    assert me.status_code == 422
    assert me.get_json()["error"]["code"] == "invalid_token"
