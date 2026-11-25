"""Article comments (Step 13): app/services/comments.py, app/api/v1/comments.py."""
import hashlib
from datetime import datetime, timedelta, timezone

import pytest
from flask_jwt_extended import create_access_token

from app.extensions import db
from app.models.article import Article
from app.models.audit import AuditLog
from app.models.comment import Comment, CommentEvent, CommentNotificationPreference, CommentReport
from app.models.people import Author
from app.models.user import Role, User
from app.services import comments as svc
from app.services.comment_settings import save_comment_settings
from tests.conftest import auth_headers

PASSWORD = "supersecret1"
BASE = "/api/v1/comments"


# --- fixtures / helpers ------------------------------------------------------------------------


class Clock:
    def __init__(self):
        self.offset = timedelta(0)

    def now(self):
        return datetime.now(timezone.utc) + self.offset


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    # Forms are "submitted" 5 s after they were issued unless a test says otherwise.
    c.offset = timedelta(seconds=5)
    monkeypatch.setattr(svc, "_now", c.now)
    return c


def _article(app, slug="a-story", mode="on", days=None, published_days_ago=1, status="published"):
    with app.app_context():
        author = Author.query.filter_by(slug="wsf-editorial").first()
        if author is None:
            author = Author(slug="wsf-editorial", name="WSF Editorial")
            db.session.add(author)
            db.session.flush()
        article = Article(title=f"Story {slug}", status=status, content=[], author_id=author.id, slug=slug,
                          comments_mode=mode, comments_close_after_days=days,
                          publish_date=(datetime.now(timezone.utc) - timedelta(days=published_days_ago))
                          if published_days_ago is not None else None)
        db.session.add(article)
        db.session.commit()
        return slug


def _member(client, email, display_name=None):
    res = client.post("/api/v1/auth/register", json={"email": email, "password": PASSWORD,
                                                     "first_name": "Ada", "last_name": email.split("@")[0]})
    data = res.get_json()["data"]
    if display_name:
        with client.application.app_context():
            user = db.session.get(User, data["user"]["id"])
            user.display_name = display_name
            db.session.commit()
    return data["access_token"], data["user"]["id"]


def _staff(app, email, role):
    with app.app_context():
        user = User(email=email, first_name="Mo", last_name="Derator", is_active=True)
        user.set_password(PASSWORD)
        user.roles.append(Role.query.filter_by(name=role).first())
        db.session.add(user)
        db.session.commit()
        return create_access_token(identity=user), user.id


def _settings(app, **values):
    with app.app_context():
        save_comment_settings(values)
        db.session.commit()


def _form(client, token, slug="a-story"):
    res = client.get(f"{BASE}/article/{slug}/form", headers=auth_headers(token))
    assert res.status_code == 200, res.get_json()
    return res.get_json()["data"]["formToken"]


def _post(client, token, body, slug="a-story", parent_id=None, website="", form=None, ip="203.0.113.7"):
    payload = {"body": body, "formToken": form or _form(client, token, slug), "website": website}
    if parent_id is not None:
        payload["parentId"] = parent_id
    return client.post(f"{BASE}/article/{slug}", json=payload, headers=auth_headers(token),
                       environ_base={"REMOTE_ADDR": ip})


def _thread(client, slug="a-story", token=None):
    res = client.get(f"{BASE}/article/{slug}", headers=auth_headers(token) if token else {})
    assert res.status_code == 200
    return res.get_json()["data"]


def _status(app, comment_id):
    with app.app_context():
        return db.session.get(Comment, comment_id).status


def _trusted(client, app, email, mod_token, display_name=None):
    """A member with enough approved comments to be trusted (threshold 1)."""
    _settings(app, trustedThreshold=1)
    token, uid = _member(client, email, display_name)
    cid = _post(client, token, f"My first thoughts, number {uid}.").get_json()["data"]["id"]
    assert client.post(f"/api/v1/admin/comments/{cid}/approve", headers=auth_headers(mod_token)).status_code == 200
    return token, uid


@pytest.fixture()
def mod(app):
    return _staff(app, "mod@example.invalid", "moderator")


# --- posting -----------------------------------------------------------------------------------


def test_anonymous_can_read_but_not_post(client, app, clock):
    _article(app)
    assert client.get(f"{BASE}/article/a-story").status_code == 200
    res = client.post(f"{BASE}/article/a-story", json={"body": "hi", "formToken": "x"})
    assert res.status_code == 401
    assert client.get(f"{BASE}/article/a-story/form").status_code == 401


def test_first_comment_is_held_and_visible_only_to_its_author(client, app, clock):
    _article(app)
    token, _uid = _member(client, "first@example.invalid")
    res = _post(client, token, "A thoughtful first comment.")
    assert res.status_code == 201
    assert res.get_json()["data"]["status"] == "pending"
    assert "approves" in res.get_json()["message"]
    assert _thread(client)["comments"] == []  # public: nothing
    mine = _thread(client, token=token)["comments"]
    assert len(mine) == 1 and mine[0]["status"] == "pending" and mine[0]["isOwn"] is True
    with app.app_context():
        assert db.session.get(Comment, res.get_json()["data"]["id"]).held_reasons == ["first_comment"]


