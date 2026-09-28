"""Admin Notifications & Work Queue — a centralized internal CMS inbox so
authenticated WSF staff can see what genuinely needs their attention
(an Article ready for review, a new Story Submission, a new Partnership
Inquiry, ...). This is NOT a public/member notification system, NOT a
project-management/task tool, and does not introduce email/SMS/push/
WebSocket delivery — see app/services/notifications.py's module docstring
for the full architecture rationale.

Fan-out design: one row per (event, recipient) rather than one shared
Notification row + a recipient-association table. This app's existing
per-user-state patterns (AuditLog.user_id, Order.user_id, ...) are all
single-owner rows, and a shared-row-plus-read-state-table design would
need its own read/archived-per-user join table anyway — a bigger surface
for no real benefit at this notification volume (see task spec: "prefer
per-recipient rows unless the existing architecture strongly favors a
shared Notification + recipient association" — it doesn't). This also
makes unread counts, read state, and archive state trivially per-user
queries with no join.
"""
from app.extensions import db

# A deliberately small, code-defined vocabulary — never an arbitrary
# frontend-supplied string (see ENTITY REFERENCES / SAFE ACTION ROUTES in
# the task spec: "Do not allow arbitrary frontend URLs or arbitrary entity
# types"). Only events that correspond to a real existing workflow are
# implemented — see app/services/notifications.py's notify_* helpers.
NOTIFICATION_TYPES = (
    "article_review_requested",
    "article_approved",
    "story_submission_received",
    "nomination_received",
    "contact_inquiry_received",
    "directory_submission_received",
    "mentorship_application_received",
    "partnership_inquiry_received",
)
_NOTIFICATION_TYPE_CHECK_SQL = "notification_type IN (" + ", ".join(f"'{t}'" for t in NOTIFICATION_TYPES) + ")"

# Deliberately simple — see task spec: "Only add urgent if there is a real
# use case." Every notify_* helper in app/services/notifications.py uses
# "normal"; nothing in this task's scope needs "high" yet, but the column
# supports it for a future, narrowly-justified case without a migration.
NOTIFICATION_PRIORITIES = ("normal", "high")
_NOTIFICATION_PRIORITY_CHECK_SQL = "priority IN (" + ", ".join(f"'{p}'" for p in NOTIFICATION_PRIORITIES) + ")"

# entity_type + entity_id is the ONLY addressing scheme a notification
# carries — never a persisted redirect URL (see task spec: "No open
# redirects"). The frontend maps entity_type to a controlled admin route
# template (frontend/src/api/notifications.js) — this backend list and
# that frontend map must be kept in sync by hand; there is deliberately no
# shared codegen for a vocabulary this small and this rarely changed.
ENTITY_TYPES = (
    "article",
    "story_submission",
    "nomination",
    "contact_inquiry",
    "directory_submission",
    "mentorship_application",
    "partnership",
)
_ENTITY_TYPE_CHECK_SQL = "entity_type IS NULL OR entity_type IN (" + ", ".join(f"'{t}'" for t in ENTITY_TYPES) + ")"


class Notification(db.Model):
    """One notification, addressed to exactly one recipient. `dedupe_key`
    (when set) is unique per row — app/services/notifications.py checks it
    before inserting and the DB constraint is the last line of defense
    under a race, so a retried request or a duplicate event never produces
    more than one notification per (event, entity, recipient) — see task
    spec's DEDUPLICATION / IDEMPOTENCY sections. Deliberately no full
    source payload lives here — see NO SENSITIVE PAYLOAD COPYING: only a
    short generic title/message plus entity_type/entity_id, resolved back
    to the source record (which stays the single source of truth) by the
    frontend admin route map.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        db.CheckConstraint(_NOTIFICATION_TYPE_CHECK_SQL, name="ck_notifications_type"),
        db.CheckConstraint(_NOTIFICATION_PRIORITY_CHECK_SQL, name="ck_notifications_priority"),
        db.CheckConstraint(_ENTITY_TYPE_CHECK_SQL, name="ck_notifications_entity_type"),
        db.UniqueConstraint("dedupe_key", name="uq_notifications_dedupe_key"),
        # The inbox's own primary access pattern (see api/v1/notifications.py):
        # "this user's active, unarchived, newest-first notifications" and
        # "this user's unread count" are both a leftmost-prefix of this
        # index, so neither needs a separate one.
        db.Index(
            "ix_notifications_recipient_archived_read_created",
            "recipient_user_id",
            "is_archived",
            "is_read",
            "created_at",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    # A User row is occasionally hard-deleted (rare admin action, distinct
    # from ordinary deactivation via is_active=False — see task spec's
    # USER DEACTIVATION section, which this never touches); cascading here
    # only ever removes derived notification rows, never a source entity
    # (Article/StorySubmission/...), which this table has no FK to at all
    # — see FK DELETE BEHAVIOR in the task spec.
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    notification_type = db.Column(db.String(40), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.String(400), nullable=False)

    entity_type = db.Column(db.String(40), nullable=True)
    entity_id = db.Column(db.Integer, nullable=True)

    priority = db.Column(db.String(10), nullable=False, default="normal")

    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)

    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    archived_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Null for most notifications (see task spec: "if genuinely useful") —
    # nothing in this task's implemented event set currently sets it; the
    # column exists so a future genuinely time-bound notification type
    # doesn't need its own migration.
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # event:entity_id:recipient_id[:version] — see this model's own
    # docstring and app/services/notifications.py for exact key shapes per
    # event. Nullable (a notification type with no natural dedupe key
    # simply skips it) but unique whenever set.
    dedupe_key = db.Column(db.String(200), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False, index=True)

    recipient = db.relationship("User", foreign_keys=[recipient_user_id])

    def __repr__(self):
        return f"<Notification {self.notification_type} -> user {self.recipient_user_id}>"
