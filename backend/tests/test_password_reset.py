import hashlib
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt as pyjwt

from app.extensions import db
from app.models.audit import AuditLog
from app.models.password_reset import PasswordResetToken
from app.models.user import User
from tests.conftest import auth_headers

REGISTER_PAYLOAD = {
    "email": "reset.target@example.com",
    "password": "supersecret1",
    "first_name": "Reset",
    "last_name": "Target",
}

GENERIC_FORGOT_MESSAGE = "If an account exists for that email, we have sent password reset instructions."
GENERIC_INVALID_TOKEN_MESSAGE = "This password reset link is invalid or has expired."


def _register(client, **overrides):
    payload = {**REGISTER_PAYLOAD, **overrides}
    return client.post("/api/v1/auth/register", json=payload)


def _forgot(client, email=REGISTER_PAYLOAD["email"]):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


def _reset(client, token, new_password="newsecret1", confirm_password=None):
    return client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "new_password": new_password,
            "confirm_password": confirm_password if confirm_password is not None else new_password,
        },
    )


def _capture_reset(client, email=REGISTER_PAYLOAD["email"], send_succeeds=True):
    """Requests a password reset while capturing what would have been
    emailed, without touching a real SMTP server. Returns (response,
    raw_token_or_None, captured_send_email_kwargs). Exercises the real
    service end-to-end (token generation/hashing/persistence) — only the
    final network call is replaced.
    """
    captured = {}

    def fake_send_email(**kwargs):
        captured.update(kwargs)
        return send_succeeds

    with patch("app.services.password_reset.send_email", side_effect=fake_send_email):
        resp = _forgot(client, email)

    match = re.search(r"#token=([^\s<\"]+)", captured.get("text_body", ""))
    raw_token = match.group(1) if match else None
    return resp, raw_token, captured


def _all_audit_text(app):
    with app.app_context():
        return " ".join(f"{e.action} {e.entity_id} {e.changes}" for e in AuditLog.query.all())


class TestForgotPasswordEnumeration:
    def test_active_user_can_request_reset(self, client, app):
        _register(client)
        resp, raw_token, captured = _capture_reset(client)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == GENERIC_FORGOT_MESSAGE
        assert "token" not in resp.get_json()  # never exposed in the API response
        assert raw_token is not None
        assert captured["subject"] == "Reset your Women Shaping Futures password"

        with app.app_context():
            user = User.query.filter_by(email=REGISTER_PAYLOAD["email"]).first()
            assert PasswordResetToken.query.filter_by(user_id=user.id).count() == 1
            assert AuditLog.query.filter_by(action="password_reset.requested").count() == 1

    def test_unknown_email_gets_identical_response(self, client, app):
        _register(client)
        known_resp, _, _ = _capture_reset(client, email=REGISTER_PAYLOAD["email"])
        unknown_resp = _forgot(client, email="nobody-at-all@example.com")

        assert unknown_resp.status_code == known_resp.status_code == 200
        assert unknown_resp.get_json() == known_resp.get_json()

        with app.app_context():
            assert PasswordResetToken.query.count() == 1  # only the known user's
            assert AuditLog.query.filter_by(action="password_reset.requested").count() == 1

    def test_inactive_user_gets_identical_response(self, client, app):
        _register(client, email="goingdark@example.com")
        with app.app_context():
            user = User.query.filter_by(email="goingdark@example.com").first()
            user.is_active = False
            db.session.commit()

        resp = _forgot(client, email="goingdark@example.com")
        assert resp.status_code == 200
        assert resp.get_json()["message"] == GENERIC_FORGOT_MESSAGE

        with app.app_context():
            assert PasswordResetToken.query.count() == 0
            assert AuditLog.query.filter_by(action="password_reset.requested").count() == 0

    def test_malformed_email_still_returns_generic_response(self, client):
        # Marshmallow's Email field 422s a non-email string — this must
        # still never distinguish "bad input" from "valid but unknown"
        # in a way that's useful for enumeration. A plain validation
        # error is acceptable here (it reveals nothing about any
        # account); the enumeration guarantee is about well-formed
        # emails, verified by the other tests in this class.
        resp = client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"})
        assert resp.status_code == 422

    def test_rate_limited_after_five_per_hour(self, client):
        for _ in range(5):
            resp = _forgot(client, email="rate.limit.target@example.com")
            assert resp.status_code == 200
        resp = _forgot(client, email="rate.limit.target@example.com")
        assert resp.status_code == 429


