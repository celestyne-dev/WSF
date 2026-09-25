"""navigation cms upgrade: controlled item types, entity-aware links

Extends the existing `menu_items` table (Phase 4) rather than creating a
new one — see app/models/cms.py's MenuItem docstring. `url` becomes
nullable (entity-typed items derive their URL from the referenced row
instead of storing one), and new columns let an item point at a Topic,
Series, or Page by FK. Purely additive/widening — no data loss for
existing rows (every pre-existing row is implicitly item_type="route",
which keeps reading its stored `url` exactly as before).

Revision ID: b7d3f9a2c4e6
Revises: a3c8e1f5b7d2
Create Date: 2026-09-25 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7d3f9a2c4e6'
down_revision = 'a3c8e1f5b7d2'
branch_labels = None
depends_on = None

MENU_ITEM_TYPES = ("route", "topic", "series", "page", "external", "group")
_TYPE_CHECK = "item_type IN (" + ", ".join(f"'{t}'" for t in MENU_ITEM_TYPES) + ")"

MENU_ITEM_STYLES = ("standard", "cta")
_STYLE_CHECK = "style IN (" + ", ".join(f"'{s}'" for s in MENU_ITEM_STYLES) + ")"


def upgrade():
    with op.batch_alter_table('menu_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('item_type', sa.String(length=20), nullable=False, server_default='route'))
        batch_op.add_column(sa.Column('topic_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('series_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('page_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('open_new_tab', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('style', sa.String(length=20), nullable=False, server_default='standard'))
        batch_op.alter_column('url', existing_type=sa.String(length=300), nullable=True)
        batch_op.create_foreign_key('fk_menu_items_topic_id_topics', 'topics', ['topic_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_menu_items_series_id_series', 'series', ['series_id'], ['id'], ondelete='SET NULL')
        batch_op.create_foreign_key('fk_menu_items_page_id_pages', 'pages', ['page_id'], ['id'], ondelete='SET NULL')
        batch_op.create_check_constraint('ck_menu_items_item_type', _TYPE_CHECK)
        batch_op.create_check_constraint('ck_menu_items_style', _STYLE_CHECK)

    with op.batch_alter_table('menu_items', schema=None) as batch_op:
        batch_op.alter_column('item_type', server_default=None)
        batch_op.alter_column('open_new_tab', server_default=None)
        batch_op.alter_column('style', server_default=None)


def downgrade():
    with op.batch_alter_table('menu_items', schema=None) as batch_op:
        batch_op.drop_constraint('ck_menu_items_style', type_='check')
        batch_op.drop_constraint('ck_menu_items_item_type', type_='check')
        batch_op.drop_constraint('fk_menu_items_page_id_pages', type_='foreignkey')
        batch_op.drop_constraint('fk_menu_items_series_id_series', type_='foreignkey')
        batch_op.drop_constraint('fk_menu_items_topic_id_topics', type_='foreignkey')
        batch_op.alter_column('url', existing_type=sa.String(length=300), nullable=False)
        batch_op.drop_column('style')
        batch_op.drop_column('open_new_tab')
        batch_op.drop_column('page_id')
        batch_op.drop_column('series_id')
        batch_op.drop_column('topic_id')
        batch_op.drop_column('item_type')
