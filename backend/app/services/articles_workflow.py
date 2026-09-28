"""Editorial workflow + scheduled publishing for Article
(draft -> in_review -> approved -> scheduled -> published -> archived,
with changes_requested as the "sent back for changes" branch off
in_review — see app/models/article.py:ARTICLE_STATUSES).

This module owns the status-transition rules and the scheduler used by
`flask publish-due-content`. It deliberately does NOT re-implement content/
media/SEO/revision handling — that stays exactly as app/api/v1/articles.py
already does it.

Editing an approved or scheduled article (via the ordinary PUT save) never
changes its status and never clears approved_at/approved_by — see
ARTICLE_STATUSES's docstring in app/models/article.py. This is a
deliberate, minimal choice: building a full re-approval/invalidation system
(e.g. hashing content at approval time to detect drift) is explicitly out
of scope, and Audit Log already gives a complete before/after trail of any
edit made after approval, so nothing is silently hidden — approved_at/
approved_by simply record when/who moved it to "approved", not a guarantee
that every later edit was re-reviewed.
"""
from datetime import datetime, timezone

from app.extensions import db
from app.models.article import Article, ArticleRevision

# A deliberately small, mostly-linear graph. "changes_requested" is this
# project's existing name for "sent back to the author with changes
# needed" (see ARTICLE_STATUSES's own comment) — the spec's generic
# "review -> draft" step maps onto it rather than inventing a duplicate
# state; MOVE_TO_DRAFT_FROM below covers literally reaching "draft" from
# there. "archived" is intentionally terminal in this task — no
# restore/republish action is implemented (see final report: "do not add
# a complicated restore workflow unless needed").
WORKFLOW_TRANSITIONS = {
    "draft": {"in_review"},
    "in_review": {"approved", "changes_requested"},
    "changes_requested": {"draft", "in_review"},
    "approved": {"scheduled", "published"},
    "scheduled": {"approved", "published"},
    "published": {"archived"},
    "archived": set(),
}

# Transitions that require articles.manage or articles.publish (editorial
# publishing authority) rather than the weaker "can edit this article"
# check — see app/api/v1/articles.py's _can_edit / _require_publish_access.
PUBLISH_GATED_TRANSITIONS = {
    ("in_review", "approved"),
    ("approved", "scheduled"),
    ("scheduled", "approved"),
    ("scheduled", "scheduled"),  # reschedule
    ("approved", "published"),
    ("scheduled", "published"),
    ("published", "archived"),
}


def is_valid_transition(from_status, to_status):
    if from_status == to_status:
        return True
    return to_status in WORKFLOW_TRANSITIONS.get(from_status, set())


def requires_publish_permission(from_status, to_status):
    return (from_status, to_status) in PUBLISH_GATED_TRANSITIONS


def validate_schedule_datetime(value):
    """A schedule time must be timezone-aware and genuinely in the future.
    Naive datetimes (no tzinfo) are rejected outright rather than guessed
    at — see spec: "do not manually calculate timezone offsets."
    """
    if value.tzinfo is None:
        raise ValueError("Scheduled time must include timezone information.")
    now = datetime.now(timezone.utc)
    if value <= now:
        raise ValueError("Scheduled time must be in the future.")
    return value


def snapshot(article, user, note=None):
    db.session.add(
        ArticleRevision(
            article_id=article.id,
            data=_dump_for_revision(article),
            note=note,
            created_by_id=user.id if user else None,
        )
    )


def _dump_for_revision(article):
    # Local import avoids a circular import (schemas/article.py doesn't
    # depend on this module) while reusing the exact same shape
    # app/api/v1/articles.py's own _snapshot() already stores.
    from app.schemas.article import ArticleSchema

    return ArticleSchema().dump(article)


def publish_due_articles(as_of=None):
    """Publish every Article whose scheduled_at is due. Safe to call
    concurrently (each row is claimed with SELECT ... FOR UPDATE SKIP
    LOCKED, so two overlapping runs split the work instead of double-
    publishing) and safe to re-run (already-published/no-longer-scheduled
    rows are re-checked under the lock and skipped, never re-processed).
    One article's failure is isolated — every other due article is still
    attempted, and every failure is reported rather than swallowed.

    published_at (Article.publish_date) is set to the article's own
    scheduled_at, not "now" — the article is treated as having gone live
    at its planned time, matching ordinary CMS/editorial convention (the
    scheduler runs promptly after the due time, and this avoids an SEO/
    editorial publish timestamp that drifts by however many minutes cron
    happened to be running late).
    """
    now = as_of or datetime.now(timezone.utc)

    candidate_ids = [
        row.id
        for row in db.session.query(Article.id)
        .filter(Article.status == "scheduled", Article.scheduled_at.isnot(None), Article.scheduled_at <= now)
        .all()
    ]

    published, skipped, failed = [], [], []

    for article_id in candidate_ids:
        try:
            article = Article.query.filter_by(id=article_id).with_for_update(skip_locked=True).first()
            if article is None:
                # Either locked by a concurrent run, or gone — either way
                # this run has nothing safe to do with it.
                db.session.rollback()
                skipped.append(article_id)
                continue
            if article.status != "scheduled" or article.scheduled_at is None or article.scheduled_at > now:
                # No longer eligible (already published/unscheduled/
                # edited since the candidate list was built) — idempotent
                # no-op, not an error.
                db.session.rollback()
                skipped.append(article_id)
                continue

            from_status = article.status
            scheduled_at_value = article.scheduled_at
            article.status = "published"
            article.publish_date = scheduled_at_value
            db.session.flush()
            snapshot(article, None, note="Published automatically (scheduled)")
            db.session.commit()

            from app.services.audit import log_action

            log_action(
                None,
                "article.publish_automatic",
                "Article",
                article.id,
                {"from_status": from_status, "scheduled_at": scheduled_at_value.isoformat()},
            )
            published.append(article_id)
        except Exception as exc:  # noqa: BLE001 - one bad row must never abort the rest
            db.session.rollback()
            failed.append({"article_id": article_id, "error": str(exc)})

    return {"published": published, "skipped": skipped, "failed": failed}
