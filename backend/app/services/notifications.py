"""Admin Notifications & Work Queue — the one place every other backend
module calls into to tell CMS staff "something needs your attention."

Architecture:
  - Recipients are resolved from RBAC (app/services/rbac.py), never a
    hard-coded email/username — `notify_users_with_permission` fans out
    to every currently active user holding any of the given permissions.
    super_admin needs no special-casing: seed_roles_and_permissions()
    already grants it every concrete Permission row, so the ordinary
    permission join finds it like any other qualifying role (see task
    spec's SUPER ADMIN section).
  - Fan-out creates one Notification row per recipient (see
    app/models/notification.py's own docstring for why), so read/archive
    state is always per-user.
  - Deduplication: every notify_* helper below builds a dedupe_key unique
    to (event, entity, recipient[, a natural "version" signal already on
    the source row]) — see each helper's own comment. create_notification
    checks it before inserting and the DB's UNIQUE constraint is the last
    line of defense under a race (see app/models/notification.py).
  - No sensitive payload: every title/message here is short, generic, and
    never includes a submitter's message body, private application
    answers, payment details, or similar — the linked source record stays
    the single source of truth (see task spec's NO SENSITIVE PAYLOAD
    COPYING).
  - Notification failure handling: every notify_* call site in this app
    is made AFTER the source entity's own db.session.commit() has already
    succeeded (see each api/v1/*.py call site) — so a notification error
    can never lose the actual submission/transition. create_notification
    catches its own IntegrityError (a concurrent duplicate insert) and
    returns None rather than raising, but any other failure intentionally
    propagates — Flask's error handler still returns 500 rather than
    silently swallowing it, since by that point the real work is already
    safely committed and worth surfacing rather than hiding (see task
    spec's NOTIFICATION FAILURE section: "document the chosen strategy").
"""
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.notification import Notification
from app.models.user import Permission, Role, User


def _active_recipients_with_permission(*permission_names):
    return (
        User.query.join(User.roles)
        .join(Role.permissions)
        .filter(User.is_active.is_(True), Permission.name.in_(permission_names))
        .distinct()
        .all()
    )


def create_notification(
    recipient, notification_type, title, message, entity_type=None, entity_id=None, priority="normal", dedupe_key=None
):
    """Create one notification for one recipient. Returns the created row,
    or None if the recipient is inactive (see task spec: "Inactive CMS
    users should not receive new notifications") or `dedupe_key` already
    exists (idempotent no-op).
    """
    if not recipient or not recipient.is_active:
        return None
    if dedupe_key is not None and Notification.query.filter_by(dedupe_key=dedupe_key).first() is not None:
        return None

    notification = Notification(
        recipient_user_id=recipient.id,
        notification_type=notification_type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        priority=priority,
        dedupe_key=dedupe_key,
    )
    db.session.add(notification)
    try:
        db.session.commit()
    except IntegrityError:
        # A concurrent request already inserted the same dedupe_key.
        db.session.rollback()
        return None
    return notification


def notify_users_with_permission(
    permission_names,
    notification_type,
    title,
    message,
    entity_type=None,
    entity_id=None,
    priority="normal",
    dedupe_key_prefix=None,
    exclude_user_id=None,
):
    """Fan out one notification to every active user holding any of
    `permission_names`. `dedupe_key_prefix`, when given, has each
    recipient's id appended so idempotency is per-user — see this
    module's own docstring.
    """
    created = []
    for recipient in _active_recipients_with_permission(*permission_names):
        if exclude_user_id is not None and recipient.id == exclude_user_id:
            continue
        dedupe_key = f"{dedupe_key_prefix}:{recipient.id}" if dedupe_key_prefix else None
        notification = create_notification(
            recipient, notification_type, title, message, entity_type, entity_id, priority, dedupe_key
        )
        if notification is not None:
            created.append(notification)
    return created


# ---------------------------------------------------------------------------
# Explicit per-event helpers — one per real, existing workflow this task
# integrates with. Deliberately not a generic event-bus/framework (see
# task spec: "Do not create a massive generic event framework").
# ---------------------------------------------------------------------------


