from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import User
from tests.conftest import auth_headers

REGISTER_PAYLOAD = {
    "email": "newpublicuser@example.com",
    "password": "supersecret1",
    "first_name": "Public",
    "last_name": "User",
    "country_code": "US",
}


def _register(client, **overrides):
    payload = {**REGISTER_PAYLOAD, **overrides}
    return client.post("/api/v1/auth/register", json=payload)


def _register_and_login(client, email="jane@example.com", password="supersecret1"):
    """Mirrors tests/test_admin_users.py's helper of the same name — a
    plain public account with no roles beyond whatever /auth/register
    itself grants.
    """
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "first_name": "Jane", "last_name": "Doe"},
    )
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return login.get_json()["data"]["access_token"]


class TestPublicRegistration:
    def test_registration_creates_user_with_member_role(self, client, app):
        resp = _register(client)
        assert resp.status_code == 201
        body = resp.get_json()["data"]
        assert [r["name"] for r in body["user"]["roles"]] == ["member"]

        with app.app_context():
            user = User.query.filter_by(email=REGISTER_PAYLOAD["email"]).first()
            assert user is not None
            assert user.has_role("member")

    def test_registered_user_does_not_require_password_change(self, client):
        resp = _register(client)
        assert resp.get_json()["data"]["user"]["must_change_password"] is False

    def test_duplicate_email_still_rejected(self, client):
        _register(client)
        resp = _register(client)
        assert resp.status_code == 409
        assert resp.get_json()["error"]["code"] == "email_taken"

    def test_registration_rejects_invalid_country(self, client, app):
        """A direct API request isn't bound by CountrySelect's browser-side
        option list — the server must validate country_code itself rather
        than trusting it straight into the country_code FK.
        """
        resp = _register(client, email="badcountry@example.com", country_code="ZZ999")
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "invalid_country"
        with app.app_context():
            assert User.query.filter_by(email="badcountry@example.com").first() is None

    def test_registration_does_not_create_a_community_member(self, app, client):
        """Core separation requirement: creating a User(email=x) must never
        create a Member(email=x) — joining /community stays its own
        explicit opt-in (see app/models/community.py, untouched here).
        """
        from app.models.community import Member

        _register(client)
        with app.app_context():
            assert Member.query.filter_by(email=REGISTER_PAYLOAD["email"]).first() is None


class TestMeGet:
    def test_get_me_works_for_public_account(self, client):
        token = _register_and_login(client)
        resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.status_code == 200
        assert resp.get_json()["data"]["email"] == "jane@example.com"


