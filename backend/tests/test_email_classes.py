"""Step 15: email classification, common footer, List-Unsubscribe (RFC 2369 /
RFC 8058 one-click), and honest reply-notification delivery state."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.extensions import db
from app.services import email as mail
from app.services.site_settings import save_site_identity


def _identity(app, address=None):
    with app.app_context():
        save_site_identity({"site_name": "Women Shaping Futures", "postal_address": address})
        db.session.commit()


def _text(message):
    return message.get_body(("plain",)).get_content()


def test_transactional_email_has_footer_and_no_unsubscribe(app):
    _identity(app, "Illustrative Street 1, Illustrative City")
    with app.test_request_context():
        msg = mail.build_message("a@example.invalid", "Reset your password", "Body", "<p>Body</p>")
    text = _text(msg)
    assert "Women Shaping Futures · Illustrative Street 1, Illustrative City · Privacy Policy: " in text
    assert text.rstrip().endswith("/privacy") and "Unsubscribe" not in text
    assert msg["List-Unsubscribe"] is None and msg["List-Unsubscribe-Post"] is None
    assert msg["X-WSF-Email-Class"] == "transactional"
    assert "Privacy Policy</a>" in msg.get_body(("html",)).get_content()


def test_blank_address_is_never_invented(app):
    _identity(app, None)
    with app.test_request_context():
        text = _text(mail.build_message("a@example.invalid", "S", "Body"))
    footer = text.split("--")[-1]
    assert footer.strip().startswith("Women Shaping Futures · Privacy Policy:")


def test_transactional_ignores_any_unsubscribe_arguments(app):
    with app.test_request_context():
        msg = mail.build_message("a@example.invalid", "Security", "Body", category=mail.TRANSACTIONAL,
                                 unsubscribe_url="https://x/u", one_click_url="https://x/o")
    assert msg["List-Unsubscribe"] is None and "Unsubscribe" not in _text(msg)


def test_optional_email_requires_and_carries_one_click_unsubscribe(app):
    with app.test_request_context():
        with pytest.raises(ValueError):
            mail.build_message("a@example.invalid", "S", "Body", category=mail.OPTIONAL)
        with pytest.raises(ValueError):
            mail.build_message("a@example.invalid", "S", "Body", category="marketing")
        msg = mail.build_message("a@example.invalid", "Reply", "Body", "<html><body><p>Hi</p></body></html>",
                                 category=mail.OPTIONAL, unsubscribe_url="https://wsf.example/comments/unsubscribe/t",
                                 one_click_url="https://wsf.example/api/v1/comments/notifications/one-click/t")
    assert msg["List-Unsubscribe"] == "<https://wsf.example/api/v1/comments/notifications/one-click/t>"
    assert msg["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert "Unsubscribe from these emails: https://wsf.example/comments/unsubscribe/t" in _text(msg)
    html = msg.get_body(("html",)).get_content()
    assert html.index("Unsubscribe from these emails") < html.index("</body>")


def test_every_caller_declares_its_class():
    import inspect

    from app.api.v1 import event_registrations, learning_enrollments
    from app.services import comments, newsletter, password_reset

    for module, expected in ((password_reset, "category=TRANSACTIONAL"), (event_registrations, "category=TRANSACTIONAL"),
                             (learning_enrollments, "category=TRANSACTIONAL"), (newsletter, "category=TRANSACTIONAL"),
                             (comments, "category=OPTIONAL")):
        assert expected in inspect.getsource(module), module.__name__


def test_smtp_failure_log_never_contains_the_address(app, caplog):
    app.config.update(EMAIL_BACKEND="smtp", SMTP_HOST="127.0.0.1", SMTP_PORT=1, SMTP_FROM_EMAIL="from@example.invalid")
    with app.app_context(), caplog.at_level("ERROR"):
        assert mail.send_email("private-person@example.invalid", "S", "Body") is False
    assert "private-person@example.invalid" not in caplog.text


# --- comment reply delivery state ----------------------------------------------------------------


@pytest.fixture()
def thread(app, client, monkeypatch):
    """A published top-level comment by an opted-in member and a published
    reply by someone else, with reply_notified_at still empty."""
    from app.models.article import Article
    from app.models.comment import Comment, CommentNotificationPreference
    from app.models.people import Author
    from app.models.user import User

    with app.app_context():
        author = Author(slug="ed", name="Ed")
        db.session.add(author)
        db.session.flush()
        article = Article(title="T", slug="t", status="published", content=[], author_id=author.id,
                          publish_date=datetime.now(timezone.utc) - timedelta(days=1))
        users = []
        for email in ("owner@example.invalid", "replier@example.invalid"):
            u = User(email=email, first_name="A", last_name="B", is_active=True)
            u.set_password("supersecret1")
            users.append(u)
        db.session.add_all([article, *users])
        db.session.flush()
        top = Comment(article_id=article.id, user_id=users[0].id, body="Top", status="published", held_reasons=[])
        db.session.add(top)
        db.session.flush()
        reply = Comment(article_id=article.id, user_id=users[1].id, parent_id=top.id, body="Reply",
                        status="published", held_reasons=[])
        db.session.add_all([reply, CommentNotificationPreference(user_id=users[0].id, reply_emails=True,
                                                                 unsubscribe_token="tok-1")])
        db.session.commit()
        return reply.id


def _notify(app, reply_id, result):
    from app.models.comment import Comment
    from app.services import comments

    calls = []
    with app.test_request_context(), patch("app.services.email.send_email",
                                           side_effect=lambda *a, **k: calls.append(k) or result):
        outcome = comments.notify_reply(db.session.get(Comment, reply_id))
        state = db.session.get(Comment, reply_id).reply_notified_at
    return outcome, state, calls


def test_successful_handoff_marks_notified_once(app, thread):
    outcome, state, calls = _notify(app, thread, True)
    assert outcome is True and state is not None and len(calls) == 1
    assert calls[0]["category"] == "optional"
    outcome, _, calls = _notify(app, thread, True)
    assert outcome is False and calls == []  # never twice


def test_smtp_failure_is_not_recorded_as_sent(app, thread):
    outcome, state, calls = _notify(app, thread, False)
    assert outcome is False and state is None and len(calls) == 1
    outcome, state, _ = _notify(app, thread, True)  # a later approval/restore can still deliver it
    assert outcome is True and state is not None


def test_not_eligible_sends_nothing_and_marks_nothing(app, thread):
    from app.models.comment import CommentNotificationPreference

    with app.app_context():
        CommentNotificationPreference.query.update({"reply_emails": False})
        db.session.commit()
    outcome, state, calls = _notify(app, thread, True)
    assert outcome is False and state is None and calls == []


def test_concurrent_claim_sends_once(app, thread):
    """Another request claims the reply between this request's in-memory
    check and its claim UPDATE: the conditional UPDATE matches no row, so
    this request sends nothing."""
    from app.models.comment import Comment
    from app.services import comments
    from app.services.comment_settings import get_comment_settings as real_settings

    def racing_settings():
        Comment.query.filter_by(id=thread).update({"reply_notified_at": datetime.now(timezone.utc)})
        db.session.commit()
        return real_settings()

    calls = []
    with app.test_request_context(), patch.object(comments, "get_comment_settings", side_effect=racing_settings), \
            patch("app.services.email.send_email", side_effect=lambda *a, **k: calls.append(1) or True):
        assert comments.notify_reply(db.session.get(Comment, thread)) is False
    assert calls == []


def test_one_click_unsubscribe_endpoint(client, app, thread):
    from app.models.comment import CommentNotificationPreference

    for _ in range(2):
        res = client.post("/api/v1/comments/notifications/one-click/tok-1", data="List-Unsubscribe=One-Click",
                          content_type="application/x-www-form-urlencoded")
        assert res.status_code == 200
    with app.app_context():
        assert CommentNotificationPreference.query.filter_by(unsubscribe_token="tok-1").one().reply_emails is False
    assert client.post("/api/v1/comments/notifications/one-click/nope").status_code == 404


def test_postal_address_is_plain_text_and_bounded(client, app):
    from flask_jwt_extended import create_access_token

    from app.models.user import Role, User
    from tests.conftest import auth_headers

    with app.app_context():
        u = User(email="settings@example.invalid", first_name="S", last_name="A", is_active=True)
        u.set_password("supersecret1")
        u.roles.append(Role.query.filter_by(name="admin").first())
        db.session.add(u)
        db.session.commit()
        h = auth_headers(create_access_token(identity=u))
    ok = client.put("/api/v1/admin/settings", headers=h, json={"settings": {"site_identity": {
        "siteName": "Women Shaping Futures", "postalAddress": "Illustrative Street 1"}}})
    assert ok.status_code == 200 and ok.get_json()["data"]["site_identity"]["postalAddress"] == "Illustrative Street 1"
    bad = client.put("/api/v1/admin/settings", headers=h, json={"settings": {"site_identity": {
        "siteName": "Women Shaping Futures", "postalAddress": "<b>x</b>"}}})
    assert bad.status_code == 422