def test_trusted_member_publishes_immediately(client, app, clock, mod):
    _article(app)
    token, _ = _trusted(client, app, "trusted@example.invalid", mod[0])
    res = _post(client, token, "Second comment, straight through.")
    assert res.get_json()["data"]["status"] == "published"
    assert [c["body"] for c in _thread(client)["comments"]][-1] == "Second comment, straight through."


def test_trust_threshold_is_studio_configurable(client, app, clock, mod):
    _article(app)
    _settings(app, trustedThreshold=2)
    token, _ = _member(client, "two@example.invalid")
    for i in range(2):
        cid = _post(client, token, f"Comment number {i}").get_json()["data"]["id"]
        client.post(f"/api/v1/admin/comments/{cid}/approve", headers=auth_headers(mod[0]))
    assert _post(client, token, "Now trusted").get_json()["data"]["status"] == "published"


def test_more_than_two_links_is_held_even_when_trusted(client, app, clock, mod):
    _article(app)
    token, _ = _trusted(client, app, "links@example.invalid", mod[0])
    two = _post(client, token, "See https://a.example.com and www.example.org for more.")
    assert two.get_json()["data"]["status"] == "published"
    three = _post(client, token, "Links: https://a.example.com, example.co.ke/page and www.b.org")
    assert three.get_json()["data"]["status"] == "pending"
    with app.app_context():
        assert "links" in db.session.get(Comment, three.get_json()["data"]["id"]).held_reasons


def test_link_counting_avoids_obvious_false_positives():
    assert svc.count_links("http is a protocol; e.g. Node.js 3.5 and the U.S.") == 0
    assert svc.count_links("https://x.org/a?b=c www.y.com z.co.ke/path") == 3
    assert svc.count_links("example.com") == 1


def test_blocked_word_holds_the_comment(client, app, clock, mod):
    _article(app)
    token, _ = _trusted(client, app, "words@example.invalid", mod[0])
    _settings(app, blockedWords=["scam*", "buy now"])
    held = _post(client, token, "This is a SCAMMER offer")
    assert held.get_json()["data"]["status"] == "pending"
    held2 = _post(client, token, "Please   Buy\nNow!")
    assert held2.get_json()["data"]["status"] == "pending"
    with app.app_context():
        assert db.session.get(Comment, held.get_json()["data"]["id"]) is not None  # never deleted
        assert "blocked_words" in db.session.get(Comment, held.get_json()["data"]["id"]).held_reasons


def test_blocked_word_matching_is_whole_word():
    assert svc.blocked_word_hits("A classic assistant", ["ass"]) == []
    assert svc.blocked_word_hits("you ASS!", ["ass"]) == ["ass"]
    assert svc.blocked_word_hits("scammers everywhere", ["scam"]) == []
    assert svc.blocked_word_hits("scammers everywhere", ["scam*"]) == ["scam*"]


def test_honeypot_is_rejected(client, app, clock):
    _article(app)
    token, _ = _member(client, "bot@example.invalid")
    res = _post(client, token, "Totally human", website="http://spam.example")
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "comment_rejected"
    with app.app_context():
        assert Comment.query.count() == 0


def test_too_fast_submission_is_rejected_and_token_cant_be_forged(client, app, clock):
    _article(app)
    token, _ = _member(client, "fast@example.invalid")
    form = _form(client, token)
    clock.offset = timedelta(seconds=0)
    res = _post(client, token, "Instant", form=form)
    assert res.status_code == 429 and res.get_json()["error"]["code"] == "comment_too_fast"
    res = _post(client, token, "Forged", form=form[:-3] + "abc")
    assert res.status_code == 400 and res.get_json()["error"]["code"] == "comment_form_invalid"
    clock.offset = timedelta(seconds=5)
    assert _post(client, token, "Took my time", form=form).status_code == 201


def test_form_token_is_bound_to_member_and_article(client, app, clock):
    _article(app)
    _article(app, slug="other-story")
    token, _ = _member(client, "bound@example.invalid")
    other, _ = _member(client, "other@example.invalid")
    form = _form(client, token)
    assert _post(client, other, "Not mine", form=form).get_json()["error"]["code"] == "comment_form_invalid"
    assert _post(client, token, "Wrong article", slug="other-story", form=form).status_code == 400


def test_duplicate_body_is_refused(client, app, clock):
    _article(app)
    token, _ = _member(client, "dupe@example.invalid")
    assert _post(client, token, "Same words").status_code == 201
    res = _post(client, token, "Same words")
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "comment_duplicate"


