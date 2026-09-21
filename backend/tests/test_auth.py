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
