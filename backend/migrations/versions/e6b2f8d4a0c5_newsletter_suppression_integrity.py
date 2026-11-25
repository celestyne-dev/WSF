"""Newsletter suppression integrity (Batch 4 corrections):
newsletter_subscribers.last_suppressed_at, newsletter_confirmations.proposed_profile.

Revision ID: e6b2f8d4a0c5
Revises: d5a1e7c3b9f4
"""
from alembic import op
import sqlalchemy as sa

revision = "e6b2f8d4a0c5"
down_revision = "d5a1e7c3b9f4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("newsletter_subscribers", sa.Column("last_suppressed_at", sa.DateTime(timezone=True)))
    op.execute("UPDATE newsletter_subscribers SET last_suppressed_at = COALESCE(unsubscribed_at, now()) "
               "WHERE status IN ('unsubscribed', 'bounced', 'complained')")
    op.add_column("newsletter_confirmations", sa.Column("proposed_profile", sa.JSON()))
    # Suppressed addresses keep no live confirmation link.
    op.execute("UPDATE newsletter_confirmations c SET superseded_at = now() FROM newsletter_subscribers s "
               "WHERE c.subscriber_id = s.id AND c.confirmed_at IS NULL AND c.superseded_at IS NULL "
               "AND s.status IN ('unsubscribed', 'bounced', 'complained') "
               "AND c.consent_at <= COALESCE(s.unsubscribed_at, now())")


def downgrade():
    op.drop_column("newsletter_confirmations", "proposed_profile")
    op.drop_column("newsletter_subscribers", "last_suppressed_at")