def test_create_is_rate_limited_per_account(client, app, clock):
    _article(app)
    token, _ = _member(client, "rate@example.invalid")
    forms = [_form(client, token) for _ in range(7)]
    codes = [_post(client, token, f"Comment {i}", form=forms[i]).status_code for i in range(7)]
    assert codes[:6] == [201] * 6 and codes[6] == 429
    # A different account on the same network still has its own budget.
    other, _ = _member(client, "rate2@example.invalid")
    assert _post(client, other, "My own budget").status_code == 201


def test_limits_are_the_prepared_values():
    from app.services.rate_limits import LIMITS

    assert LIMITS["comment_create"] == "6 per minute; 60 per day"
    assert LIMITS["comment_edit"] == "20 per minute"
    assert LIMITS["comment_report"] == "10 per minute; 50 per day"


def test_empty_and_overlong_bodies(client, app, clock):
    _article(app)
    token, _ = _member(client, "len@example.invalid")
    assert _post(client, token, "   ").get_json()["error"]["code"] == "comment_empty"
    assert _post(client, token, "x" * 5001).get_json()["error"]["code"] == "comment_too_long"


# --- replies -----------------------------------------------------------------------------------


def test_one_reply_level_and_reply_to_reply_joins_the_thread(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "a@example.invalid", mod[0])
    b, _ = _trusted(client, app, "b@example.invalid", mod[0])
    top = _post(client, a, "Top-level comment").get_json()["data"]["id"]
    reply = _post(client, b, "A reply", parent_id=top).get_json()["data"]["id"]
    nested = _post(client, a, "Reply to the reply", parent_id=reply).get_json()["data"]["id"]
    with app.app_context():
        assert db.session.get(Comment, reply).parent_id == top
        assert db.session.get(Comment, nested).parent_id == top  # never depth 2
    thread = [t for t in _thread(client)["comments"] if t["id"] == top][0]
    assert [r["body"] for r in thread["replies"]] == ["A reply", "Reply to the reply"]
    assert all(r["replies"] == [] for r in thread["replies"])


def test_parent_must_belong_to_the_same_published_article(client, app, clock, mod):
    _article(app)
    _article(app, slug="elsewhere")
    a, _ = _trusted(client, app, "pa@example.invalid", mod[0])
    other_top = _post(client, a, "On another article", slug="elsewhere").get_json()["data"]["id"]
    res = _post(client, a, "Cross-article reply", parent_id=other_top)
    assert res.status_code == 422 and res.get_json()["error"]["code"] == "comment_parent_invalid"
    assert _post(client, a, "Bad id", parent_id=999999).status_code == 422


def test_closed_article_blocks_new_comments_and_replies(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "closer@example.invalid", mod[0])
    top = _post(client, a, "Before closing").get_json()["data"]["id"]
    with app.app_context():
        Article.query.filter_by(slug="a-story").update({"comments_mode": "off"})
        db.session.commit()
    res = _post(client, a, "After closing", parent_id=top)
    assert res.status_code == 403 and res.get_json()["error"]["code"] == "comments_closed"
    data = _thread(client)
    assert data["open"] is False and data["state"] == "off"
    assert [c["body"] for c in data["comments"]][-1] == "Before closing"  # still readable


# --- article modes -----------------------------------------------------------------------------


def test_close_after_n_days(client, app, clock):
    _article(app, slug="young", mode="close_after", days=7, published_days_ago=3)
    _article(app, slug="old", mode="close_after", days=7, published_days_ago=8)
    _article(app, slug="undated", mode="close_after", days=7, published_days_ago=None)
    assert _thread(client, "young")["open"] is True
    assert _thread(client, "young")["closesAt"]
    assert _thread(client, "old")["state"] == "closed"
    assert _thread(client, "undated")["state"] == "closed"  # fails safe
    token, _ = _member(client, "late@example.invalid")
    assert _post(client, token, "Too late", slug="old").status_code == 403


def test_global_switch_disables_everywhere(client, app, clock):
    _article(app)
    _settings(app, enabled=False)
    assert _thread(client)["state"] == "disabled"
    token, _ = _member(client, "off@example.invalid")
    assert _post(client, token, "Nope").status_code == 403


def test_unpublished_article_has_no_comments_api(client, app, clock):
    _article(app, slug="draft-story", status="draft")
    assert client.get(f"{BASE}/article/draft-story").status_code == 404


def test_article_editor_saves_comment_mode(client, app):
    _article(app)
    token, _ = _staff(app, "ed@example.invalid", "editor")
    with app.app_context():
        aid = Article.query.filter_by(slug="a-story").first().id
    current = client.get("/api/v1/articles/a-story", headers=auth_headers(token)).get_json()["data"]
    base = {"title": current["title"], "authorSlug": "wsf-editorial", "status": "published",
            "content": [{"type": "paragraph", "text": "Body."}]}
    res = client.put("/api/v1/articles/a-story", headers=auth_headers(token),
                     json={**base, "commentsMode": "close_after"})
    assert res.status_code == 422  # days required
    res = client.put("/api/v1/articles/a-story", headers=auth_headers(token),
                     json={**base, "commentsMode": "close_after", "commentsCloseAfterDays": 30})
    assert res.status_code == 200, res.get_json()
    with app.app_context():
        art = db.session.get(Article, aid)
        assert (art.comments_mode, art.comments_close_after_days) == ("close_after", 30)


