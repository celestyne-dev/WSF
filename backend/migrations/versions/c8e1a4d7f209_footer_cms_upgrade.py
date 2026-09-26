"""footer cms upgrade: menu group ordering/visibility, richer social links

Footer link groups are Menu rows (key prefixed "footer_") reusing the
Navigation CMS Menu/MenuItem architecture — see Menu's docstring in
app/models/cms.py. This migration adds what Footer CMS needs that
Navigation never did: a group can be hidden without deleting it, and
groups can be reordered independently of insertion order. Both columns
are harmless no-ops for the primary/secondary menus (they stay at their
defaults and are never surfaced there).

social_links gains `visible` (hide a platform without deleting the row)
and `label` (accessible-name override), plus a controlled-platform CHECK
constraint matching the frontend's icon map — see SOCIAL_PLATFORMS in
app/models/cms.py.

Revision ID: c8e1a4d7f209
Revises: b7d3f9a2c4e6
Create Date: 2026-09-26 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c8e1a4d7f209'
down_revision = 'b7d3f9a2c4e6'
branch_labels = None
depends_on = None

SOCIAL_PLATFORMS = (
    "linkedin",
    "instagram",
    "facebook",
    "tiktok",
    "threads",
    "pinterest",
    "youtube",
    "whatsapp",
    "twitter",
)
_PLATFORM_CHECK = "platform IN (" + ", ".join(f"'{p}'" for p in SOCIAL_PLATFORMS) + ")"


def upgrade():
    with op.batch_alter_table('menus', schema=None) as batch_op:
        batch_op.add_column(sa.Column('visible', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))

    with op.batch_alter_table('menus', schema=None) as batch_op:
        batch_op.alter_column('visible', server_default=None)
        batch_op.alter_column('sort_order', server_default=None)

    with op.batch_alter_table('social_links', schema=None) as batch_op:
        batch_op.add_column(sa.Column('label', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('visible', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.create_check_constraint('ck_social_links_platform', _PLATFORM_CHECK)

    with op.batch_alter_table('social_links', schema=None) as batch_op:
        batch_op.alter_column('visible', server_default=None)


def downgrade():
    with op.batch_alter_table('social_links', schema=None) as batch_op:
        batch_op.drop_constraint('ck_social_links_platform', type_='check')
        batch_op.drop_column('visible')
        batch_op.drop_column('label')

    with op.batch_alter_table('menus', schema=None) as batch_op:
        batch_op.drop_column('sort_order')
        batch_op.drop_column('visible')