class TestProfileUpdate:
    def test_patch_me_requires_authentication(self, client):
        resp = client.patch("/api/v1/auth/me", json={"first_name": "X"})
        assert resp.status_code == 401

    def test_patch_me_updates_permitted_fields(self, client, app):
        token = _register_and_login(client)
        resp = client.patch(
            "/api/v1/auth/me",
            json={
                "first_name": "Janet",
                "last_name": "Doer",
                "display_name": "J. Doer",
                "bio": "Building things for women in tech.",
                "country_code": "KE",
            },
            headers=auth_headers(token),
        )
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["first_name"] == "Janet"
        assert data["last_name"] == "Doer"
        assert data["display_name"] == "J. Doer"
        assert data["bio"] == "Building things for women in tech."
        assert data["country_code"] == "KE"

        with app.app_context():
            user = User.query.filter_by(email="jane@example.com").first()
            assert user.first_name == "Janet"
            assert user.country_code == "KE"

    def test_patch_me_trims_string_fields(self, client):
        token = _register_and_login(client)
        resp = client.patch(
            "/api/v1/auth/me", json={"display_name": "  Spacey Name  "}, headers=auth_headers(token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["display_name"] == "Spacey Name"

    def test_patch_me_partial_update_leaves_other_fields_untouched(self, client):
        token = _register_and_login(client)
        client.patch("/api/v1/auth/me", json={"bio": "Hello there."}, headers=auth_headers(token))
        resp = client.patch("/api/v1/auth/me", json={"first_name": "Janet"}, headers=auth_headers(token))
        assert resp.status_code == 200
        data = resp.get_json()["data"]
        assert data["first_name"] == "Janet"
        assert data["bio"] == "Hello there."

    def test_cannot_change_roles_through_patch_me(self, client, app):
        # SelfProfileUpdateSchema doesn't declare roles/role_names at all,
        # and marshmallow's default unknown=RAISE rejects the whole request
        # outright (422) rather than silently accepting and ignoring it —
        # stronger than merely "no-op": the attempt itself is refused.
        token = _register_and_login(client)
        resp = client.patch(
            "/api/v1/auth/me", json={"roles": ["super_admin"], "role_names": ["super_admin"]}, headers=auth_headers(token)
        )
        assert resp.status_code == 422
        with app.app_context():
            user = User.query.filter_by(email="jane@example.com").first()
            assert user.role_names() == {"member"}

    def test_cannot_change_email_through_patch_me(self, client, app):
        token = _register_and_login(client)
        resp = client.patch(
            "/api/v1/auth/me", json={"email": "hijacked@example.com"}, headers=auth_headers(token)
        )
        assert resp.status_code == 422
        with app.app_context():
            # Still findable under the original address — email untouched.
            assert User.query.filter_by(email="jane@example.com").first() is not None
            assert User.query.filter_by(email="hijacked@example.com").first() is None

    def test_cannot_change_must_change_password_through_patch_me(self, client, app):
        token = _register_and_login(client)
        resp = client.patch(
            "/api/v1/auth/me", json={"must_change_password": True}, headers=auth_headers(token)
        )
        assert resp.status_code == 422
        with app.app_context():
            user = User.query.filter_by(email="jane@example.com").first()
            assert user.must_change_password is False

    def test_invalid_country_rejected(self, client):
        token = _register_and_login(client)
        resp = client.patch(
            "/api/v1/auth/me", json={"country_code": "ZZ999"}, headers=auth_headers(token)
        )
        assert resp.status_code == 422

    def test_inactive_account_cannot_update_profile(self, client, app):
        token = _register_and_login(client, email="goingdark@example.com")
        with app.app_context():
            user = User.query.filter_by(email="goingdark@example.com").first()
            user.is_active = False
            db.session.commit()

        resp = client.patch("/api/v1/auth/me", json={"first_name": "X"}, headers=auth_headers(token))
        assert resp.status_code == 403

    def test_forced_change_account_cannot_update_profile(self, client, app):
        """A staff account created with a temporary password must finish
        POST /auth/change-password before she can edit her own profile —
        same centralized guard that blocks every other protected action.
        """
        from app.services.user_admin import create_staff_user

        with app.app_context():
            actor = User(email="actor@example.com", first_name="A", last_name="B")
            actor.set_password("supersecret1")
            db.session.add(actor)
            db.session.commit()
            _, temp_password = create_staff_user(
                email="forcedstaff@example.com",
                first_name="Forced",
                last_name="Staff",
                role_names=["editor"],
                is_active=True,
                actor=actor,
            )

        login = client.post(
            "/api/v1/auth/login", json={"email": "forcedstaff@example.com", "password": temp_password}
        )
        token = login.get_json()["data"]["access_token"]

        resp = client.patch("/api/v1/auth/me", json={"first_name": "X"}, headers=auth_headers(token))
        assert resp.status_code == 403
        assert resp.get_json()["error"]["code"] == "password_change_required"

    def test_profile_update_is_audited(self, client, app):
        token = _register_and_login(client, email="audited_profile@example.com")
        client.patch(
            "/api/v1/auth/me",
            json={"first_name": "Renamed", "bio": "A very distinctive bio value."},
            headers=auth_headers(token),
        )
        with app.app_context():
            entry = AuditLog.query.filter_by(action="user.profile_update").first()
            assert entry is not None
            # The audit entry records WHICH fields changed, never the
            # submitted values — a distinctive profile value must not leak
            # into audit metadata (bio/name content isn't on
            # app/services/audit.py's sensitive-key denylist, so this has
            # to be enforced at the call site, not the redactor).
            assert entry.changes == {"fields": ["bio", "first_name"]}
            assert "Renamed" not in str(entry.changes)
            assert "distinctive bio" not in str(entry.changes)