# --- editing -----------------------------------------------------------------------------------


def test_edit_own_within_15_minutes_shows_edited(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "edit@example.invalid", mod[0])
    cid = _post(client, a, "Original words").get_json()["data"]["id"]
    res = client.patch(f"{BASE}/{cid}", json={"body": "Better words"}, headers=auth_headers(a))
    assert res.status_code == 200 and res.get_json()["data"]["edited"] is True
    item = [c for c in _thread(client)["comments"] if c["id"] == cid][0]
    assert item["body"] == "Better words" and item["edited"] is True
    assert "Original words" not in str(_thread(client))  # no public edit history
    with app.app_context():
        ev = CommentEvent.query.filter_by(comment_id=cid, action="edited").one()
        assert "Original" not in str(ev.meta)


def test_edit_after_15_minutes_is_rejected_by_server_time(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "late-edit@example.invalid", mod[0])
    cid = _post(client, a, "Posted").get_json()["data"]["id"]
    clock.offset = timedelta(minutes=16)
    res = client.patch(f"{BASE}/{cid}", json={"body": "Too late"}, headers=auth_headers(a))
    assert res.status_code == 403 and res.get_json()["error"]["code"] == "comment_edit_window_closed"


def test_cannot_edit_or_delete_someone_elses_comment(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "own1@example.invalid", mod[0])
    b, _ = _member(client, "own2@example.invalid")
    cid = _post(client, a, "Mine").get_json()["data"]["id"]
    assert client.patch(f"{BASE}/{cid}", json={"body": "Hijack"}, headers=auth_headers(b)).status_code == 403
    assert client.delete(f"{BASE}/{cid}", headers=auth_headers(b)).status_code == 403
    assert _status(app, cid) == "published"


def test_edit_that_adds_links_goes_back_to_review(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "relink@example.invalid", mod[0])
    cid = _post(client, a, "Clean").get_json()["data"]["id"]
    client.patch(f"{BASE}/{cid}", json={"body": "a.com b.com c.com"}, headers=auth_headers(a))
    assert _status(app, cid) == "pending"


# --- deleting ----------------------------------------------------------------------------------


def test_delete_own_without_replies_disappears(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "del@example.invalid", mod[0])
    cid = _post(client, a, "Regrettable").get_json()["data"]["id"]
    assert client.delete(f"{BASE}/{cid}", headers=auth_headers(a)).status_code == 200
    assert cid not in [c["id"] for c in _thread(client)["comments"]]
    with app.app_context():
        row = db.session.get(Comment, cid)
        assert row.status == "deleted" and row.body is None
        assert CommentEvent.query.filter_by(comment_id=cid, action="deleted_by_author").count() == 1


def test_delete_with_replies_leaves_a_tombstone_without_the_text(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "tomb@example.invalid", mod[0])
    b, _ = _trusted(client, app, "tomb2@example.invalid", mod[0])
    top = _post(client, a, "Secret original text").get_json()["data"]["id"]
    _post(client, b, "A reply that stays", parent_id=top)
    client.delete(f"{BASE}/{top}", headers=auth_headers(a))
    data = _thread(client)
    item = [c for c in data["comments"] if c["id"] == top][0]
    assert item["placeholder"] is True and item["body"] == "Comment deleted" and item["author"] is None
    assert [r["body"] for r in item["replies"]] == ["A reply that stays"]
    assert "Secret original text" not in str(data)


def test_removed_comment_body_never_public(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "rm@example.invalid", mod[0])
    b, _ = _trusted(client, app, "rm2@example.invalid", mod[0])
    top = _post(client, a, "Offensive original").get_json()["data"]["id"]
    _post(client, b, "Reply", parent_id=top)
    client.post(f"/api/v1/admin/comments/{top}/remove", json={"reason": "Harassment"}, headers=auth_headers(mod[0]))
    data = _thread(client)
    assert "Offensive original" not in str(data)
    assert [c for c in data["comments"] if c["id"] == top][0]["body"] == "Comment removed"


# --- reporting ---------------------------------------------------------------------------------


@pytest.mark.parametrize("reason", ["spam", "harassment", "misinformation", "other"])
def test_each_report_reason(client, app, clock, mod, reason):
    _article(app)
    a, _ = _trusted(client, app, "rep@example.invalid", mod[0])
    b, _ = _member(client, "reporter@example.invalid")
    cid = _post(client, a, "Reportable").get_json()["data"]["id"]
    res = client.post(f"{BASE}/{cid}/report", json={"reason": reason, "details": "Context here"},
                      headers=auth_headers(b))
    assert res.status_code == 200
    with app.app_context():
        r = CommentReport.query.one()
        assert r.reason == reason and (r.details == "Context here") == (reason == "other")


