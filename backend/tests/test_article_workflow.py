"""Editorial workflow + scheduled publishing (draft -> in_review ->
changes_requested/approved -> scheduled -> published -> archived). See
app/services/articles_workflow.py for the transition rules and scheduler
this exercises.
"""
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

EDITOR_PAYLOAD = {
    "email": "workflow-editor@example.com",
    "password": "supersecret1",
    "first_name": "Wanjiru",
    "last_name": "Editor",
}
AUTHOR_USER_PAYLOAD = {
    "email": "workflow-author@example.com",
    "password": "supersecret1",
    "first_name": "Amina",
    "last_name": "Writer",
}


@pytest.fixture()
def editor_token(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=EDITOR_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=EDITOR_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="editor").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": EDITOR_PAYLOAD["email"], "password": EDITOR_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


SUPER_ADMIN_PAYLOAD = {
    "email": "workflow-super-admin@example.com",
    "password": "supersecret1",
    "first_name": "Root",
    "last_name": "Admin",
}


@pytest.fixture()
def super_admin_token(client, app):
    """A `super_admin` user — seeded with every Permission row via the "*"
    expansion in rbac.py's seed_roles_and_permissions(), rather than an
    explicit permission list like every other role. Used to prove the
    editorial-workflow audit's finding in code: super_admin already holds
    articles.manage/articles.publish and can walk the full workflow
    unassisted, exactly like an editor token — it's just gated by the same
    one-step-at-a-time state machine as everyone else, not missing any
    permission.
    """
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=SUPER_ADMIN_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=SUPER_ADMIN_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="super_admin").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": SUPER_ADMIN_PAYLOAD["email"], "password": SUPER_ADMIN_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def author_user_token(client, app):
    """A plain "author" role — articles.create/edit_own only, no manage/
    publish — used to assert the weaker tier can submit-review its own
    work but never approve/schedule/publish/archive.
    """
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=AUTHOR_USER_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=AUTHOR_USER_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="author").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": AUTHOR_USER_PAYLOAD["email"], "password": AUTHOR_USER_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def author_slug(client, editor_token):
    resp = client.post(
        "/api/v1/authors",
        json={"name": "Byline Author", "role": "Contributor", "countryCode": "NG"},
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["slug"]


def _create_draft(client, token, author_slug, title="Workflow Draft Article"):
    resp = client.post(
        "/api/v1/articles",
        json={
            "title": title,
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Body text."}],
        },
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    return resp.get_json()["data"]["slug"]


def _future_iso(seconds=3600):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_full_workflow_happy_path(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)

    submit = client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))
    assert submit.status_code == 200
    assert submit.get_json()["data"]["status"] == "in_review"

    approve = client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))
    assert approve.status_code == 200
    approved_data = approve.get_json()["data"]
    assert approved_data["status"] == "approved"
    assert approved_data["approved_at"] is not None
    assert approved_data["approved_by"]["email"] == EDITOR_PAYLOAD["email"]

    scheduled_at = _future_iso()
    schedule = client.post(
        f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": scheduled_at}, headers=auth_headers(editor_token)
    )
    assert schedule.status_code == 200
    assert schedule.get_json()["data"]["status"] == "scheduled"
    assert schedule.get_json()["data"]["scheduled_at"] is not None

    # Scheduled content must never be publicly visible before publication.
    hidden = client.get(f"/api/v1/articles/{slug}")
    assert hidden.status_code == 404
    public_list = client.get("/api/v1/articles")
    assert not any(a["slug"] == slug for a in public_list.get_json()["data"])

    unschedule = client.post(f"/api/v1/articles/{slug}/unschedule", headers=auth_headers(editor_token))
    assert unschedule.status_code == 200
    assert unschedule.get_json()["data"]["status"] == "approved"
    assert unschedule.get_json()["data"]["scheduled_at"] is None

    publish = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert publish.status_code == 200
    assert publish.get_json()["data"]["status"] == "published"
    assert publish.get_json()["data"]["publish_date"] is not None

    public = client.get(f"/api/v1/articles/{slug}")
    assert public.status_code == 200

    archive = client.post(f"/api/v1/articles/{slug}/archive", headers=auth_headers(editor_token))
    assert archive.status_code == 200
    assert archive.get_json()["data"]["status"] == "archived"

    # Archived must leave the DB record/revisions/audit trail intact but
    # drop out of public eligibility.
    archived_public = client.get(f"/api/v1/articles/{slug}")
    assert archived_public.status_code == 404


