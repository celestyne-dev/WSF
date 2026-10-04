"""event circle_only access type

Revision ID: 5e6c6ef78228
Revises: 8a2f4c6e9d31
Create Date: 2026-10-04 18:20:20.351096

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5e6c6ef78228'
down_revision = '8a2f4c6e9d31'
branch_labels = None
depends_on = None

_EVENT_ACCESS_TYPES = ("public", "circle_only")
_CHECK_SQL = "access_type IN (" + ", ".join(f"'{a}'" for a in _EVENT_ACCESS_TYPES) + ")"


def upgrade():
    op.add_column(
        "events",
        sa.Column("access_type", sa.String(length=20), nullable=False, server_default="public"),
    )
    op.create_check_constraint("ck_events_access_type", "events", _CHECK_SQL)


def downgrade():
    op.drop_constraint("ck_events_access_type", "events", type_="check")
    op.drop_column("events", "access_type")
