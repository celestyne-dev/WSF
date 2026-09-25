"""taxonomy cms: status/seo/media/ordering for Topic, Category, Series, Tag

Purely additive — every column below is nullable-or-server-defaulted so
every existing Topic/Category/Series/Tag row (and every Article/Person/
Member/... relationship pointing at one) keeps working unchanged. No
table is dropped or recreated, and no existing id/slug/relationship is
touched.

Revision ID: d6e1f3a8c9b2
Revises: c5d9e2b7a4f8
Create Date: 2026-09-25 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd6e1f3a8c9b2'
down_revision = 'c5d9e2b7a4f8'
branch_labels = None
depends_on = None

TAXONOMY_STATUSES = ("draft", "published", "archived")
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s}'" for s in TAXONOMY_STATUSES) + ")"


def upgrade():
    # Categories: status + display order. No SEO/media — no public detail
    # page exists for Categories (Article's sole classification value).
    op.add_column('categories', sa.Column('status', sa.String(length=20), nullable=False, server_default='published'))
    op.add_column('categories', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    op.create_check_constraint('ck_categories_status', 'categories', _STATUS_CHECK)

    # Tags: status + timestamps (previously had neither).
    op.add_column('tags', sa.Column('status', sa.String(length=20), nullable=False, server_default='published'))
    op.add_column('tags', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column('tags', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_check_constraint('ck_tags_status', 'tags', _STATUS_CHECK)

    # Topics: status, hero image, SEO.
    op.add_column('topics', sa.Column('hero_media_id', sa.Integer(), nullable=True))
    op.add_column('topics', sa.Column('seo', sa.JSON(), nullable=True))
    op.add_column('topics', sa.Column('status', sa.String(length=20), nullable=False, server_default='published'))
    op.create_foreign_key('fk_topics_hero_media_id', 'topics', 'media', ['hero_media_id'], ['id'])
    op.create_check_constraint('ck_topics_status', 'topics', _STATUS_CHECK)

    # Series: subtitle, SEO, status, display order (cover image already existed).
    op.add_column('series', sa.Column('subtitle', sa.String(length=300), nullable=True))
    op.add_column('series', sa.Column('seo', sa.JSON(), nullable=True))
    op.add_column('series', sa.Column('status', sa.String(length=20), nullable=False, server_default='published'))
    op.add_column('series', sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'))
    op.create_check_constraint('ck_series_status', 'series', _STATUS_CHECK)


def downgrade():
    op.drop_constraint('ck_series_status', 'series', type_='check')
    op.drop_column('series', 'sort_order')
    op.drop_column('series', 'status')
    op.drop_column('series', 'seo')
    op.drop_column('series', 'subtitle')

    op.drop_constraint('ck_topics_status', 'topics', type_='check')
    op.drop_constraint('fk_topics_hero_media_id', 'topics', type_='foreignkey')
    op.drop_column('topics', 'status')
    op.drop_column('topics', 'seo')
    op.drop_column('topics', 'hero_media_id')

    op.drop_constraint('ck_tags_status', 'tags', type_='check')
    op.drop_column('tags', 'updated_at')
    op.drop_column('tags', 'created_at')
    op.drop_column('tags', 'status')

    op.drop_constraint('ck_categories_status', 'categories', type_='check')
    op.drop_column('categories', 'sort_order')
    op.drop_column('categories', 'status')
