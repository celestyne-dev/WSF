"""Batch 4 corrections, Fix 1: first-party email verification and the
export/deletion privacy boundary for records matched only by email."""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.extensions import db
from app.models.audit import AuditLog
from app.models.email_verification import EmailVerificationToken
from app.models.newsletter import NewsletterSubscriber
from app.models.submissions import StorySubmission
from app.models.user import User
from tests.conftest import RAW_REGISTER_HEADER, auth_headers

PW = "supersecret1"
RAW = {RAW_REGISTER_HEADER: "1"}


def _register(client, email="new@example.invalid", send_ok=True):
    with patch("app.services.email.send_email", return_value=send_ok) as sent:
        res = client.post("/api/v1/auth/register", headers=RAW, json={
            "email": email, "password": PW, "first_name": "Nia", "last_name": "New", "age_confirmed": True})
    assert res.status_code == 201, res.get_json()
    link = sent.call_args.args[2].split("/verify-email/")[1].split()[0] if sent.call_args else None
    return res.get_json()["data"], link


def _verify(client, token):
    return client.post("/api/v1/auth/verify-email", json={"token": token})


def test_new_account_is_gated_until_verified(client, app):
    data, link = _register(client)
    assert data["verification_email_sent"] is True
    assert data["user"]["email_verification_pending"] is True and data["user"]["email_verified"] is False
    h = auth_headers(data["access_token"])
    gated = client.get("/api/v1/account/export", headers=h)
    assert gated.status_code == 403 and gated.get_json()["error"]["code"] == "email_verification_required"
    assert client.get("/api/v1/auth/me", headers=h).status_code == 200  # still allowed
    res = _verify(client, link)
    assert res.status_code == 200 and res.get_json()["data"]["result"] == "verified"
    assert client.get("/api/v1/account/export", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).get_json()["data"]["email_verification_pending"] is False


def test_token_is_hashed_single_use_and_audited_without_token(client, app):
    data, link = _register(client)
    with app.app_context():
        row = EmailVerificationToken.query.one()
        assert row.token_hash == hashlib.sha256(link.encode()).hexdigest() and link not in row.token_hash
        assert row.expires_at.replace(tzinfo=row.expires_at.tzinfo or timezone.utc) - datetime.now(timezone.utc) \
            <= timedelta(hours=24)
    assert _verify(client, link).get_json()["data"]["result"] == "verified"
    assert _verify(client, link).get_json()["data"]["result"] == "already_verified"  # reuse is harmless
    with app.app_context():
        logs = AuditLog.query.filter(AuditLog.action.like("user.email_verif%")).all()
        assert {l.action for l in logs} == {"user.email_verification_sent", "user.email_verified"}
        assert all(link not in str(l.changes) for l in logs)


def test_invalid_expired_and_superseded_links(client, app):
    data, first = _register(client)
    assert _verify(client, "not-a-real-token").status_code == 404
    with patch("app.services.email.send_email", return_value=True) as sent:
        res = client.post("/api/v1/auth/verify-email/resend", headers=auth_headers(data["access_token"]))
    assert res.status_code == 200
    second = sent.call_args.args[2].split("/verify-email/")[1].split()[0]
    sup = _verify(client, first)
    assert sup.status_code == 410 and sup.get_json()["error"]["code"] == "verification_superseded"
    with app.app_context():
        row = EmailVerificationToken.query.filter_by(token_hash=hashlib.sha256(second.encode()).hexdigest()).one()
        row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
    exp = _verify(client, second)
    assert exp.status_code == 410 and exp.get_json()["error"]["code"] == "verification_expired"
    with app.app_context():
        assert User.query.filter_by(email="new@example.invalid").one().email_verified_at is None


