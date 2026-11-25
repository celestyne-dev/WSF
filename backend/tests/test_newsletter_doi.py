"""Provider-neutral newsletter (Step 14): double opt-in, legacy rows,
suppression authority, consented export, external send records, external
unsubscribe import. No sending-provider API anywhere."""
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.audit import AuditLog
from app.models.newsletter import (
    NewsletterConfirmation,
    NewsletterIssue,
    NewsletterSendRecord,
    NewsletterSubscriber,
    NewsletterSubscriberEvent,
)
from app.models.user import Role, User
from app.services import newsletter as svc
from tests.conftest import auth_headers


class Outbox:
    def __init__(self):
        self.mail = []

    def send(self, to, subject, text, *a, **k):
        self.mail.append({"to": to, "subject": subject, "text": text})
        return True

    def token(self, index=-1):
        return re.search(r"/newsletter/confirm/(\S+)", self.mail[index]["text"]).group(1)


@pytest.fixture()
def outbox():
    box = Outbox()
    with patch("app.services.email.send_email", side_effect=box.send):
        yield box


@pytest.fixture()
def admin(app):
    with app.app_context():
        user = User(email="nl-admin@example.invalid", first_name="N", last_name="A", is_active=True)
        user.set_password("supersecret1")
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.add(user)
        db.session.commit()
        return auth_headers(create_access_token(identity=user))


def _signup(client, email, consent=True, **extra):
    return client.post("/api/v1/newsletter/subscribe", json={"email": email, "consent": consent, **extra})


def _confirm(client, token):
    return client.post("/api/v1/newsletter/confirm", json={"token": token})


def _row(app, email):
    with app.app_context():
        return NewsletterSubscriber.query.filter_by(email=email).first()


def _events(app, email):
    with app.app_context():
        sid = NewsletterSubscriber.query.filter_by(email=email).first().id
        return [e.event for e in NewsletterSubscriberEvent.query.filter_by(subscriber_id=sid)
                .order_by(NewsletterSubscriberEvent.id).all()]


def test_unticked_consent_stores_nothing_and_sends_nothing(client, app, outbox):
    for consent in (False, None, "yes"):
        resp = client.post("/api/v1/newsletter/subscribe", json={"email": "x@example.com", "consent": consent})
        assert resp.status_code == 422
    assert _row(app, "x@example.com") is None and outbox.mail == []


def test_signup_creates_pending_and_sends_a_transactional_confirmation(client, app, outbox):
    resp = _signup(client, "New@Example.com", placement="footer")
    assert resp.status_code == 201 and resp.get_json()["data"]["status"] == "confirmation_required"
    row = _row(app, "new@example.com")
    assert row.status == "pending" and row.confirmed_at is None
    assert len(outbox.mail) == 1
    mail = outbox.mail[0]
    assert mail["to"] == "new@example.com" and "confirm" in mail["subject"].lower()
    assert "/newsletter/confirm/" in mail["text"] and "/privacy" in mail["text"] and "7 days" in mail["text"]
    with app.app_context():
        stored = NewsletterConfirmation.query.one()
        assert stored.token_hash != outbox.token() and len(stored.token_hash) == 64  # only a hash is stored
        assert stored.consent_version == "newsletter-v2" and stored.consent_source == "footer"
    assert _events(app, "new@example.com") == ["signup_requested"]


def test_confirmation_activates_records_consent_and_is_idempotent(client, app, outbox):
    _signup(client, "c@example.com", placement="newsletter-page")
    token = outbox.token()
    assert _confirm(client, token).get_json()["data"]["result"] == "confirmed"
    row = _row(app, "c@example.com")
    assert row.status == "active" and row.confirmed_at and row.consent_at
    assert row.consent_version == "newsletter-v2" and row.consent_source == "newsletter-page"
    again = _confirm(client, token)
    assert again.status_code == 200 and again.get_json()["data"]["result"] == "already_confirmed"
    assert _events(app, "c@example.com") == ["signup_requested", "confirmed"]


