"""Newsletter consent provenance: consent_at + consent_version.

Two nullable columns on newsletter_subscribers recording WHEN the visitor
last gave signup consent and WHICH version of the consent wording they saw
(app/services/engagement_settings.py NEWSLETTER_CONSENT_VERSION). Where it
was given is the existing `placement` column. No IP address or browser data
is stored. Existing rows keep NULL (their provenance was never recorded);
nothing is rewritten.

Revision ID: b8e4d2f6a1c3
Revises: a7d3c9e1f5b2
"""
from alembic import op
import sqlalchemy as sa

revision = "b8e4d2f6a1c3"
down_revision = "a7d3c9e1f5b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("newsletter_subscribers", sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("newsletter_subscribers", sa.Column("consent_version", sa.String(length=40), nullable=True))


def downgrade():
    op.drop_column("newsletter_subscribers", "consent_version")
    op.drop_column("newsletter_subscribers", "consent_at")
