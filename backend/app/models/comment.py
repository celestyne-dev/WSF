"""First-party article comments (Step 13). See app/services/comments.py for
the rules; this module only holds the tables.

Data categories (for the Step 27 Data Processing Register; not built yet):
  * comment content ............ comments.body (cleared when the member
                                  deletes the comment)
  * account/display identity ... comments.user_id -> users (public name is
                                  the account's display name; nothing else)
  * moderation state/history ... comments.status/held_reasons/approved_*/
                                  hidden_at/removed_*, comment_events
  * reports .................... comment_reports (reason + optional details)
  * comment restrictions ....... comment_restrictions (suspension / ban)
  * reply-notification choice .. comment_notification_preferences (opt-in,
                                  off by default)
  * abuse-prevention IP hash ... comments.ip_hash: HMAC-SHA256 of the
                                  client IP under a server key, never the raw
                                  IP; cleared after 90 days (ip_hash_expires_at,
                                  `flask comments-purge-ip-hashes`)

Account deletion (Batch 4): every user reference is nullable with
ON DELETE SET NULL, so a comment survives its author's account and shows
"Former member"; app/services/comments.py detach_user_comments() also
clears the IP hash and can remove the comments ("Also remove my comments").
"""
from app.extensions import db

# Lifecycle (app/services/comments.py):
#   pending   held for a moderator: first-time commenter, too many links,
#             a blocked word/phrase, or an edit that tripped one of those.
#             Visible only to its author ("awaiting approval") and moderators.
#   published public.
#   hidden    taken out of public view without a final decision: hidden by a
#             moderator, or automatically when unique reports reach the
#             Studio threshold. A moderator can approve (restore) or remove it.
#   removed   a moderator's final decision, with a reason. The body is kept
#             for moderators only and is never shown publicly; if the comment
#             has published replies, the public thread shows a neutral
#             "Comment removed" placeholder.
#   deleted   deleted by its author. The body is erased; a public placeholder
#             ("Comment deleted") stays only while published replies exist.
COMMENT_STATUSES = ("pending", "published", "hidden", "removed", "deleted")
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s}'" for s in COMMENT_STATUSES) + ")"

REPORT_REASONS = ("spam", "harassment", "misinformation", "other")
_REASON_CHECK = "reason IN (" + ", ".join(f"'{r}'" for r in REPORT_REASONS) + ")"

RESTRICTION_KINDS = ("suspension", "ban")
_KIND_CHECK = "kind IN (" + ", ".join(f"'{k}'" for k in RESTRICTION_KINDS) + ")"


class Comment(db.Model):
    __tablename__ = "comments"
    __table_args__ = (
        db.CheckConstraint(_STATUS_CHECK, name="ck_comments_status"),
        db.Index("ix_comments_article_status", "article_id", "status"),
        db.Index("ix_comments_status_created", "status", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    article_id = db.Column(db.Integer, db.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False)
    # Nullable + SET NULL: survives account deletion as "Former member".
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # One reply level only: a reply's parent is always a top-level comment
    # (enforced in app/services/comments.py). Comments are never hard-deleted
    # by the app, so CASCADE only matters when the whole article goes.
    parent_id = db.Column(db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    body = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")
    # Why a comment was held or hidden: any of "first_comment", "links",
    # "blocked_words", "reports", "moderator". Moderators only.
    held_reasons = db.Column(db.JSON, nullable=False, default=list)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(),
                           nullable=False)
    edited_at = db.Column(db.DateTime(timezone=True))
    published_at = db.Column(db.DateTime(timezone=True))
    approved_at = db.Column(db.DateTime(timezone=True))
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hidden_at = db.Column(db.DateTime(timezone=True))
    removed_at = db.Column(db.DateTime(timezone=True))
    removed_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    removal_reason = db.Column(db.String(500))
    deleted_at = db.Column(db.DateTime(timezone=True))
    # Set only when the reply-notification email was HANDED OFF to the email
    # service (claimed atomically, released again if delivery fails), so a
    # later approval/restore never sends it twice and a failure is never
    # recorded as sent (app/services/comments.py notify_reply).
    reply_notified_at = db.Column(db.DateTime(timezone=True))

    # Abuse prevention only: HMAC-SHA256(server key, normalized client IP).
    ip_hash = db.Column(db.String(64), nullable=True)
    ip_hash_expires_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)

    article = db.relationship("Article")
    user = db.relationship("User", foreign_keys=[user_id])
    parent = db.relationship("Comment", remote_side=[id], backref=db.backref("replies", lazy="select"))


class CommentReport(db.Model):
    """One report per account per comment (unique), so a single account can
    never push a comment over the auto-hide threshold."""

    __tablename__ = "comment_reports"
    __table_args__ = (
        db.UniqueConstraint("comment_id", "reporter_id", name="uq_comment_reports_comment_reporter"),
        db.CheckConstraint(_REASON_CHECK, name="ck_comment_reports_reason"),
    )

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, index=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reason = db.Column(db.String(20), nullable=False)
    details = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    comment = db.relationship("Comment", backref=db.backref("reports", lazy="select"))
    reporter = db.relationship("User")


class CommentEvent(db.Model):
    """Moderation history: what happened, by whom, why. Metadata only — no
    copies of comment text, no IP data (see the module docstring)."""

    __tablename__ = "comment_events"

    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    # The member an account-level event is about (suspension/ban/lift).
    subject_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    # Who did it; NULL = the system (e.g. automatic hide on reports).
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = db.Column(db.String(40), nullable=False)
    reason = db.Column(db.String(500))
    meta = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    actor = db.relationship("User", foreign_keys=[actor_id])


class CommentRestriction(db.Model):
    """Comment participation restriction — NOT account deactivation: the
    member keeps signing in, reading, buying, learning. While active they
    cannot post, reply, edit or report comments.
      suspension: until ends_at.   ban: until a moderator lifts it."""

    __tablename__ = "comment_restrictions"
    __table_args__ = (db.CheckConstraint(_KIND_CHECK, name="ck_comment_restrictions_kind"),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = db.Column(db.String(20), nullable=False)
    reason = db.Column(db.String(500), nullable=False)
    ends_at = db.Column(db.DateTime(timezone=True))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    lifted_at = db.Column(db.DateTime(timezone=True))
    lifted_by_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


class CommentNotificationPreference(db.Model):
    """Reply-notification emails: off unless the member opts in. The token is
    an opaque random value for the unsubscribe link (works signed out)."""

    __tablename__ = "comment_notification_preferences"

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    reply_emails = db.Column(db.Boolean, nullable=False, default=False)
    unsubscribe_token = db.Column(db.String(64), nullable=False, unique=True)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(),
                           nullable=False)
