"""resource circle access level (yearly member bonus vault)

Revision ID: 4082ec5bec43
Revises: 9e40ec084a5f
Create Date: 2026-10-14 00:00:00.000000

Additive only: one new column on resources (circle_access_level),
meaningful only when access_type == 'circle_only' (see
app/models/resource.py's CIRCLE_ACCESS_LEVELS and
app/services/resource_access.py's check_resource_access). Backfills
every existing row to 'all_members' — the exact behavior circle_only
already had before this column existed — so no existing Resource's
access changes. No changes to access_type, any Circle table, or
ResourcePurchase/ResourcePayment.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '4082ec5bec43'
down_revision = '9e40ec084a5f'
branch_labels = None
depends_on = None

CIRCLE_ACCESS_LEVELS = ("all_members", "yearly_members")


def upgrade():
    op.add_column(
        'resources',
        sa.Column('circle_access_level', sa.String(length=20), nullable=False, server_default='all_members'),
    )
    op.create_check_constraint(
        'ck_resources_circle_access_level',
        'resources',
        "circle_access_level IN (" + ", ".join(f"'{l}'" for l in CIRCLE_ACCESS_LEVELS) + ")",
    )


def downgrade():
    op.drop_constraint('ck_resources_circle_access_level', 'resources', type_='check')
    op.drop_column('resources', 'circle_access_level')