class TestTokenStorageAndHashing:
    def test_raw_token_is_not_stored_in_database(self, client, app):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        assert raw_token

        with app.app_context():
            for row in PasswordResetToken.query.all():
                assert row.token_hash != raw_token
                assert raw_token not in (row.token_hash or "")

    def test_stored_hash_is_sha256_of_raw_token(self, client, app):
        _register(client)
        _, raw_token, _ = _capture_reset(client)

        with app.app_context():
            user = User.query.filter_by(email=REGISTER_PAYLOAD["email"]).first()
            token_row = PasswordResetToken.query.filter_by(user_id=user.id).first()
            assert token_row.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class TestResetPassword:
    def test_expired_token_rejected_safely(self, client, app):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        with app.app_context():
            token_row = PasswordResetToken.query.first()
            token_row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            db.session.commit()

        resp = _reset(client, raw_token)
        assert resp.status_code == 422
        assert resp.get_json()["error"]["message"] == GENERIC_INVALID_TOKEN_MESSAGE
        assert resp.get_json()["error"]["code"] == "invalid_token"

    def test_token_is_one_time_use(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)

        first = _reset(client, raw_token, new_password="firstnewpass1")
        assert first.status_code == 200

        second = _reset(client, raw_token, new_password="secondnewpass1")
        assert second.status_code == 422
        assert second.get_json()["error"]["message"] == GENERIC_INVALID_TOKEN_MESSAGE

    def test_second_request_invalidates_first_token(self, client):
        _register(client)
        _, first_token, _ = _capture_reset(client)
        _, second_token, _ = _capture_reset(client)
        assert first_token != second_token

        stale = _reset(client, first_token)
        assert stale.status_code == 422

        fresh = _reset(client, second_token)
        assert fresh.status_code == 200

    def test_malformed_token_rejected_safely(self, client):
        _register(client)
        resp = _reset(client, "not-even-a-real-token")
        assert resp.status_code == 422
        assert resp.get_json()["error"]["message"] == GENERIC_INVALID_TOKEN_MESSAGE
        assert resp.get_json()["error"]["code"] == "invalid_token"

    def test_wrong_unknown_token_rejected_safely(self, client):
        import secrets

        _register(client)
        resp = _reset(client, secrets.token_urlsafe(32))
        assert resp.status_code == 422
        assert resp.get_json()["error"]["message"] == GENERIC_INVALID_TOKEN_MESSAGE

    def test_mismatched_passwords_rejected(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        resp = _reset(client, raw_token, new_password="newsecret1", confirm_password="different1")
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "password_mismatch"

    def test_too_short_password_rejected(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        resp = _reset(client, raw_token, new_password="short1", confirm_password="short1")
        assert resp.status_code == 422
        assert resp.get_json()["error"]["code"] == "validation_error"

    def test_successful_reset_changes_password(self, client, app):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        resp = _reset(client, raw_token, new_password="brandnewpass1")
        assert resp.status_code == 200
        assert resp.get_json()["data"] is None

        with app.app_context():
            user = User.query.filter_by(email=REGISTER_PAYLOAD["email"]).first()
            assert user.check_password("brandnewpass1")
            assert not user.check_password(REGISTER_PAYLOAD["password"])

    def test_old_password_fails_after_reset(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )
        assert resp.status_code == 401

    def test_new_password_works_after_reset(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        resp = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": "brandnewpass1"},
        )
        assert resp.status_code == 200

    def test_reset_does_not_auto_login(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        resp = _reset(client, raw_token, new_password="brandnewpass1")
        body = resp.get_json()
        assert body["data"] is None
        assert "access_token" not in str(body)
        assert "refresh_token" not in str(body)

    def test_must_change_password_becomes_false_after_recovery(self, client, app):
        from app.services.user_admin import create_staff_user

        with app.app_context():
            actor = User(email="actor@example.com", first_name="A", last_name="B")
            actor.set_password("supersecret1")
            db.session.add(actor)
            db.session.commit()
            _, _temp_password = create_staff_user(
                email="forcedstaff@example.com",
                first_name="Forced",
                last_name="Staff",
                role_names=["editor"],
                is_active=True,
                actor=actor,
            )
            user = User.query.filter_by(email="forcedstaff@example.com").first()
            assert user.must_change_password is True

        _, raw_token, _ = _capture_reset(client, email="forcedstaff@example.com")
        resp = _reset(client, raw_token, new_password="herchosenpass1")
        assert resp.status_code == 200

        with app.app_context():
            user = User.query.filter_by(email="forcedstaff@example.com").first()
            assert user.must_change_password is False


class TestJwtInvalidationAfterRecovery:
    def test_existing_access_token_invalid_after_recovery(self, client):
        _register(client)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )
        old_access_token = login.get_json()["data"]["access_token"]
        assert client.get("/api/v1/auth/me", headers=auth_headers(old_access_token)).status_code == 200

        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        resp = client.get("/api/v1/auth/me", headers=auth_headers(old_access_token))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "token_revoked"

    def test_existing_refresh_token_invalid_after_recovery(self, client):
        _register(client)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )
        old_refresh_token = login.get_json()["data"]["refresh_token"]

        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        resp = client.post("/api/v1/auth/refresh", headers=auth_headers(old_refresh_token))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "token_revoked"

    def test_tokens_issued_after_recovery_work(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        login = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": "brandnewpass1"},
        )
        assert login.status_code == 200
        new_access_token = login.get_json()["data"]["access_token"]

        resp = client.get("/api/v1/auth/me", headers=auth_headers(new_access_token))
        assert resp.status_code == 200


def _decode_reencode(app, token, mutate):
    with app.app_context():
        secret = app.config["JWT_SECRET_KEY"]
        algorithm = app.config["JWT_ALGORITHM"]
        payload = pyjwt.decode(token, secret, algorithms=[algorithm])
        mutate(payload)
        return pyjwt.encode(payload, secret, algorithm=algorithm)


class TestAuthVersionBackwardCompatibility:
    def test_token_with_no_auth_version_claim_works_when_user_still_version_zero(self, client, app):
        _register(client)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )
        access_token = login.get_json()["data"]["access_token"]

        legacy_token = _decode_reencode(app, access_token, lambda p: p.pop("auth_version", None))

        resp = client.get("/api/v1/auth/me", headers=auth_headers(legacy_token))
        assert resp.status_code == 200

    def test_legacy_token_rejected_once_auth_version_increments(self, client, app):
        _register(client)
        login = client.post(
            "/api/v1/auth/login",
            json={"email": REGISTER_PAYLOAD["email"], "password": REGISTER_PAYLOAD["password"]},
        )
        access_token = login.get_json()["data"]["access_token"]
        legacy_token = _decode_reencode(app, access_token, lambda p: p.pop("auth_version", None))

        # Confirm it works BEFORE the bump (same assertion as the test
        # above, kept here too so this test is self-contained proof of
        # the "before vs after" transition on one token).
        assert client.get("/api/v1/auth/me", headers=auth_headers(legacy_token)).status_code == 200

        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        resp = client.get("/api/v1/auth/me", headers=auth_headers(legacy_token))
        assert resp.status_code == 401
        assert resp.get_json()["error"]["code"] == "token_revoked"