def notify_article_review_requested(article, requested_by):
    """draft|changes_requested -> in_review. Recipients: anyone who can
    approve/publish (the people who would actually act on this) — see
    app/api/v1/articles.py's _require_manage_or_publish, the same tier
    ArticleApproveResource itself requires. `article.updated_at` was just
    re-stamped by this exact transition (onupdate=func.now(), read after
    the caller's commit) so it doubles as a free per-transition "request
    version" — a second, later submit-review on the same article gets a
    new timestamp and therefore a new dedupe_key, so it is never silently
    swallowed by an older notification (see task spec's DEDUPLICATION).
    """
    version = article.updated_at.isoformat() if article.updated_at else str(article.id)
    notify_users_with_permission(
        ("articles.manage", "articles.publish"),
        "article_review_requested",
        "Article ready for review",
        f'"{article.title}" was submitted for editorial review.',
        entity_type="article",
        entity_id=article.id,
        dedupe_key_prefix=f"article_review_requested:{article.id}:{version}",
        exclude_user_id=requested_by.id if requested_by else None,
    )


def notify_article_approved(article, approved_by):
    """in_review -> approved. Recipient: whoever created the article
    (Article.created_by_id — the only reliably-determined "requester"
    ownership this app tracks; see task spec's ARTICLE APPROVAL section:
    "Only implement if recipient ownership can be determined reliably.
    Do not invent recipients."). Skipped entirely when there's no
    created_by_id, the creator is inactive, or the approver is the
    creator themself (nothing useful to tell someone about their own
    action).
    """
    if not article.created_by_id or (approved_by and article.created_by_id == approved_by.id):
        return
    creator = db.session.get(User, article.created_by_id)
    if creator is None:
        return
    version = article.approved_at.isoformat() if article.approved_at else str(article.id)
    create_notification(
        creator,
        "article_approved",
        "Article approved",
        f'"{article.title}" was approved.',
        entity_type="article",
        entity_id=article.id,
        dedupe_key=f"article_approved:{article.id}:{creator.id}:{version}",
    )


def notify_story_submission_received(submission):
    notify_users_with_permission(
        ("submissions.manage",),
        "story_submission_received",
        "New story submission",
        "A new story submission was received.",
        entity_type="story_submission",
        entity_id=submission.id,
        dedupe_key_prefix=f"story_submission_received:{submission.id}",
    )


def notify_nomination_received(nomination):
    notify_users_with_permission(
        ("nominations.manage",),
        "nomination_received",
        "New nomination",
        "A new nomination was received.",
        entity_type="nomination",
        entity_id=nomination.id,
        dedupe_key_prefix=f"nomination_received:{nomination.id}",
    )


def notify_contact_received(inquiry):
    # inquiry_type is a small controlled enum (see app/models/contact.py's
    # CONTACT_INQUIRY_TYPES) — safe to surface, unlike the free-text
    # subject/message the visitor actually wrote.
    label = (inquiry.inquiry_type or "general").replace("_", " ")
    notify_users_with_permission(
        ("contact.manage",),
        "contact_inquiry_received",
        "New contact inquiry",
        f"A new {label} inquiry was received.",
        entity_type="contact_inquiry",
        entity_id=inquiry.id,
        dedupe_key_prefix=f"contact_inquiry_received:{inquiry.id}",
    )


def notify_directory_submission_received(submission):
    notify_users_with_permission(
        ("directory.manage",),
        "directory_submission_received",
        "New directory submission",
        "A new business listing was submitted for review.",
        entity_type="directory_submission",
        entity_id=submission.id,
        dedupe_key_prefix=f"directory_submission_received:{submission.id}",
    )


def notify_mentorship_application_received(application):
    # role is a small controlled enum ("mentor"/"mentee" — see
    # app/models/mentorship.py) — safe to surface, unlike free-text answers.
    role_label = application.role or "mentorship"
    notify_users_with_permission(
        ("mentorship.manage",),
        "mentorship_application_received",
        "New mentorship application",
        f"A new {role_label} application was received.",
        entity_type="mentorship_application",
        entity_id=application.id,
        dedupe_key_prefix=f"mentorship_application_received:{application.id}",
    )


def notify_partnership_received(inquiry):
    notify_users_with_permission(
        ("partnerships.manage",),
        "partnership_inquiry_received",
        "New partnership inquiry",
        "A new partnership inquiry was received.",
        entity_type="partnership",
        entity_id=inquiry.id,
        dedupe_key_prefix=f"partnership_inquiry_received:{inquiry.id}",
    )
