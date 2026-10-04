"""opportunity circle_only access type

Revision ID: 2fbced78e8a6
Revises: 5e6c6ef78228
Create Date: 2026-10-04 20:07:14.511585

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2fbced78e8a6'
down_revision = '5e6c6ef78228'
branch_labels = None
depends_on = None

_OPPORTUNITY_ACCESS_TYPES = ("public", "circle_only")
_CHECK_SQL = "access_type IN (" + ", ".join(f"'{a}'" for a in _OPPORTUNITY_ACCESS_TYPES) + ")"


def upgrade():
    op.add_column(
        "opportunities",
        sa.Column("access_type", sa.String(length=20), nullable=False, server_default="public"),
    )
    op.create_check_constraint("ck_opportunities_access_type", "opportunities", _CHECK_SQL)


def downgrade():
    op.drop_constraint("ck_opportunities_access_type", "opportunities", type_="check")
    op.drop_column("opportunities", "access_type")