def test_bad_and_expired_tokens(client, app, outbox):
    assert _confirm(client, "not-a-token").status_code == 404
    assert _confirm(client, None).status_code == 404
    _signup(client, "late@example.com")
    with app.app_context():
        NewsletterConfirmation.query.update({"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)})
        db.session.commit()
    resp = _confirm(client, outbox.token())
    assert resp.status_code == 410 and resp.get_json()["error"]["code"] == "confirmation_expired"
    assert _row(app, "late@example.com").status == "pending"


def test_resend_rules_one_usable_link_and_no_inbox_flooding(client, app, outbox):
    _signup(client, "again@example.com")
    _signup(client, "again@example.com")  # within 10 minutes: no second email
    assert len(outbox.mail) == 1
    with app.app_context():
        NewsletterConfirmation.query.update({"created_at": datetime.now(timezone.utc) - timedelta(minutes=11)})
        db.session.commit()
    _signup(client, "again@example.com")
    assert len(outbox.mail) == 2
    assert _confirm(client, outbox.token(0)).status_code == 404  # superseded link
    assert _confirm(client, outbox.token(1)).status_code == 200
    with app.app_context():
        assert NewsletterSubscriber.query.filter_by(email="again@example.com").count() == 1


def test_already_confirmed_signup_sends_nothing(client, app, outbox):
    _signup(client, "done@example.com")
    _confirm(client, outbox.token())
    resp = _signup(client, "done@example.com", firstName="Later")
    assert resp.get_json()["data"]["status"] == "confirmation_required" and len(outbox.mail) == 1
    # Batch 4 corrections: an unauthenticated signup never changes an existing
    # subscriber's details.
    assert _row(app, "done@example.com").first_name is None


def test_unsubscribe_is_authoritative_and_voids_pending_links(client, app, outbox):
    _signup(client, "u@example.com")
    _confirm(client, outbox.token())
    token = _row(app, "u@example.com").unsubscribe_token
    assert client.get(f"/api/v1/newsletter/unsubscribe/{token}").status_code == 200
    row = _row(app, "u@example.com")
    assert row.status == "unsubscribed" and row.unsubscribe_source == "link"
    # An ordinary signup does not reactivate...
    _signup(client, "u@example.com")
    assert _row(app, "u@example.com").status == "unsubscribed"
    # ...unsubscribing again voids that fresh link too.
    client.get(f"/api/v1/newsletter/unsubscribe/{token}")
    assert _confirm(client, outbox.token()).status_code == 404
    assert _row(app, "u@example.com").status == "unsubscribed"


def test_fresh_signup_and_confirmation_reactivate_with_trail(client, app, outbox):
    _signup(client, "r@example.com")
    _confirm(client, outbox.token())
    client.post("/api/v1/newsletter/unsubscribe", json={"email": "r@example.com"})
    _signup(client, "r@example.com", placement="jobs")
    _confirm(client, outbox.token())
    row = _row(app, "r@example.com")
    assert row.status == "active" and row.consent_source == "jobs"
    assert _events(app, "r@example.com") == ["signup_requested", "confirmed", "unsubscribed", "signup_requested",
                                             "reactivated_by_confirmation"]


def test_export_only_confirmed_active_and_only_delivery_fields(client, app, admin, outbox):
    _signup(client, "yes@example.com", firstName="Ada")
    _confirm(client, outbox.token())
    _signup(client, "pending@example.com")
    _signup(client, "gone@example.com")
    _confirm(client, outbox.token())
    client.post("/api/v1/newsletter/unsubscribe", json={"email": "gone@example.com"})
    with app.app_context():
        db.session.add(NewsletterSubscriber(email="legacy@example.com", status="legacy_unconfirmed",
                                            consent_version="newsletter-v1"))
        db.session.add(NewsletterSubscriber(email="bounce@example.com", status="bounced"))
        db.session.commit()
    text = client.get("/api/v1/newsletter/subscribers/export", headers=admin).get_data(as_text=True)
    lines = text.strip().splitlines()
    assert lines == ["email,first_name,last_name", "yes@example.com,Ada,"]


def test_issue_export_follows_audience_and_is_recorded(client, app, admin, outbox):
    _signup(client, "one@example.com")
    _confirm(client, outbox.token())
    create = client.post("/api/v1/newsletter/issues", headers=admin, json={
        "title": "Issue", "subject": "Subject", "content": [{"type": "paragraph", "text": "Hi"}], "status": "ready"})
    slug = create.get_json()["data"]["slug"]
    resp = client.get(f"/api/v1/newsletter/issues/{slug}/export", headers=admin)
    assert resp.status_code == 200 and "one@example.com" in resp.get_data(as_text=True)
    records = client.get(f"/api/v1/newsletter/issues/{slug}/send-records", headers=admin).get_json()["data"]["records"]
    assert records[0]["kind"] == "export" and records[0]["recipientCount"] == 1
    assert client.get(f"/api/v1/newsletter/issues/{slug}", headers=admin).get_json()["data"]["status"] == "ready"
    sent = client.post(f"/api/v1/newsletter/issues/{slug}/record-send", headers=admin, json={
        "providerName": "Illustrative Sending Service", "recipientCount": 1, "externalReference": "abc",
        "sentAt": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()})
    assert sent.status_code == 200
    future = client.post("/api/v1/newsletter/issues", headers=admin, json={
        "title": "Issue 2", "subject": "S2", "content": [{"type": "paragraph", "text": "Hi"}]}).get_json()["data"]["slug"]
    bad = client.post(f"/api/v1/newsletter/issues/{future}/record-send", headers=admin, json={
        "providerName": "X", "recipientCount": 1, "sentAt": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()})
    assert bad.status_code == 422
    with app.app_context():
        kinds = [r.kind for r in NewsletterSendRecord.query.order_by(NewsletterSendRecord.id).all()]
        assert kinds == ["export", "external_send"]
        actions = {a.action for a in AuditLog.query.all()}
        assert {"newsletter_issue_exported", "newsletter_issue_external_send_recorded"} <= actions


def test_suppression_import_is_authoritative_and_idempotent(client, app, admin, outbox):
    _signup(client, "active1@example.com")
    _confirm(client, outbox.token())
    _signup(client, "pending1@example.com")
    csv_text = ("Email Address,Unsubscribed On\n"
                "ACTIVE1@example.com,2026-11-01\n"
                "pending1@example.com,2026-11-01\n"
                "unknown@example.com,2026-11-01\n"
                "not-an-email,2026-11-01\n"
                "active1@example.com,2026-11-02\n")
    res = client.post("/api/v1/newsletter/subscribers/suppression-import", headers=admin,
                      json={"provider": "Illustrative Sending Service", "csv": csv_text, "filename": "unsubs.csv"})
    assert res.status_code == 200
    counts = res.get_json()["data"]
    assert counts == {**counts, "rows": 5, "invalid": 1, "newlySuppressed": 2, "alreadySuppressed": 1,
                      "addedUnknown": 1}
    for email in ("active1@example.com", "pending1@example.com", "unknown@example.com"):
        row = _row(app, email)
        assert row.status == "unsubscribed" and row.unsubscribe_source == "external_import"
        assert row.unsubscribe_reason == "Illustrative Sending Service"
    again = client.post("/api/v1/newsletter/subscribers/suppression-import", headers=admin,
                        json={"provider": "Illustrative Sending Service", "csv": csv_text}).get_json()["data"]
    assert again["newlySuppressed"] == 0 and again["addedUnknown"] == 0 and again["alreadySuppressed"] == 4
    # Never reactivated by the import, and the unknown address can't be exported.
    text = client.get("/api/v1/newsletter/subscribers/export", headers=admin).get_data(as_text=True)
    assert "unknown@example.com" not in text and "active1@example.com" not in text
    with app.app_context():
        entry = AuditLog.query.filter_by(action="newsletter_suppression_import").first()
        assert entry.changes["newlySuppressed"] == 2 and "active1@example.com" not in str(entry.changes)


def test_one_by_one_studio_suppression_still_works(client, app, admin, outbox):
    _signup(client, "studio@example.com")
    _confirm(client, outbox.token())
    sid = _row(app, "studio@example.com").id
    res = client.post(f"/api/v1/newsletter/subscribers/{sid}/suppress", headers=admin, json={"reason": "Asked by phone"})
    assert res.status_code == 200
    row = _row(app, "studio@example.com")
    assert row.status == "unsubscribed" and row.unsubscribe_source == "studio" and row.unsubscribe_reason == "Asked by phone"


def test_legacy_subscribers_are_not_exported_until_they_confirm(client, app, admin, outbox):
    old = datetime(2025, 3, 1, tzinfo=timezone.utc)
    with app.app_context():
        row = NewsletterSubscriber(email="old@example.com", status="legacy_unconfirmed", subscribed_at=old,
                                   consent_version="newsletter-v1")
        db.session.add(row)
        db.session.commit()
        sid = row.id
    assert "old@example.com" not in client.get("/api/v1/newsletter/subscribers/export",
                                               headers=admin).get_data(as_text=True)
    res = client.post(f"/api/v1/newsletter/subscribers/{sid}/request-confirmation", headers=admin)
    assert res.status_code == 200 and "keep receiving" in outbox.mail[-1]["subject"]
    _confirm(client, outbox.token())
    row = _row(app, "old@example.com")
    assert row.status == "active" and row.consent_version == "newsletter-reconfirm-v1"
    assert row.subscribed_at.replace(tzinfo=timezone.utc) == old  # original date kept, nothing invented
    # Only legacy rows can be asked.
    assert client.post(f"/api/v1/newsletter/subscribers/{sid}/request-confirmation", headers=admin).status_code == 409


def test_audience_estimate_counts_only_confirmed(client, app, admin, outbox):
    _signup(client, "a1@example.com")
    _confirm(client, outbox.token())
    _signup(client, "a2@example.com")
    res = client.post("/api/v1/newsletter/audience-estimate", json={}, headers=admin)
    assert res.get_json()["data"]["estimatedRecipients"] == 1
    overview = client.get("/api/v1/newsletter/overview", headers=admin).get_json()["data"]
    assert overview["activeSubscribers"] == 1 and overview["pendingSubscribers"] == 1 and "readyIssues" in overview


def test_no_provider_api_is_required_or_configured():
    import inspect

    source = inspect.getsource(svc)
    for name in ("mailchimp", "brevo", "sendinblue", "mailerlite", "zoho", "convertkit", "requests.", "httpx"):
        assert name not in source.lower()
    with pytest.raises(NotImplementedError):
        svc.DeliveryAdapter().push_audience([])


def test_issue_statuses_are_honest():
    from app.models.newsletter import ISSUE_STATUSES

    assert ISSUE_STATUSES == ("draft", "ready", "sent", "archived")
    assert NewsletterIssue.__table__.c.status is not None
