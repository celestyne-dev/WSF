"""Account export/deletion and privacy requests (Step 16).

- users: deletion_requested_at, deletion_scheduled_for, deletion_remove_comments
  (self-service deletion with a 14-day grace period).
- Payment records survive account deletion (6-year retention): user_id on
  circle_payments, circle_subscriptions, resource_payments,
  resource_purchases becomes nullable with ON DELETE SET NULL (was NOT NULL
  CASCADE, which would have deleted them); orders.user_id ON DELETE SET NULL.
- audit_logs.user_id and analytics_events.user_id ON DELETE SET NULL (was NO
  ACTION, which blocked deleting a user): history kept, identity link removed.
- consent_records.account_deleted_at (retention: account lifetime + 2 years).
- story_submissions.anonymised_at.
- privacy_requests table.

Downgrade restores the old FK rules; it fails if detached (NULL user_id)
payment rows exist, by design (they cannot be re-attached).

Revision ID: f9c5e1a3b7d2
Revises: e8b4d0f2a6c9
"""
from alembic import op
import sqlalchemy as sa

revision = "f9c5e1a3b7d2"
down_revision = "e8b4d0f2a6c9"
branch_labels = None
depends_on = None

DETACHED_PAYMENT_TABLES = ("circle_payments", "circle_subscriptions", "resource_payments", "resource_purchases")


def _refk(table, ondelete):
    name = f"{table}_user_id_fkey"
    op.drop_constraint(name, table, type_="foreignkey")
    op.create_foreign_key(name, table, "users", ["user_id"], ["id"], ondelete=ondelete)


def upgrade():
    op.add_column("users", sa.Column("deletion_requested_at", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("deletion_scheduled_for", sa.DateTime(timezone=True)))
    op.add_column("users", sa.Column("deletion_remove_comments", sa.Boolean(), nullable=False,
                                     server_default=sa.false()))
    op.create_index("ix_users_deletion_scheduled_for", "users", ["deletion_scheduled_for"])

    for table in DETACHED_PAYMENT_TABLES:
        op.alter_column(table, "user_id", existing_type=sa.Integer(), nullable=True)
        _refk(table, "SET NULL")
    for table in ("orders", "audit_logs", "analytics_events"):
        _refk(table, "SET NULL")

    op.add_column("consent_records", sa.Column("account_deleted_at", sa.DateTime(timezone=True)))
    op.add_column("story_submissions", sa.Column("anonymised_at", sa.DateTime(timezone=True)))

    op.create_table(
        "privacy_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("requester_name", sa.String(length=200)),
        sa.Column("requester_email", sa.String(length=255)),
        sa.Column("request_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False),
        sa.Column("details", sa.Text()),
        sa.Column("admin_notes", sa.Text()),
        sa.Column("opened_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("request_type IN ('access', 'correction', 'deletion', 'other')",
                           name="ck_privacy_requests_type"),
        sa.CheckConstraint("status IN ('open', 'in_progress', 'completed', 'declined')",
                           name="ck_privacy_requests_status"),
    )
    op.create_index("ix_privacy_requests_user_id", "privacy_requests", ["user_id"])


def downgrade():
    op.drop_index("ix_privacy_requests_user_id", table_name="privacy_requests")
    op.drop_table("privacy_requests")
    op.drop_column("story_submissions", "anonymised_at")
    op.drop_column("consent_records", "account_deleted_at")
    for table in ("orders", "audit_logs", "analytics_events"):
        _refk(table, None)
    for table in DETACHED_PAYMENT_TABLES:
        _refk(table, "CASCADE")
        op.alter_column(table, "user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_users_deletion_scheduled_for", table_name="users")
    op.drop_column("users", "deletion_remove_comments")
    op.drop_column("users", "deletion_scheduled_for")
    op.drop_column("users", "deletion_requested_at")