def test_duplicate_and_own_reports_are_refused(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "dr@example.invalid", mod[0])
    b, _ = _member(client, "dr2@example.invalid")
    cid = _post(client, a, "Once").get_json()["data"]["id"]
    assert client.post(f"{BASE}/{cid}/report", json={"reason": "spam"}, headers=auth_headers(b)).status_code == 200
    res = client.post(f"{BASE}/{cid}/report", json={"reason": "other"}, headers=auth_headers(b))
    assert res.status_code == 409 and res.get_json()["error"]["code"] == "comment_already_reported"
    res = client.post(f"{BASE}/{cid}/report", json={"reason": "spam"}, headers=auth_headers(a))
    assert res.status_code == 422
    assert client.post(f"{BASE}/{cid}/report", json={"reason": "rude"}, headers=auth_headers(b)).status_code in (
        409, 422)
    with app.app_context():
        assert CommentReport.query.count() == 1


def test_unique_reports_auto_hide_once_at_the_threshold(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "hideme@example.invalid", mod[0])
    cid = _post(client, a, "Contentious").get_json()["data"]["id"]
    reporters = [_member(client, f"r{i}@example.invalid")[0] for i in range(4)]
    for t in reporters[:2]:
        client.post(f"{BASE}/{cid}/report", json={"reason": "spam"}, headers=auth_headers(t))
    assert _status(app, cid) == "published"
    client.post(f"{BASE}/{cid}/report", json={"reason": "harassment"}, headers=auth_headers(reporters[2]))
    assert _status(app, cid) == "hidden"
    res = client.post(f"{BASE}/{cid}/report", json={"reason": "spam"}, headers=auth_headers(reporters[3]))
    assert res.status_code == 409  # hidden: not reportable, no second auto-hide
    with app.app_context():
        events = CommentEvent.query.filter_by(comment_id=cid, action="auto_hidden").all()
        assert len(events) == 1 and events[0].actor_id is None and events[0].meta["threshold"] == 3
    assert cid not in [c["id"] for c in _thread(client)["comments"]]


def test_auto_hide_threshold_is_configurable(client, app, clock, mod):
    _article(app)
    a, _ = _trusted(client, app, "cfg@example.invalid", mod[0])
    _settings(app, reportHideThreshold=1)
    cid = _post(client, a, "One strike").get_json()["data"]["id"]
    b, _ = _member(client, "one@example.invalid")
    client.post(f"{BASE}/{cid}/report", json={"reason": "spam"}, headers=auth_headers(b))
    assert _status(app, cid) == "hidden"


def test_removed_or_pending_comments_cannot_be_reported(client, app, clock, mod):
    _article(app)
    a, _ = _member(client, "pend@example.invalid")
    b, _ = _member(client, "pend2@example.invalid")
    cid = _post(client, a, "Waiting").get_json()["data"]["id"]
    assert client.post(f"{BASE}/{cid}/report", json={"reason": "spam"}, headers=auth_headers(b)).status_code == 409


# --- moderation --------------------------------------------------------------------------------


def test_moderation_queue_actions_history_and_audit(client, app, clock, mod):
    _article(app)
    a, _ = _member(client, "q@example.invalid")
    cid = _post(client, a, "Please approve me").get_json()["data"]["id"]
    h = auth_headers(mod[0])
    queue = client.get("/api/v1/admin/comments?queue=pending", headers=h).get_json()["data"]
    assert [c["id"] for c in queue["items"]] == [cid] and queue["counts"]["pending"] == 1
    assert queue["items"][0]["heldReasons"] == ["first_comment"]
    assert "q@example.invalid" not in str(queue) and not any("ip" in k.lower() for k in queue["items"][0])
    assert client.post(f"/api/v1/admin/comments/{cid}/approve", headers=h).get_json()["data"]["status"] == "published"
    assert client.post(f"/api/v1/admin/comments/{cid}/hide", json={"reason": "Checking"},
                       headers=h).get_json()["data"]["status"] == "hidden"
    assert client.post(f"/api/v1/admin/comments/{cid}/approve", headers=h).get_json()["data"]["status"] == "published"
    assert client.post(f"/api/v1/admin/comments/{cid}/remove", json={}, headers=h).status_code == 422  # reason needed
    assert client.post(f"/api/v1/admin/comments/{cid}/remove", json={"reason": "Off-topic"},
                       headers=h).get_json()["data"]["removalReason"] == "Off-topic"
    detail = client.get(f"/api/v1/admin/comments/{cid}", headers=h).get_json()["data"]
    assert [e["action"] for e in detail["history"]] == ["created", "approved", "hidden", "restored", "removed"]
    with app.app_context():
        actions = [r.action for r in AuditLog.query.filter_by(entity_type="Comment", entity_id=str(cid))
                   .order_by(AuditLog.id).all()]
        assert actions == ["comment.approve", "comment.hide", "comment.restore", "comment.remove"]
        assert all("Please approve me" not in str(r.changes) for r in AuditLog.query.all())


