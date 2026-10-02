"""widen partnership_inquiries.partnership_type CHECK to the eight paid
commercial formats publicly advertised on /advertise and /partnerships

Revision ID: 9c1d7e4b2a6f
Revises: 26c75ea13da3
Create Date: 2026-10-02 00:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '9c1d7e4b2a6f'
down_revision = '26c75ea13da3'
branch_labels = None
depends_on = None

# Mirrors app/models/commerce.py's PARTNERSHIP_TYPES exactly. Narrow,
# additive change: every pre-existing value stays, in the same order,
# so no stored PartnershipInquiry.partnership_type value is invalidated
# or needs rewriting — only the CHECK constraint widens to also accept
# the eight new paid formats.
PAID_PARTNERSHIP_TYPES = (
    "Sponsored Editorial",
    "Sponsored Series",
    "Newsletter Sponsorship",
    "Social Media Campaigns",
    "Employer Branding",
    "Event Sponsorship",
    "Sponsored Resources",
    "Research Partnerships",
)

EXISTING_PARTNERSHIP_TYPES = (
    "Brand Partnership", "Content Partnership", "Employer Partnership", "Event Partnership",
    "Community Partnership", "Education Partnership", "Resource Partnership", "Recruitment Partnership",
    "Strategic Partnership", "Affiliate Partnership", "Research Partnership", "Advertising", "Other",
)

PARTNERSHIP_TYPES = PAID_PARTNERSHIP_TYPES + EXISTING_PARTNERSHIP_TYPES


def upgrade():
    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_partnership_inquiries_type', type_='check')
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_type',
            "partnership_type IS NULL OR partnership_type IN (" + ", ".join(f"'{t}'" for t in PARTNERSHIP_TYPES) + ")",
        )


def downgrade():
    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_partnership_inquiries_type', type_='check')
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_type',
            "partnership_type IS NULL OR partnership_type IN (" + ", ".join(f"'{t}'" for t in EXISTING_PARTNERSHIP_TYPES) + ")",
        )