def test_send_failure_is_reported_truthfully(client, app):
    data, _ = _register(client, send_ok=False)
    assert data["verification_email_sent"] is False
    with app.app_context():
        assert EmailVerificationToken.query.filter_by(superseded_at=None).count() == 0  # no live link left
    with patch("app.services.email.send_email", return_value=False):
        res = client.post("/api/v1/auth/verify-email/resend", headers=auth_headers(data["access_token"]))
    assert res.status_code == 503 and res.get_json()["error"]["code"] == "email_send_failed"


def test_email_change_voids_ownership(client, app):
    data, link = _register(client)
    _verify(client, link)
    from app.services.user_admin import update_user_identity

    with app.app_context():
        user = User.query.filter_by(email="new@example.invalid").one()
        update_user_identity(user, email="changed@example.invalid")
        assert user.email_verified_at is None


def _legacy_account(app, email, is_verified=True):
    """An account from before verification existed: full access, unproven email."""
    with app.app_context():
        user = User(email=email, first_name="Old", last_name="Timer", is_verified=is_verified,
                    email_verification_required=False)
        user.set_password(PW)
        db.session.add(user)
        db.session.commit()


def _login(client, email):
    return client.post("/api/v1/auth/login", json={"email": email, "password": PW}).get_json()["data"]["access_token"]


def test_legacy_accounts_keep_access_and_is_verified_is_not_proof(client, app):
    _legacy_account(app, "legacy@example.invalid", is_verified=True)
    h = auth_headers(_login(client, "legacy@example.invalid"))
    res = client.get("/api/v1/account/export", headers=h)
    assert res.status_code == 200
    account = (res.get_json().get("data") or res.get_json())["account"]
    assert account["email_verified"] is False  # historical Boolean ignored
    with patch("app.services.email.send_email", return_value=True):
        assert client.post("/api/v1/auth/verify-email/resend", headers=h).status_code == 200  # offered


def _victim_records(app, email):
    with app.app_context():
        db.session.add(StorySubmission(first_name="Vic", last_name="Tim", email=email, title="Victim's story",
                                       body="Private story", status="submitted"))
        db.session.add(NewsletterSubscriber(email=email, status="active", first_name="Vic"))
        db.session.commit()


def test_account_using_someone_elses_email_cannot_read_or_destroy_their_records(client, app):
    victim = "victim@example.invalid"
    _victim_records(app, victim)
    # An account holding the victim's address without proving it (the only
    # way: legacy accounts; new registrations are gated before export).
    _legacy_account(app, victim, is_verified=True)
    token = _login(client, victim)
    res = client.get("/api/v1/account/export", headers=auth_headers(token))
    body = res.get_json().get("data") or res.get_json()
    assert body["story_submissions"] == [] and body["newsletter"] is None
    assert body["independent_records"]["newsletter_and_stories_included"] is False
    assert "Private story" not in str(body)
    # Deletion + purge leaves the independently submitted records untouched.
    with patch("app.services.email.send_email", return_value=True):
        assert client.post("/api/v1/account/deletion", headers=auth_headers(token),
                           json={"password": PW}).status_code == 200
    from app.services.account_privacy import purge_due

    with app.app_context():
        user = User.query.filter_by(email=victim).one()
        user.deletion_scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()
        assert purge_due()["purged"] == 1
        story = StorySubmission.query.filter_by(title="Victim's story").one()
        assert story.email == victim and story.body == "Private story" and story.anonymised_at is None
        assert NewsletterSubscriber.query.filter_by(email=victim).one().status == "active"
        from app.models.privacy import PrivacyRequest

        note = PrivacyRequest.query.filter_by(request_type="deletion").one().admin_notes
        assert "NOT deleted" in note


def test_verified_owner_gets_their_independent_records(client, app):
    owner = "owner@example.invalid"
    _victim_records(app, owner)
    data, link = _register(client, email=owner)
    _verify(client, link)
    res = client.get("/api/v1/account/export", headers=auth_headers(data["access_token"]))
    body = res.get_json().get("data") or res.get_json()
    assert [s["title"] for s in body["story_submissions"]] == ["Victim's story"]
    assert body["newsletter"]["status"] == "active"