def test_members_cannot_moderate_or_see_history(client, app, clock):
    _article(app)
    a, _ = _member(client, "nomod@example.invalid")
    cid = _post(client, a, "Mine").get_json()["data"]["id"]
    h = auth_headers(a)
    assert client.get("/api/v1/admin/comments", headers=h).status_code == 403
    assert client.get(f"/api/v1/admin/comments/{cid}", headers=h).status_code == 403
    for action in ("approve", "hide", "remove"):
        assert client.post(f"/api/v1/admin/comments/{cid}/{action}", json={"reason": "x"}, headers=h).status_code == 403
    assert client.post(f"/api/v1/admin/comments/users/1/restrict", json={"kind": "ban", "reason": "x"},
                       headers=h).status_code == 403
    assert _status(app, cid) == "pending"


def test_editor_and_admin_can_moderate_but_author_role_cannot(client, app, clock):
    for role, expected in (("editor", 200), ("admin", 200), ("moderator", 200), ("author", 403)):
        token, _ = _staff(app, f"{role}-mod@example.invalid", role)
        assert client.get("/api/v1/admin/comments", headers=auth_headers(token)).status_code == expected


# --- suspension / ban --------------------------------------------------------------------------


def test_suspension_and_ban_block_participation_but_not_the_account(client, app, clock, mod):
    _article(app)
    a, uid = _trusted(client, app, "restricted@example.invalid", mod[0])
    existing = _post(client, a, "Published before the ban").get_json()["data"]["id"]
    other, _ = _trusted(client, app, "victim@example.invalid", mod[0])
    target = _post(client, other, "Something to report").get_json()["data"]["id"]
    h = auth_headers(mod[0])
    res = client.post(f"/api/v1/admin/comments/users/{uid}/restrict", json={"kind": "suspension", "days": 7,
                                                                            "reason": "Cooling off"}, headers=h)
    assert res.status_code == 200 and res.get_json()["data"]["restriction"]["kind"] == "suspension"
    res = _post(client, a, "Trying anyway")
    assert res.status_code == 403 and res.get_json()["error"]["code"] == "comment_suspended"
    assert client.post(f"{BASE}/{target}/report", json={"reason": "spam"}, headers=auth_headers(a)).status_code == 403
    assert client.patch(f"{BASE}/{existing}", json={"body": "edit"}, headers=auth_headers(a)).status_code == 403
    client.post(f"/api/v1/admin/comments/users/{uid}/restrict", json={"kind": "ban", "reason": "Repeated abuse"},
                headers=h)
    res = _post(client, a, "Still trying")
    assert res.status_code == 403 and res.get_json()["error"]["code"] == "comment_banned"
    assert client.get("/api/v1/auth/me", headers=auth_headers(a)).status_code == 200  # account still works
    assert _status(app, existing) == "published"  # existing comments untouched
    assert _thread(client, token=a)["viewer"]["restriction"]["kind"] == "ban"
    assert client.post(f"/api/v1/admin/comments/users/{uid}/lift", headers=h).status_code == 200
    assert _post(client, a, "Back again").status_code == 201
    with app.app_context():
        assert [r.action for r in AuditLog.query.filter_by(entity_type="User", entity_id=str(uid))
                .order_by(AuditLog.id).all() if r.action.startswith("comment_user.")] == [
            "comment_user.suspend", "comment_user.ban", "comment_user.lift"]
        assert [e.action for e in CommentEvent.query.filter_by(subject_user_id=uid, comment_id=None)
                .order_by(CommentEvent.id).all()] == ["user_suspended", "user_banned", "user_restriction_lifted"]


def test_suspension_ends_by_itself(client, app, clock, mod):
    _article(app)
    a, uid = _member(client, "timed@example.invalid")
    client.post(f"/api/v1/admin/comments/users/{uid}/restrict", json={"kind": "suspension", "days": 1,
                                                                      "reason": "Short"},
                headers=auth_headers(mod[0]))
    clock.offset = timedelta(days=1, minutes=1)
    assert _post(client, a, "After the suspension").status_code == 201


# --- notifications -----------------------------------------------------------------------------


def _outbox(monkeypatch):
    sent = []
    import app.services.email as email

    # Registration now also sends an email-verification link (Batch 4
    # corrections); this outbox is for comment notifications only.
    monkeypatch.setattr(email, "send_email",
                        lambda to, subject, text, html=None, **kw: (
                            None if subject.startswith("Confirm your email address") else sent.append((to, subject, text, kw))
                        ) or True)
    return sent