class TestEmailFailureHandling:
    def test_delivery_failure_still_returns_generic_response(self, client, app):
        _register(client)
        resp, raw_token, _ = _capture_reset(client, send_succeeds=False)
        assert resp.status_code == 200
        assert resp.get_json()["message"] == GENERIC_FORGOT_MESSAGE
        assert raw_token  # the service did generate one before delivery failed

        with app.app_context():
            user = User.query.filter_by(email=REGISTER_PAYLOAD["email"]).first()
            # Never audited as "requested" — delivery never actually happened.
            assert AuditLog.query.filter_by(action="password_reset.requested").count() == 0
            token_row = PasswordResetToken.query.filter_by(user_id=user.id).first()
            assert token_row.used_at is not None  # invalidated on failure

    def test_token_from_failed_delivery_cannot_be_used(self, client):
        _register(client)
        _, raw_token, _ = _capture_reset(client, send_succeeds=False)
        resp = _reset(client, raw_token)
        assert resp.status_code == 422
        assert resp.get_json()["error"]["message"] == GENERIC_INVALID_TOKEN_MESSAGE


class TestAuditPrivacy:
    def test_raw_token_never_appears_in_audit_records(self, client, app):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        audit_text = _all_audit_text(app)
        assert raw_token not in audit_text

    def test_password_reset_completed_is_audited_without_secrets(self, client, app):
        _register(client)
        _, raw_token, _ = _capture_reset(client)
        _reset(client, raw_token, new_password="brandnewpass1")

        with app.app_context():
            entry = AuditLog.query.filter_by(action="password_reset.completed").first()
            assert entry is not None
            assert "brandnewpass1" not in str(entry.changes)
            assert raw_token not in str(entry.changes)