def test_request_changes_and_return_to_draft(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))

    rejected = client.post(
        f"/api/v1/articles/{slug}/request-changes",
        json={"note": "Please add a stronger lede."},
        headers=auth_headers(editor_token),
    )
    assert rejected.status_code == 200
    assert rejected.get_json()["data"]["status"] == "changes_requested"

    back_to_draft = client.post(f"/api/v1/articles/{slug}/move-to-draft", headers=auth_headers(editor_token))
    assert back_to_draft.status_code == 200
    assert back_to_draft.get_json()["data"]["status"] == "draft"

    with client.application.app_context():
        from app.models.audit import AuditLog

        entry = AuditLog.query.filter_by(action="article.request_changes").first()
        assert entry is not None
        assert entry.changes.get("note") == "Please add a stronger lede."
        # Never a full Article body in the audit trail.
        assert "content" not in entry.changes


# ---------------------------------------------------------------------------
# Super Admin — proves the editorial-workflow audit's finding: super_admin
# already holds articles.manage/articles.publish and can walk the full
# workflow unassisted, identically to an editor token. No other workflow
# test in this file uses a super_admin token, which was a real coverage
# gap the audit flagged — this closes it without changing any RBAC/
# transition code.
# ---------------------------------------------------------------------------


def test_super_admin_can_submit_approve_and_publish(client, super_admin_token, author_slug):
    slug = _create_draft(client, super_admin_token, author_slug, title="Super Admin Direct Publish")

    submit = client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(super_admin_token))
    assert submit.status_code == 200
    assert submit.get_json()["data"]["status"] == "in_review"

    approve = client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(super_admin_token))
    assert approve.status_code == 200
    assert approve.get_json()["data"]["status"] == "approved"

    publish = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(super_admin_token))
    assert publish.status_code == 200
    assert publish.get_json()["data"]["status"] == "published"

    public = client.get(f"/api/v1/articles/{slug}")
    assert public.status_code == 200


def test_super_admin_can_schedule_and_publish(client, super_admin_token, author_slug):
    slug = _create_draft(client, super_admin_token, author_slug, title="Super Admin Scheduled Publish")
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(super_admin_token))
    client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(super_admin_token))

    schedule = client.post(
        f"/api/v1/articles/{slug}/schedule",
        json={"scheduledAt": _future_iso()},
        headers=auth_headers(super_admin_token),
    )
    assert schedule.status_code == 200
    assert schedule.get_json()["data"]["status"] == "scheduled"

    publish = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(super_admin_token))
    assert publish.status_code == 200
    assert publish.get_json()["data"]["status"] == "published"


# ---------------------------------------------------------------------------
# Invalid transitions
# ---------------------------------------------------------------------------


def test_cannot_approve_a_draft(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    resp = client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "invalid_transition"


def test_cannot_schedule_without_approval(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))
    resp = client.post(
        f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": _future_iso()}, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 409


def test_cannot_publish_directly_from_draft(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    resp = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "invalid_transition"


def test_publish_is_idempotent(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))
    client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))
    first = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert first.status_code == 200
    second = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(editor_token))
    assert second.status_code == 200  # no-op, not a 409

    with client.application.app_context():
        from app.models.audit import AuditLog

        publish_events = AuditLog.query.filter_by(action="article.publish").count()
        assert publish_events == 1  # the idempotent replay logged nothing new


def test_cannot_archive_unpublished_article(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    resp = client.post(f"/api/v1/articles/{slug}/archive", headers=auth_headers(editor_token))
    assert resp.status_code == 409


def test_ordinary_save_cannot_change_status(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))
    client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))

    resp = client.put(
        f"/api/v1/articles/{slug}",
        json={
            "title": "Workflow Draft Article",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Edited body."}],
            "status": "published",
        },
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "invalid_transition"

    # But an ordinary save that echoes the current status through (no-op)
    # succeeds and keeps the article approved — editing shouldn't silently
    # revert or advance status.
    ok = client.put(
        f"/api/v1/articles/{slug}",
        json={
            "title": "Workflow Draft Article",
            "authorSlug": author_slug,
            "content": [{"type": "paragraph", "text": "Edited body."}],
            "status": "approved",
        },
        headers=auth_headers(editor_token),
    )
    assert ok.status_code == 200
    assert ok.get_json()["data"]["status"] == "approved"


def test_new_article_cannot_be_created_in_a_workflow_status_directly(client, editor_token, author_slug):
    resp = client.post(
        "/api/v1/articles",
        json={
            "title": "Sneaky Direct Approval",
            "authorSlug": author_slug,
            "status": "approved",
            "content": [{"type": "paragraph", "text": "Body."}],
        },
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "invalid_status"


# ---------------------------------------------------------------------------
# Scheduling validation
# ---------------------------------------------------------------------------


def _approved_article(client, editor_token, author_slug, title="Approved For Scheduling"):
    slug = _create_draft(client, editor_token, author_slug, title=title)
    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))
    client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))
    return slug