def test_reply_emails_are_opt_in_and_unsubscribable(client, app, clock, mod, monkeypatch):
    _article(app)
    sent = _outbox(monkeypatch)
    a, a_id = _trusted(client, app, "author@example.invalid", mod[0])
    b, _ = _trusted(client, app, "replier@example.invalid", mod[0], display_name="Bea")
    top = _post(client, a, "Top").get_json()["data"]["id"]
    assert client.get(f"{BASE}/notifications", headers=auth_headers(a)).get_json()["data"]["replyEmails"] is False
    _post(client, b, "Reply while not opted in", parent_id=top)
    assert sent == []  # off by default
    assert client.put(f"{BASE}/notifications", json={"replyEmails": True},
                      headers=auth_headers(a)).get_json()["data"]["replyEmails"] is True
    _post(client, b, "Reply after opting in", parent_id=top)
    assert len(sent) == 1 and sent[0][0] == "author@example.invalid"
    with app.app_context():
        token = db.session.get(CommentNotificationPreference, a_id).unsubscribe_token
    assert "Bea replied" in sent[0][2]
    assert sent[0][3]["category"] == "optional"
    assert sent[0][3]["unsubscribe_url"].endswith(f"/comments/unsubscribe/{token}")
    assert sent[0][3]["one_click_url"].endswith(f"/api/v1/comments/notifications/one-click/{token}")
    for _ in range(2):  # idempotent, works signed out
        assert client.post(f"{BASE}/notifications/unsubscribe", json={"token": token}).status_code == 200
    assert client.post(f"{BASE}/notifications/unsubscribe", json={"token": "nope"}).status_code == 404
    _post(client, b, "Reply after unsubscribing", parent_id=top)
    assert len(sent) == 1


def test_reply_email_sent_on_approval_once_and_never_to_self(client, app, clock, mod, monkeypatch):
    _article(app)
    sent = _outbox(monkeypatch)
    a, _ = _trusted(client, app, "self@example.invalid", mod[0])
    client.put(f"{BASE}/notifications", json={"replyEmails": True}, headers=auth_headers(a))
    top = _post(client, a, "Top").get_json()["data"]["id"]
    _post(client, a, "Replying to myself", parent_id=top)
    assert sent == []
    newbie, _ = _member(client, "newbie@example.invalid")
    pending = _post(client, newbie, "Held reply", parent_id=top).get_json()["data"]["id"]
    assert sent == []
    client.post(f"/api/v1/admin/comments/{pending}/approve", headers=auth_headers(mod[0]))
    client.post(f"/api/v1/admin/comments/{pending}/hide", headers=auth_headers(mod[0]))
    client.post(f"/api/v1/admin/comments/{pending}/approve", headers=auth_headers(mod[0]))
    assert len(sent) == 1


# --- IP hash -----------------------------------------------------------------------------------


def test_ip_is_only_stored_as_a_keyed_hash_for_90_days(client, app, clock):
    _article(app)
    token, _ = _member(client, "ip@example.invalid")
    cid = _post(client, token, "Hello", ip="198.51.100.23").get_json()["data"]["id"]
    with app.app_context():
        row = db.session.get(Comment, cid)
        assert row.ip_hash and "198.51.100.23" not in row.ip_hash
        assert row.ip_hash != hashlib.sha256(b"198.51.100.23").hexdigest()  # not a plain hash
        assert row.ip_hash == svc.hash_ip("198.51.100.23") == svc.hash_ip("::ffff:198.51.100.23")
        assert svc.hash_ip("198.51.100.24") != row.ip_hash
        expires = row.ip_hash_expires_at
        created = row.created_at
        assert abs((expires - created) - timedelta(days=90)) < timedelta(minutes=1)
        columns = {c.name for c in Comment.__table__.columns}
        assert not {"ip", "ip_address", "raw_ip"} & columns
    payload = str(_thread(client, token=token))
    assert "198.51.100.23" not in payload and "ip_hash" not in payload and "ipHash" not in payload


def test_expired_ip_hashes_are_cleared_idempotently(client, app, clock):
    _article(app)
    token, _ = _member(client, "purge@example.invalid")
    cid = _post(client, token, "Hello").get_json()["data"]["id"]
    with app.app_context():
        assert svc.purge_expired_ip_hashes() == 0
        assert svc.purge_expired_ip_hashes(datetime.now(timezone.utc) + timedelta(days=91)) == 1
        assert svc.purge_expired_ip_hashes(datetime.now(timezone.utc) + timedelta(days=91)) == 0
        row = db.session.get(Comment, cid)
        assert row.ip_hash is None and row.ip_hash_expires_at is None and row.body == "Hello"


def test_purge_cli(app):
    result = app.test_cli_runner().invoke(args=["comments-purge-ip-hashes"])
    assert "Cleared 0 expired comment IP hash(es)." in result.output


# --- privacy of payloads -----------------------------------------------------------------------


def test_public_payload_never_exposes_email_ip_or_user_id(client, app, clock, mod):
    _article(app)
    a, uid = _trusted(client, app, "private@example.invalid", mod[0], display_name="Private Person")
    _post(client, a, "Public words")
    data = _thread(client)
    text = str(data)
    assert "private@example.invalid" not in text and "ip_hash" not in text and "203.0.113.7" not in text
    item = data["comments"][-1]
    assert item["author"] == {"name": "Private Person", "avatarUrl": None, "formerMember": False}
    assert "userId" not in str(item) and "heldReasons" not in str(item)


