"""Step 16: FK audit, self-service JSON export, 14-day account deletion with
cancellation and scheduled purge, payment retention, audit-log FK fix,
comment/story anonymisation, privacy-request tool."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.services import account_privacy as svc
from tests.conftest import CSRF_HEADERS, auth_headers, refresh_cookie_value, refresh_session

PASSWORD = "supersecret1"


def _member(client, email="leaver@example.invalid"):
    res = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD,
                                                     "first_name": "Lee", "last_name": "Ver"})
    data = res.get_json()["data"]
    return data["access_token"], data["user"]["id"]


def _staff(app, email, role="admin"):
    with app.app_context():
        u = User(email=email, first_name="S", last_name="T", is_active=True)
        u.set_password(PASSWORD)
        u.roles.append(Role.query.filter_by(name=role).first())
        db.session.add(u)
        db.session.commit()
        return auth_headers(create_access_token(identity=u)), u.id


def _request_deletion(client, token, remove_comments=False, password=PASSWORD):
    with patch("app.services.email.send_email", return_value=True) as sent:
        res = client.post("/api/v1/account/deletion", headers=auth_headers(token),
                          json={"password": password, "removeComments": remove_comments})
    return res, sent


def _expire_grace(app, uid):
    with app.app_context():
        db.session.get(User, uid).deletion_scheduled_for = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()


# --- FK audit ----------------------------------------------------------------------------------


def test_every_foreign_key_to_users_has_a_deletion_decision(app):
    with app.app_context():
        found = {f"{t.name}.{c.name}" for t, c, _o, _n in svc.user_foreign_keys()}
    assert found == set(svc.FK_TREATMENT), (found - set(svc.FK_TREATMENT), set(svc.FK_TREATMENT) - found)
    assert len(found) == 63  # 61 before Step 16 + privacy_requests.user_id and .created_by_id
    assert {k for k, (t, _) in svc.FK_TREATMENT.items() if t == "retain"} == {
        "circle_payments.user_id", "circle_subscriptions.user_id", "resource_payments.user_id",
        "resource_purchases.user_id", "orders.user_id"}


def test_payment_and_audit_fks_no_longer_cascade_or_block(app):
    with app.app_context():
        rules = {f"{t.name}.{c.name}": (o, n) for t, c, o, n in svc.user_foreign_keys()}
    for key in ("circle_payments.user_id", "circle_subscriptions.user_id", "resource_payments.user_id",
                "resource_purchases.user_id", "orders.user_id", "audit_logs.user_id", "analytics_events.user_id"):
        assert rules[key] == ("SET NULL", True), key


# --- export ------------------------------------------------------------------------------------


def test_export_is_own_data_only_and_never_secrets(client, app):
    token, uid = _member(client)
    _other_token, _ = _member(client, "someone-else@example.invalid")
    res = client.get("/api/v1/account/export", headers=auth_headers(token))
    assert res.status_code == 200 and res.headers["Content-Disposition"].startswith("attachment;")
    assert res.headers["Cache-Control"] == "no-store"
    data = res.get_json()
    assert data["format"] == "wsf-account-export-v1" and data["account"]["email"] == "leaver@example.invalid"
    text = res.get_data(as_text=True)
    assert "someone-else@example.invalid" not in text
    for secret in ("password_hash", "token_hash", "ip_hash", "unsubscribe_token", "auth_version", "secret_encrypted"):
        assert secret not in text
    for section in ("sign_in_sessions", "saved_items", "event_registrations", "learning_enrollments", "comments",
                    "newsletter", "cookie_consent_records", "orders", "circle_payments", "story_submissions"):
        assert section in data
    with app.app_context():
        assert AuditLog.query.filter_by(action="account.export").count() == 1
    assert client.get("/api/v1/account/export").status_code == 401


def test_export_is_rate_limited(client):
    token, _ = _member(client, "many@example.invalid")
    codes = [client.get("/api/v1/account/export", headers=auth_headers(token)).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


# --- deletion request ----------------------------------------------------------------------------


def test_deletion_needs_the_password_and_staff_cannot_self_delete(client, app):
    token, _ = _member(client)
    res, _ = _request_deletion(client, token, password="wrong")
    assert res.status_code == 422
    staff_headers, staff_id = _staff(app, "staffer@example.invalid")
    with patch("app.services.email.send_email", return_value=True):
        res = client.post("/api/v1/account/deletion", headers=staff_headers, json={"password": PASSWORD})
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "deletion_blocked"


def test_request_revokes_every_session_at_once_and_blocks_use(client, app):
    token, uid = _member(client)
    cookie = refresh_cookie_value(client)
    res, sent = _request_deletion(client, token)
    assert res.status_code == 200
    assert res.get_json()["data"]["session_ended"] is True
    assert any(h.startswith("wsf_refresh=;") for h in res.headers.getlist("Set-Cookie"))
    assert client.get("/api/v1/auth/me", headers=auth_headers(token)).status_code == 401  # access token dead
    assert refresh_session(client, cookie).status_code == 401  # refresh session dead
    mail = sent.call_args
    assert "scheduled for deletion" in mail.args[1] and "/account/deletion/cancel/" in mail.args[2]
    # Signing in offers only cancellation, never a session.
    login = client.post("/api/v1/auth/login", json={"email": "leaver@example.invalid", "password": PASSWORD})
    data = login.get_json()["data"]
    assert data["deletion_pending"] is True and "access_token" not in data and data["cancel_token"]
    assert refresh_cookie_value(client) is None
    with app.app_context():
        user = db.session.get(User, uid)
        scheduled = user.deletion_scheduled_for.replace(tzinfo=timezone.utc)
        assert timedelta(days=13, hours=23) < scheduled - datetime.now(timezone.utc) <= timedelta(days=14)
        from app.models.privacy import PrivacyRequest

        req = PrivacyRequest.query.filter_by(user_id=uid).one()
        assert (req.request_type, req.status, req.source) == ("deletion", "in_progress", "self_service")


def test_cancel_by_signing_in_then_normal_login(client, app):
    token, uid = _member(client)
    _request_deletion(client, token)
    login = client.post("/api/v1/auth/login", json={"email": "leaver@example.invalid", "password": PASSWORD})
    cancel = client.post("/api/v1/account/deletion/cancel", json={"token": login.get_json()["data"]["cancel_token"]})
    assert cancel.status_code == 200
    again = client.post("/api/v1/auth/login", json={"email": "leaver@example.invalid", "password": PASSWORD})
    assert "access_token" in again.get_json()["data"]
    with app.app_context():
        assert db.session.get(User, uid).deletion_scheduled_for is None
    assert client.post("/api/v1/account/deletion/cancel", json={"token": "bad"}).status_code == 400


def test_cancel_by_email_link_signed_out(client, app):
    token, uid = _member(client)
    _, sent = _request_deletion(client, token)
    link_token = sent.call_args.args[2].split("/account/deletion/cancel/")[1].split()[0]
    assert client.post("/api/v1/account/deletion/cancel-link", json={"token": link_token}).status_code == 200
    with app.app_context():
        assert db.session.get(User, uid).deletion_scheduled_for is None
    # A link from an earlier, cancelled request can't cancel a later one.
    token2 = client.post("/api/v1/auth/login", json={"email": "leaver@example.invalid",
                                                     "password": PASSWORD}).get_json()["data"]["access_token"]
    _request_deletion(client, token2)
    assert client.post("/api/v1/account/deletion/cancel-link", json={"token": link_token}).status_code == 404


# --- purge -------------------------------------------------------------------------------------


def _world(app, uid):
    """Comments, a reply from someone else, payments, an audit entry, consent,
    a community member profile and story submissions for this user."""
    from app.models.article import Article
    from app.models.comment import Comment
    from app.models.community import Member
    from app.models.consent import ConsentRecord
    from app.models.learning import LearningProgram
    from app.models.people import Author
    from app.models.resource import Resource, ResourcePayment, ResourcePurchase
    from app.models.submissions import StorySubmission

    with app.app_context():
        user = db.session.get(User, uid)
        other = User(email="replier@example.invalid", first_name="R", last_name="P", is_active=True)
        other.set_password(PASSWORD)
        author = Author(slug="ed", name="Ed")
        db.session.add_all([other, author])
        db.session.flush()
        article = Article(title="A", slug="a", status="published", content=[], author_id=author.id,
                          publish_date=datetime.now(timezone.utc) - timedelta(days=2))
        resource = Resource(name="R", slug="r", status="published")
        db.session.add_all([article, resource])
        db.session.flush()
        top = Comment(article_id=article.id, user_id=uid, body="My words", status="published", held_reasons=[],
                      ip_hash="a" * 64, ip_hash_expires_at=datetime.now(timezone.utc) + timedelta(days=30))
        db.session.add(top)
        db.session.flush()
        db.session.add(Comment(article_id=article.id, user_id=other.id, parent_id=top.id, body="Reply",
                               status="published", held_reasons=[]))
        purchase = ResourcePurchase(user_id=uid, resource_id=resource.id, payment_reference="REF-1")
        db.session.add(purchase)
        db.session.flush()
        db.session.add(ResourcePayment(reference="REF-1", user_id=uid, resource_id=resource.id,
                                       purchase_id=purchase.id, amount_subunits=1000, currency="KES",
                                       customer_email=user.email, status="consumed"))
        db.session.add(AuditLog(user_id=uid, action="user.login", entity_type="User", entity_id=str(uid)))
        db.session.add(ConsentRecord(user_id=uid, consent_version="1", preferences=False, analytics=False,
                                     marketing=False, decided_at=datetime.now(timezone.utc)))
        db.session.add(Member(first_name="Lee", last_name="Ver", email=user.email, user_id=uid, status="active"))
        base = dict(last_name="Ver", email=user.email, body="Story", status="submitted")
        published = StorySubmission(first_name="Lee", title="Published story", city="Nairobi", **base)
        unpublished = StorySubmission(first_name="Lee", title="Unpublished", **base)
        db.session.add_all([published, unpublished])
        db.session.flush()
        db.session.add(Article(title="From story", slug="from-story", status="published", content=[],
                               author_id=author.id, source_submission_id=published.id))
        db.session.commit()
        return {"top": top.id, "published_story": published.id, "unpublished_story": unpublished.id}


def test_purge_after_grace_keeps_threads_payments_and_audit(client, app):
    token, uid = _member(client)
    ids = _world(app, uid)
    _request_deletion(client, token)
    with app.app_context():
        assert svc.purge_due() == {"purged": 0, "skipped": 0}  # still within the grace period
    _expire_grace(app, uid)
    with app.app_context():
        assert svc.purge_due() == {"purged": 1, "skipped": 0}
        assert svc.purge_due() == {"purged": 0, "skipped": 0}  # idempotent
        from app.models.comment import Comment
        from app.models.community import Member
        from app.models.consent import ConsentRecord
        from app.models.privacy import PrivacyRequest
        from app.models.resource import ResourcePayment, ResourcePurchase
        from app.models.submissions import StorySubmission

        assert db.session.get(User, uid) is None
        top = db.session.get(Comment, ids["top"])
        assert top.user_id is None and top.body == "My words" and top.ip_hash is None  # Former member by default
        payment = ResourcePayment.query.filter_by(reference="REF-1").one()
        assert payment.user_id is None and payment.amount_subunits == 1000  # retained, detached
        assert ResourcePurchase.query.filter_by(payment_reference="REF-1").one().user_id is None
        audit = AuditLog.query.filter_by(action="user.login").all()
        assert audit and all(a.user_id is None for a in audit)  # audit FK no longer blocks
        assert AuditLog.query.filter_by(action="account.purged", entity_id=str(uid)).count() == 1
        consent = ConsentRecord.query.one()
        assert consent.user_id is None and consent.account_deleted_at is not None
        assert Member.query.filter_by(email="leaver@example.invalid").count() == 0
        story = db.session.get(StorySubmission, ids["published_story"])
        assert story.anonymised_at and story.first_name == "Former" and story.city is None
        assert "leaver" not in story.email and story.body == "Story"
        assert db.session.get(StorySubmission, ids["unpublished_story"]) is None
        req = PrivacyRequest.query.filter_by(request_type="deletion").one()
        assert req.status == "completed" and req.requester_email is None and req.user_id is None
    item = [c for c in client.get("/api/v1/comments/article/a").get_json()["data"]["comments"]
            if c["id"] == ids["top"]][0]
    assert item["author"]["name"] == "Former member" and item["replies"]


def test_purge_with_also_remove_my_comments(client, app):
    token, uid = _member(client)
    ids = _world(app, uid)
    _request_deletion(client, token, remove_comments=True)
    _expire_grace(app, uid)
    with app.app_context():
        svc.purge_due()
    data = client.get("/api/v1/comments/article/a").get_json()["data"]
    assert "My words" not in str(data)
    assert [c for c in data["comments"] if c["id"] == ids["top"]][0]["body"] == "Comment deleted"


def test_purge_cli_and_maintenance_job(app):
    result = app.test_cli_runner().invoke(args=["accounts-purge-due"])
    assert "Purged 0 account(s)" in result.output


# --- privacy requests --------------------------------------------------------------------------


def test_member_and_studio_privacy_requests(client, app):
    token, uid = _member(client)
    res = client.post("/api/v1/account/privacy-requests", headers=auth_headers(token),
                      json={"requestType": "correction", "details": "My surname is misspelled."})
    assert res.status_code == 201
    due = datetime.fromisoformat(res.get_json()["data"]["dueAt"])
    assert timedelta(days=29, hours=23) < due - datetime.now(timezone.utc) <= timedelta(days=30)
    assert client.post("/api/v1/account/privacy-requests", headers=auth_headers(token),
                       json={"requestType": "deletion", "details": "x"}).status_code == 422
    assert client.get("/api/v1/admin/privacy-requests", headers=auth_headers(token)).status_code == 403
    staff, _ = _staff(app, "dpo@example.invalid")
    created = client.post("/api/v1/admin/privacy-requests", headers=staff, json={
        "requestType": "access", "requesterEmail": "phone-caller@example.invalid", "details": "Asked by phone"})
    assert created.status_code == 201
    rid = created.get_json()["data"]["id"]
    listing = client.get("/api/v1/admin/privacy-requests", headers=staff).get_json()["data"]["items"]
    assert {r["requestType"] for r in listing} == {"correction", "access"} and not any(r["overdue"] for r in listing)
    upd = client.patch(f"/api/v1/admin/privacy-requests/{rid}", headers=staff,
                       json={"status": "completed", "adminNotes": "Sent export by email."})
    assert upd.get_json()["data"]["status"] == "completed" and upd.get_json()["data"]["completedAt"]
    with app.app_context():
        actions = [a.action for a in AuditLog.query.filter_by(entity_type="PrivacyRequest").order_by(AuditLog.id)]
        assert actions == ["privacy_request.created", "privacy_request.created", "privacy_request.updated"]


def test_cancel_page_is_served_noindex_and_token_free(client, app):
    from tests.test_spa_shell import FIXTURE_INDEX_PATH

    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    res = client.get("/account/deletion/cancel/secret-cancel-token")
    assert res.status_code == 200 and "secret-cancel-token" not in res.get_data(as_text=True)