def test_schedule_rejects_past_datetime(client, editor_token, author_slug):
    slug = _approved_article(client, editor_token, author_slug)
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    resp = client.post(f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": past}, headers=auth_headers(editor_token))
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "invalid_schedule"


def test_schedule_rejects_naive_datetime(client, editor_token, author_slug):
    slug = _approved_article(client, editor_token, author_slug)
    naive = (datetime.now() + timedelta(hours=1)).isoformat()  # no tzinfo
    resp = client.post(
        f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": naive}, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 422


def test_reschedule_changes_time_and_logs(client, editor_token, author_slug):
    slug = _approved_article(client, editor_token, author_slug)
    first_time = _future_iso(3600)
    client.post(f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": first_time}, headers=auth_headers(editor_token))

    second_time = _future_iso(7200)
    resp = client.post(
        f"/api/v1/articles/{slug}/reschedule", json={"scheduledAt": second_time}, headers=auth_headers(editor_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["status"] == "scheduled"

    with client.application.app_context():
        from app.models.audit import AuditLog

        entry = AuditLog.query.filter_by(action="article.reschedule").first()
        assert entry is not None
        assert entry.changes["previous_scheduled_at"] is not None
        assert entry.changes["scheduled_at"] is not None


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------


def test_unauthenticated_cannot_call_workflow_actions(client, editor_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    resp = client.post(f"/api/v1/articles/{slug}/submit-review")
    assert resp.status_code == 401


def test_author_cannot_approve_or_schedule_or_publish(client, editor_token, author_user_token, author_slug):
    slug = _create_draft(client, editor_token, author_slug)
    # Owner-level access (submit-review) is fine for an editor; a bare
    # "author" role has no ownership tie to this article (different
    # created_by_id/byline) and no articles.manage, so even submit-review
    # is forbidden here — proving the weaker tier is properly gated too.
    forbidden_submit = client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(author_user_token))
    assert forbidden_submit.status_code == 403

    client.post(f"/api/v1/articles/{slug}/submit-review", headers=auth_headers(editor_token))
    forbidden_approve = client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(author_user_token))
    assert forbidden_approve.status_code == 403

    client.post(f"/api/v1/articles/{slug}/approve", headers=auth_headers(editor_token))
    forbidden_schedule = client.post(
        f"/api/v1/articles/{slug}/schedule",
        json={"scheduledAt": _future_iso()},
        headers=auth_headers(author_user_token),
    )
    assert forbidden_schedule.status_code == 403

    forbidden_publish = client.post(f"/api/v1/articles/{slug}/publish", headers=auth_headers(author_user_token))
    assert forbidden_publish.status_code == 403


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------


def test_scheduler_publishes_due_articles_and_is_idempotent(client, editor_token, author_slug):
    slug = _approved_article(client, editor_token, author_slug, title="Due For Publication")
    future_time = _future_iso(3600)
    client.post(
        f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": future_time}, headers=auth_headers(editor_token)
    )

    with client.application.app_context():
        from app.extensions import db
        from app.models.article import Article
        from app.services.articles_workflow import publish_due_articles

        article = Article.query.filter_by(slug=slug).first()
        # Deterministic time control instead of a real sleep: directly
        # back-date scheduled_at into the past so it's due right now.
        due_time = datetime.now(timezone.utc) - timedelta(minutes=1)
        article.scheduled_at = due_time
        db.session.commit()

        result = publish_due_articles()
        assert result["published"] == [article.id]
        assert result["skipped"] == []
        assert result["failed"] == []

        db.session.refresh(article)
        assert article.status == "published"
        assert article.publish_date == due_time

        from app.models.audit import AuditLog

        auto_entry = AuditLog.query.filter_by(action="article.publish_automatic", entity_id=str(article.id)).first()
        assert auto_entry is not None
        # System-attributed, never a fabricated staff user.
        assert auto_entry.user_id is None

        # A second run must be a safe, harmless no-op — the article is no
        # longer "scheduled" at all, so it's not even a candidate anymore.
        second_result = publish_due_articles()
        assert second_result["published"] == []
        assert second_result["skipped"] == []

    public = client.get(f"/api/v1/articles/{slug}")
    assert public.status_code == 200
    assert public.get_json()["data"]["status"] == "published"


def test_scheduler_skips_future_and_non_scheduled_articles(client, editor_token, author_slug):
    future_slug = _approved_article(client, editor_token, author_slug, title="Not Due Yet")
    client.post(
        f"/api/v1/articles/{future_slug}/schedule",
        json={"scheduledAt": _future_iso(7200)},
        headers=auth_headers(editor_token),
    )
    draft_slug = _create_draft(client, editor_token, author_slug, title="Still A Draft")

    with client.application.app_context():
        from app.services.articles_workflow import publish_due_articles

        result = publish_due_articles()
        assert result["published"] == []
        assert result["failed"] == []


def test_cli_publish_due_content_reports_counts(client, editor_token, author_slug, app):
    slug = _approved_article(client, editor_token, author_slug, title="CLI Due Article")
    client.post(
        f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": _future_iso()}, headers=auth_headers(editor_token)
    )

    with app.app_context():
        from app.extensions import db
        from app.models.article import Article

        article = Article.query.filter_by(slug=slug).first()
        article.scheduled_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=["publish-due-content"])
    assert result.exit_code == 0
    assert "Published 1" in result.output

    # Safe/idempotent on immediate re-run.
    second = runner.invoke(args=["publish-due-content"])
    assert second.exit_code == 0
    assert "Published 0" in second.output

    # Safe on zero rows from a clean slate too.
    empty = runner.invoke(args=["publish-due-content"])
    assert empty.exit_code == 0


# ---------------------------------------------------------------------------
# Calendar API
# ---------------------------------------------------------------------------


def test_calendar_requires_date_range_and_auth(client, editor_token):
    unauth = client.get("/api/v1/articles/calendar")
    assert unauth.status_code == 401

    missing_range = client.get("/api/v1/articles/calendar", headers=auth_headers(editor_token))
    assert missing_range.status_code == 422

    now = datetime.now(timezone.utc)
    # query_string (not an interpolated URL) so Werkzeug urlencodes the "+"
    # in a UTC offset properly — a raw "+00:00" in a query string would
    # otherwise decode back as a literal space and break ISO parsing.
    end_before_start = client.get(
        "/api/v1/articles/calendar",
        query_string={"start": now.isoformat(), "end": (now - timedelta(days=1)).isoformat()},
        headers=auth_headers(editor_token),
    )
    assert end_before_start.status_code == 422


def test_calendar_returns_scheduled_and_published_within_range(client, editor_token, author_slug):
    slug = _approved_article(client, editor_token, author_slug, title="On The Calendar")
    scheduled_at = _future_iso(3600)
    client.post(
        f"/api/v1/articles/{slug}/schedule", json={"scheduledAt": scheduled_at}, headers=auth_headers(editor_token)
    )

    now = datetime.now(timezone.utc)
    resp = client.get(
        "/api/v1/articles/calendar",
        query_string={"start": now.isoformat(), "end": (now + timedelta(days=2)).isoformat()},
        headers=auth_headers(editor_token),
    )
    assert resp.status_code == 200
    slugs = [a["slug"] for a in resp.get_json()["data"]]
    assert slug in slugs
    # Calendar rows carry workflow metadata (not on the public schema).
    matching = next(a for a in resp.get_json()["data"] if a["slug"] == slug)
    assert matching["scheduled_at"] is not None

    empty_resp = client.get(
        "/api/v1/articles/calendar",
        query_string={"start": (now - timedelta(days=20)).isoformat(), "end": (now - timedelta(days=10)).isoformat()},
        headers=auth_headers(editor_token),
    )
    assert empty_resp.status_code == 200
    assert slug not in [a["slug"] for a in empty_resp.get_json()["data"]]


def test_calendar_denies_user_with_no_article_permission(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "no-permission@example.com", "password": "supersecret1", "first_name": "No", "last_name": "Perm"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "no-permission@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]
    now = datetime.now(timezone.utc)
    resp = client.get(
        "/api/v1/articles/calendar",
        query_string={"start": now.isoformat(), "end": (now + timedelta(days=1)).isoformat()},
        headers=auth_headers(token),
    )
    assert resp.status_code == 403
