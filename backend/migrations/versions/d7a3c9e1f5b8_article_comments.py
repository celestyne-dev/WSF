"""First-party article comments (Step 13).

- articles.comments_mode ('on' | 'off' | 'close_after', existing rows: 'on')
  and articles.comments_close_after_days.
- comments: one reply level (parent_id), moderation lifecycle, user_id
  nullable with ON DELETE SET NULL ("Former member"), HMAC IP hash with a
  90-day expiry.
- comment_reports (one per account per comment), comment_events
  (moderation history, metadata only), comment_restrictions (comment
  suspension/ban, separate from account deactivation),
  comment_notification_preferences (reply emails, off by default).

Downgrade drops all comment data.

Revision ID: d7a3c9e1f5b8
Revises: c6f2b8d0e4a7
"""
from alembic import op
import sqlalchemy as sa

revision = "d7a3c9e1f5b8"
down_revision = "c6f2b8d0e4a7"
branch_labels = None
depends_on = None


def _ts(name, **kw):
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def _user_fk(name, **kw):
    return sa.Column(name, sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, **kw)


def upgrade():
    op.add_column("articles", sa.Column("comments_mode", sa.String(length=20), nullable=False, server_default="on"))
    op.add_column("articles", sa.Column("comments_close_after_days", sa.Integer(), nullable=True))
    op.create_check_constraint("ck_articles_comments_mode", "articles",
                               "comments_mode IN ('on', 'off', 'close_after')")
    op.create_check_constraint(
        "ck_articles_comments_close_after_days", "articles",
        "comments_mode <> 'close_after' OR (comments_close_after_days BETWEEN 1 AND 3650)")

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
        _user_fk("user_id"),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("held_reasons", sa.JSON(), nullable=False),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
        _ts("updated_at", server_default=sa.func.now(), nullable=False),
        _ts("edited_at"),
        _ts("published_at"),
        _ts("approved_at"),
        _user_fk("approved_by_id"),
        _ts("hidden_at"),
        _ts("removed_at"),
        _user_fk("removed_by_id"),
        sa.Column("removal_reason", sa.String(length=500)),
        _ts("deleted_at"),
        _ts("reply_notified_at"),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        _ts("ip_hash_expires_at", nullable=True),
        sa.CheckConstraint("status IN ('pending', 'published', 'hidden', 'removed', 'deleted')",
                           name="ck_comments_status"),
    )
    op.create_index("ix_comments_article_status", "comments", ["article_id", "status"])
    op.create_index("ix_comments_status_created", "comments", ["status", "created_at"])
    op.create_index("ix_comments_user_id", "comments", ["user_id"])
    op.create_index("ix_comments_parent_id", "comments", ["parent_id"])
    op.create_index("ix_comments_ip_hash_expires_at", "comments", ["ip_hash_expires_at"])

    op.create_table(
        "comment_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("comment_id", sa.Integer(), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=False),
        _user_fk("reporter_id"),
        sa.Column("reason", sa.String(length=20), nullable=False),
        sa.Column("details", sa.String(length=500)),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("comment_id", "reporter_id", name="uq_comment_reports_comment_reporter"),
        sa.CheckConstraint("reason IN ('spam', 'harassment', 'misinformation', 'other')",
                           name="ck_comment_reports_reason"),
    )
    op.create_index("ix_comment_reports_comment_id", "comment_reports", ["comment_id"])

    op.create_table(
        "comment_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("comment_id", sa.Integer(), sa.ForeignKey("comments.id", ondelete="CASCADE"), nullable=True),
        _user_fk("subject_user_id"),
        _user_fk("actor_id"),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("reason", sa.String(length=500)),
        sa.Column("meta", sa.JSON()),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_comment_events_comment_id", "comment_events", ["comment_id"])
    op.create_index("ix_comment_events_subject_user_id", "comment_events", ["subject_user_id"])

    op.create_table(
        "comment_restrictions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        _ts("ends_at"),
        _user_fk("created_by_id"),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
        _ts("lifted_at"),
        _user_fk("lifted_by_id"),
        sa.CheckConstraint("kind IN ('suspension', 'ban')", name="ck_comment_restrictions_kind"),
    )
    op.create_index("ix_comment_restrictions_user_id", "comment_restrictions", ["user_id"])

    op.create_table(
        "comment_notification_preferences",
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("reply_emails", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("unsubscribe_token", sa.String(length=64), nullable=False, unique=True),
        _ts("updated_at", server_default=sa.func.now(), nullable=False),
    )


def downgrade():
    op.drop_table("comment_notification_preferences")
    op.drop_index("ix_comment_restrictions_user_id", table_name="comment_restrictions")
    op.drop_table("comment_restrictions")
    op.drop_index("ix_comment_events_subject_user_id", table_name="comment_events")
    op.drop_index("ix_comment_events_comment_id", table_name="comment_events")
    op.drop_table("comment_events")
    op.drop_index("ix_comment_reports_comment_id", table_name="comment_reports")
    op.drop_table("comment_reports")
    for name in ("ix_comments_ip_hash_expires_at", "ix_comments_parent_id", "ix_comments_user_id",
                 "ix_comments_status_created", "ix_comments_article_status"):
        op.drop_index(name, table_name="comments")
    op.drop_table("comments")
    op.drop_constraint("ck_articles_comments_close_after_days", "articles", type_="check")
    op.drop_constraint("ck_articles_comments_mode", "articles", type_="check")
    op.drop_column("articles", "comments_close_after_days")
    op.drop_column("articles", "comments_mode")