# --- account deletion / export readiness -------------------------------------------------------


def test_comments_survive_account_deletion_as_former_member(client, app, clock, mod):
    _article(app)
    a, a_id = _trusted(client, app, "leaving@example.invalid", mod[0])
    b, _ = _trusted(client, app, "staying@example.invalid", mod[0])
    top = _post(client, a, "I was here").get_json()["data"]["id"]
    _post(client, b, "Reply to someone leaving", parent_id=top)
    with app.app_context():
        svc.detach_user_comments(a_id)
        # Batch 4 decides what happens to the account's audit entries; here
        # they are only detached so the users row can go.
        AuditLog.query.filter_by(user_id=a_id).update({"user_id": None})
        db.session.delete(db.session.get(User, a_id))
        db.session.commit()
        row = db.session.get(Comment, top)
        assert row.user_id is None and row.ip_hash is None and row.body == "I was here"
    item = [c for c in _thread(client)["comments"] if c["id"] == top][0]
    assert item["author"]["name"] == "Former member" and item["author"]["formerMember"] is True
    assert [r["body"] for r in item["replies"]] == ["Reply to someone leaving"]


def test_also_remove_my_comments_keeps_threads(client, app, clock, mod):
    _article(app)
    a, a_id = _trusted(client, app, "erase@example.invalid", mod[0])
    b, _ = _trusted(client, app, "keep@example.invalid", mod[0])
    top = _post(client, a, "Erase me").get_json()["data"]["id"]
    _post(client, b, "Kept reply", parent_id=top)
    with app.app_context():
        svc.detach_user_comments(a_id, remove=True)
        db.session.commit()
    data = _thread(client)
    assert "Erase me" not in str(data)
    assert [c for c in data["comments"] if c["id"] == top][0]["body"] == "Comment deleted"


def test_export_returns_only_own_comments(client, app, clock, mod):
    _article(app)
    a, a_id = _trusted(client, app, "export@example.invalid", mod[0])
    b, _ = _trusted(client, app, "notme@example.invalid", mod[0])
    _post(client, a, "Mine to export")
    _post(client, b, "Not mine")
    with app.app_context():
        rows = svc.comments_for_export(db.session.get(User, a_id))
    bodies = [r["body"] for r in rows]
    assert "Mine to export" in bodies and "Not mine" not in bodies
    assert all("ip" not in k.lower() for r in rows for k in r)


# --- settings ----------------------------------------------------------------------------------


def test_studio_settings_validate_and_audit(client, app):
    token, _ = _staff(app, "settings@example.invalid", "admin")
    h = auth_headers(token)
    current = client.get("/api/v1/admin/settings", headers=h).get_json()["data"]["comments"]
    assert current["reportHideThreshold"] == 3 and current["blockedWords"] == []
    bad = client.put("/api/v1/admin/settings", json={"settings": {"comments": {"reportHideThreshold": 0}}}, headers=h)
    assert bad.status_code == 422
    bad = client.put("/api/v1/admin/settings", json={"settings": {"comments": {"surprise": 1}}}, headers=h)
    assert bad.status_code == 422
    ok = client.put("/api/v1/admin/settings", headers=h, json={"settings": {"comments": {
        "reportHideThreshold": 5, "blockedWords": ["Spam", "spam", " buy  now "], "minSubmitSeconds": 4}}})
    saved = ok.get_json()["data"]["comments"]
    assert saved["reportHideThreshold"] == 5 and saved["blockedWords"] == ["Spam", "buy now"]
    with app.app_context():
        entry = AuditLog.query.filter_by(action="settings.update", entity_id="comments").one()
        assert entry.changes["blockedWordsCount"] == 2 and "blockedWords" not in entry.changes
    member, _ = _member(client, "nosettings@example.invalid")
    assert client.put("/api/v1/admin/settings", json={"settings": {"comments": {"enabled": False}}},
                      headers=auth_headers(member)).status_code == 403


def test_unsubscribe_link_is_served_as_a_noindex_token_free_page(client, app):
    from tests.test_spa_shell import FIXTURE_INDEX_PATH

    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    res = client.get("/comments/unsubscribe/some-secret-token")
    html = res.get_data(as_text=True)
    assert res.status_code == 200
    assert "noindex" in html and "some-secret-token" not in html


def test_ip_hash_key_is_configurable_and_never_the_secret_key(app):
    with app.app_context():
        derived = svc.hash_ip("192.0.2.1")
        app.config["COMMENT_IP_HASH_KEY"] = "a-separate-comment-key"
        configured = svc.hash_ip("192.0.2.1")
        import hmac as _hmac

        plain_secret = _hmac.new(app.config["SECRET_KEY"].encode(), b"192.0.2.1", hashlib.sha256).hexdigest()
        assert derived != configured and derived != plain_secret
        assert svc.hash_ip("not-an-ip") is None and svc.hash_ip(None) is None
