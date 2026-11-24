"""Provider-neutral newsletter: double opt-in, consent trail, suppression
imports and external-send records (Step 14).

Historical rows (nothing is invented):
- subscribers with status 'active' -> 'legacy_unconfirmed': they consented
  before double opt-in existed, and whether they ever confirmed is not
  known. Their stored consent_at / consent_version / placement are kept
  as-is (NULL stays NULL); confirmed_at stays NULL. One
  "legacy_unconfirmed" event records the mapping.
- 'unsubscribed' / 'bounced' / 'complained' are unchanged.
- issues 'scheduled' -> 'ready' (WSF never sent on a schedule; the status
  only ever meant "finished, waiting for a manual send").

Downgrade: 'legacy_unconfirmed' and 'active' -> 'active', 'pending' ->
'unsubscribed' (never confirmed, so never sendable), 'ready' -> 'scheduled';
the new tables and columns are dropped.

Revision ID: e8b4d0f2a6c9
Revises: d7a3c9e1f5b8
"""
from alembic import op
import sqlalchemy as sa

revision = "e8b4d0f2a6c9"
down_revision = "d7a3c9e1f5b8"
branch_labels = None
depends_on = None

OLD_SUB = "status IN ('active', 'unsubscribed', 'bounced', 'complained')"
NEW_SUB = "status IN ('pending', 'active', 'legacy_unconfirmed', 'unsubscribed', 'bounced', 'complained')"
OLD_ISSUE = "status IN ('draft', 'scheduled', 'sent', 'archived')"
NEW_ISSUE = "status IN ('draft', 'ready', 'sent', 'archived')"


def _ts(name, **kw):
    return sa.Column(name, sa.DateTime(timezone=True), **kw)


def upgrade():
    for col in (sa.Column("consent_source", sa.String(length=50)), _ts("confirmed_at"),
                sa.Column("unsubscribe_source", sa.String(length=40)),
                sa.Column("unsubscribe_reason", sa.String(length=200))):
        op.add_column("newsletter_subscribers", col)

    op.create_table(
        "newsletter_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscriber_id", sa.Integer(),
                  sa.ForeignKey("newsletter_subscribers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        _ts("consent_at", nullable=False),
        sa.Column("consent_version", sa.String(length=40), nullable=False),
        sa.Column("consent_source", sa.String(length=50)),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
        _ts("expires_at", nullable=False),
        _ts("confirmed_at"),
        _ts("superseded_at"),
    )
    op.create_index("ix_newsletter_confirmations_subscriber_id", "newsletter_confirmations", ["subscriber_id"])
    op.create_table(
        "newsletter_suppression_imports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("filename", sa.String(length=200)),
        *(sa.Column(n, sa.Integer(), nullable=False, server_default="0")
          for n in ("rows", "invalid", "newly_suppressed", "already_suppressed", "added_unknown")),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "newsletter_subscriber_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscriber_id", sa.Integer(),
                  sa.ForeignKey("newsletter_subscribers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=80)),
        sa.Column("consent_version", sa.String(length=40)),
        sa.Column("import_id", sa.Integer(), sa.ForeignKey("newsletter_suppression_imports.id", ondelete="SET NULL")),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_newsletter_subscriber_events_subscriber_id", "newsletter_subscriber_events", ["subscriber_id"])
    op.create_table(
        "newsletter_send_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("issue_id", sa.Integer(), sa.ForeignKey("newsletter_issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("provider_name", sa.String(length=100)),
        sa.Column("external_reference", sa.String(length=200)),
        sa.Column("recipient_count", sa.Integer(), nullable=False, server_default="0"),
        _ts("occurred_at", nullable=False),
        sa.Column("note", sa.String(length=500)),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        _ts("created_at", server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("kind IN ('export', 'external_send')", name="ck_newsletter_send_records_kind"),
    )
    op.create_index("ix_newsletter_send_records_issue_id", "newsletter_send_records", ["issue_id"])

    op.drop_constraint("ck_newsletter_subscribers_status", "newsletter_subscribers", type_="check")
    op.execute("INSERT INTO newsletter_subscriber_events (subscriber_id, event, source, consent_version, created_at) "
               "SELECT id, 'legacy_unconfirmed', 'migration', consent_version, now() "
               "FROM newsletter_subscribers WHERE status = 'active'")
    op.execute("UPDATE newsletter_subscribers SET status = 'legacy_unconfirmed' WHERE status = 'active'")
    op.create_check_constraint("ck_newsletter_subscribers_status", "newsletter_subscribers", NEW_SUB)

    op.drop_constraint("ck_newsletter_issues_status", "newsletter_issues", type_="check")
    op.execute("UPDATE newsletter_issues SET status = 'ready' WHERE status = 'scheduled'")
    op.create_check_constraint("ck_newsletter_issues_status", "newsletter_issues", NEW_ISSUE)


def downgrade():
    op.drop_constraint("ck_newsletter_issues_status", "newsletter_issues", type_="check")
    op.execute("UPDATE newsletter_issues SET status = 'scheduled' WHERE status = 'ready'")
    op.create_check_constraint("ck_newsletter_issues_status", "newsletter_issues", OLD_ISSUE)
    op.drop_constraint("ck_newsletter_subscribers_status", "newsletter_subscribers", type_="check")
    op.execute("UPDATE newsletter_subscribers SET status = 'active' WHERE status = 'legacy_unconfirmed'")
    op.execute("UPDATE newsletter_subscribers SET status = 'unsubscribed' WHERE status = 'pending'")
    op.create_check_constraint("ck_newsletter_subscribers_status", "newsletter_subscribers", OLD_SUB)
    op.drop_index("ix_newsletter_send_records_issue_id", table_name="newsletter_send_records")
    op.drop_table("newsletter_send_records")
    op.drop_index("ix_newsletter_subscriber_events_subscriber_id", table_name="newsletter_subscriber_events")
    op.drop_table("newsletter_subscriber_events")
    op.drop_table("newsletter_suppression_imports")
    op.drop_index("ix_newsletter_confirmations_subscriber_id", table_name="newsletter_confirmations")
    op.drop_table("newsletter_confirmations")
    for col in ("unsubscribe_reason", "unsubscribe_source", "confirmed_at", "consent_source"):
        op.drop_column("newsletter_subscribers", col)
