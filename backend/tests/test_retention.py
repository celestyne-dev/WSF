"""Step 17 retention engine: only expired data is affected; idempotent; dry
run; inactive-account warning lifecycle; removed comment text after 12
months; unverified-account rule inactive; bounded, audited settings."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.services import retention as svc
from tests.conftest import auth_headers

NOW = datetime.now(timezone.utc)


def ago(**kw):
    return NOW - timedelta(**kw)


def _user(email, created=None, last_login=None, role="member", verified=False):
    u = User(email=email, first_name="A", last_name="B", is_active=True, is_verified=verified,
             created_at=created or NOW, last_login_at=last_login)
    u.set_password("supersecret1")
    u.roles.append(Role.query.filter_by(name=role).first())
    db.session.add(u)
    db.session.flush()
    return u


def _run(app, **kw):
    with app.app_context():
        return svc.run_retention(now=NOW, **kw)


def test_each_rule_only_touches_expired_records(app):
    from app.models.analytics import AnalyticsEvent
    from app.models.consent import ConsentRecord
    from app.models.contact import ContactInquiry
    from app.models.password_reset import PasswordResetToken
    from app.models.submissions import StorySubmission

    with app.app_context():
        u = _user("keep@example.invalid")
        db.session.add_all([
            AnalyticsEvent(event_name="old", created_at=ago(days=430)),
            AnalyticsEvent(event_name="new", created_at=ago(days=400)),
            AuditLog(action="user.login", entity_type="User", ip_address="203.0.113.1", user_agent="UA",
                     created_at=ago(days=370)),
            AuditLog(action="user.login", entity_type="User", ip_address="203.0.113.2", user_agent="UA",
                     created_at=ago(days=300)),
            AuditLog(action="article.publish", entity_type="Article", ip_address="203.0.113.3",
                     created_at=ago(days=900)),
            ContactInquiry(first_name="Old", last_name="X", email="o@example.invalid", subject="S", message="M", inquiry_type="general",
                           created_at=ago(days=740)),
            ContactInquiry(first_name="New", last_name="X", email="n@example.invalid", subject="S", message="M", inquiry_type="general",
                           created_at=ago(days=700)),
            StorySubmission(first_name="D", last_name="X", email="d@example.invalid", title="Declined", body="B",
                            status="declined", reviewed_at=ago(days=370)),
            StorySubmission(first_name="R", last_name="X", email="r@example.invalid", title="Recent", body="B",
                            status="declined", reviewed_at=ago(days=100)),
            StorySubmission(first_name="P", last_name="X", email="p@example.invalid", title="Pending", body="B",
                            status="submitted"),
            PasswordResetToken(user_id=u.id, token_hash="a" * 64, created_at=ago(hours=25), expires_at=ago(hours=24)),
            PasswordResetToken(user_id=u.id, token_hash="b" * 64, created_at=ago(hours=1), expires_at=NOW),
            ConsentRecord(consent_version="1", preferences=False, analytics=False, marketing=False, decided_at=NOW,
                          account_deleted_at=ago(days=740)),
            ConsentRecord(consent_version="1", preferences=False, analytics=False, marketing=False, decided_at=NOW,
                          account_deleted_at=ago(days=300)),
            ConsentRecord(user_id=u.id, consent_version="1", preferences=False, analytics=False, marketing=False,
                          decided_at=ago(days=2000)),
        ])
        db.session.commit()
    results = _run(app)
    assert results["analytics_events"] == 1 and results["auth_ip_cleared"] == 1
    assert results["contact_inquiries"] == 1 and results["declined_stories"] == 1
    assert results["password_reset_tokens"] == 1 and results["consent_records"] == 1
    with app.app_context():
        assert [e.event_name for e in AnalyticsEvent.query.all()] == ["new"]
        logs = {a.ip_address for a in AuditLog.query.all()}
        assert logs == {None, "203.0.113.2", "203.0.113.3"}  # only old sign-in entries cleared; entries kept
        assert AuditLog.query.count() == 3
        assert [c.first_name for c in ContactInquiry.query.all()] == ["New"]
        assert sorted(s.title for s in StorySubmission.query.all()) == ["Pending", "Recent"]
        assert PasswordResetToken.query.count() == 1
        assert ConsentRecord.query.count() == 2  # live account's record kept regardless of age
    second = _run(app)
    assert all(v == 0 for k, v in second.items() if isinstance(v, int))  # idempotent


def test_payments_kept_six_years_then_deleted(app):
    from app.models.circle import CirclePayment, CirclePlan

    with app.app_context():
        plan = CirclePlan(name="P", slug="p", price=10, currency="KES", status="active", billing_interval="monthly")
        db.session.add(plan)
        db.session.flush()
        for ref, age in (("OLD", 6 * 366), ("NEW", 5 * 365)):
            db.session.add(CirclePayment(reference=ref, plan_id=plan.id, amount_subunits=1000, currency="KES",
                                         billing_interval="monthly", customer_email="p@example.invalid", status="pending",
                                         created_at=ago(days=age)))
        db.session.commit()
    assert _run(app)["payment_records"] == 1
    with app.app_context():
        assert [p.reference for p in CirclePayment.query.all()] == ["NEW"]


def test_removed_comment_text_erased_after_12_months_thread_kept(app, client):
    from app.models.article import Article
    from app.models.comment import Comment, CommentEvent
    from app.models.people import Author

    with app.app_context():
        u = _user("c@example.invalid")
        author = Author(slug="ed", name="Ed")
        db.session.add(author)
        db.session.flush()
        article = Article(title="T", slug="t", status="published", content=[], author_id=author.id,
                          publish_date=ago(days=500))
        db.session.add(article)
        db.session.flush()
        old = Comment(article_id=article.id, user_id=u.id, body="Old removed", status="removed",
                      removal_reason="Abuse", removed_at=ago(days=370), held_reasons=[])
        recent = Comment(article_id=article.id, user_id=u.id, body="Recent removed", status="removed",
                         removal_reason="Abuse", removed_at=ago(days=100), held_reasons=[])
        db.session.add_all([old, recent])
        db.session.flush()
        db.session.add(Comment(article_id=article.id, user_id=u.id, parent_id=old.id, body="Reply",
                               status="published", held_reasons=[]))
        db.session.commit()
        old_id, recent_id = old.id, recent.id
    assert _run(app)["removed_comment_text"] == 1
    with app.app_context():
        erased = db.session.get(Comment, old_id)
        assert erased.body is None and erased.status == "removed" and erased.removal_reason == "Abuse"
        assert db.session.get(Comment, recent_id).body == "Recent removed"
        assert CommentEvent.query.filter_by(comment_id=old_id, action="body_erased").count() == 1
    thread = client.get("/api/v1/comments/article/t").get_json()["data"]["comments"]
    assert [c["body"] for c in thread if c["id"] == old_id] == ["Comment removed"]


def test_comment_ip_hashes_cleared_after_90_days(app):
    from app.models.article import Article
    from app.models.comment import Comment
    from app.models.people import Author

    with app.app_context():
        author = Author(slug="ed2", name="Ed")
        db.session.add(author)
        db.session.flush()
        article = Article(title="T", slug="t2", status="published", content=[], author_id=author.id)
        db.session.add(article)
        db.session.flush()
        db.session.add_all([
            Comment(article_id=article.id, body="a", status="published", held_reasons=[], ip_hash="x" * 64,
                    ip_hash_expires_at=ago(days=1)),
            Comment(article_id=article.id, body="b", status="published", held_reasons=[], ip_hash="y" * 64,
                    ip_hash_expires_at=NOW + timedelta(days=10)),
        ])
        db.session.commit()
    assert _run(app)["comment_ip_hashes"] == 1


def test_dry_run_changes_nothing(app):
    from app.models.analytics import AnalyticsEvent

    with app.app_context():
        db.session.add(AnalyticsEvent(event_name="old", created_at=ago(days=500)))
        db.session.commit()
    assert _run(app, dry_run=True)["analytics_events"] == 1
    with app.app_context():
        assert AnalyticsEvent.query.count() == 1


def test_unverified_rule_never_touches_accounts_that_predate_verification(app):
    with app.app_context():
        _user("never-verified@example.invalid", created=ago(days=90), last_login=ago(days=1))
        db.session.commit()
    assert _run(app)["unverified_accounts"] == 0
    with app.app_context():
        assert User.query.filter_by(email="never-verified@example.invalid").count() == 1


# --- inactive accounts ---------------------------------------------------------------------------


def _inactive(app, email="sleepy@example.invalid", role="member"):
    with app.app_context():
        u = _user(email, created=ago(days=4 * 365), last_login=ago(days=3 * 365 - 20), role=role)
        db.session.commit()
        return u.id


def test_warning_once_then_purge_after_the_warning_period(app):
    uid = _inactive(app)
    sent = []
    with patch("app.services.email.send_email", side_effect=lambda *a, **k: sent.append(a) or True):
        assert _run(app)["inactive_accounts"] == {"warned": 1, "purged": 0}
        assert _run(app)["inactive_accounts"] == {"warned": 0, "purged": 0}  # not repeated
    assert len(sent) == 1 and "will be deleted soon" in sent[0][1] and "sign in before" in sent[0][2]
    with app.app_context():
        user = db.session.get(User, uid)
        user.inactivity_warning_sent_at = ago(days=31)
        user.last_login_at = ago(days=3 * 365 + 5)
        db.session.commit()
    assert _run(app)["inactive_accounts"] == {"warned": 0, "purged": 1}
    with app.app_context():
        assert db.session.get(User, uid) is None
        assert AuditLog.query.filter_by(action="account.purged_inactive").count() == 1


def test_signing_in_after_the_warning_keeps_the_account(app):
    uid = _inactive(app)
    with patch("app.services.email.send_email", return_value=True):
        _run(app)
    with app.app_context():
        user = db.session.get(User, uid)
        assert user.inactivity_warning_sent_at is not None
        user.inactivity_warning_sent_at = NOW - timedelta(days=2)
        user.last_login_at = NOW - timedelta(days=1)  # signed in after the warning
        db.session.commit()
    assert _run(app)["inactive_accounts"] == {"warned": 0, "purged": 0}
    with app.app_context():
        assert db.session.get(User, uid).inactivity_warning_sent_at is None


def test_email_failure_means_no_warning_recorded_and_no_deletion(app):
    uid = _inactive(app)
    with patch("app.services.email.send_email", return_value=False):
        _run(app)
    with app.app_context():
        assert db.session.get(User, uid).inactivity_warning_sent_at is None


def test_staff_and_paying_members_are_never_auto_deleted(app):
    from app.models.circle import CirclePlan, CircleSubscription

    _inactive(app, "staff@example.invalid", role="editor")
    paid_id = _inactive(app, "paid@example.invalid")
    with app.app_context():
        plan = CirclePlan(name="P", slug="p2", price=10, currency="KES", status="active", billing_interval="monthly")
        db.session.add(plan)
        db.session.flush()
        db.session.add(CircleSubscription(user_id=paid_id, plan_id=plan.id, status="active", source="manual"))
        db.session.commit()
    with patch("app.services.email.send_email", return_value=True) as sent:
        assert _run(app)["inactive_accounts"]["warned"] == 0
    assert not sent.called


# --- settings / scheduling -----------------------------------------------------------------------


def test_settings_are_bounded_and_audited(client, app):
    with app.app_context():
        u = _user("settings@example.invalid", role="admin")
        db.session.commit()
        h = auth_headers(create_access_token(identity=u))
    current = client.get("/api/v1/admin/settings", headers=h).get_json()["data"]["retention"]
    assert current["values"]["analyticsEventsMonths"] == 14 and current["values"]["paymentRecordYears"] == 6
    assert current["unverifiedAccountsActive"] is True
    for bad in ({"paymentRecordYears": 5}, {"analyticsEventsMonths": 0}, {"authIpMonths": -1},
                {"contactInquiriesMonths": "24"}, {"nope": 1}):
        assert client.put("/api/v1/admin/settings", headers=h, json={"settings": {"retention": {"values": bad}}}
                          ).status_code == 422, bad
    ok = client.put("/api/v1/admin/settings", headers=h, json={"settings": {"retention": {"values": {
        "analyticsEventsMonths": 13}}}})
    assert ok.get_json()["data"]["retention"]["values"]["analyticsEventsMonths"] == 13
    with app.app_context():
        assert AuditLog.query.filter_by(action="settings.update", entity_id="retention").count() == 1


def test_daily_throttle_inside_the_maintenance_command(app):
    with app.app_context():
        assert svc.run_retention_if_due(NOW) is not None
        assert svc.run_retention_if_due(NOW + timedelta(hours=2)) is None
        assert svc.run_retention_if_due(NOW + timedelta(hours=24)) is not None


def test_logs_counts_only(app, caplog):
    with app.app_context():
        _user("private-person@example.invalid")
        db.session.commit()
    with caplog.at_level("INFO"):
        _run(app)
    assert "Retention run" in caplog.text and "private-person@example.invalid" not in caplog.text


def test_retention_cli(app):
    result = app.test_cli_runner().invoke(args=["retention-run", "--dry-run"])
    assert "analytics_events: 0" in result.output and "unverified_accounts: 0" in result.output
