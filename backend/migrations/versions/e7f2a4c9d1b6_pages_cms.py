"""pages cms: Page + PageRevision models

Brand-new tables — nothing else in the app references `pages` or
`page_revisions` yet, so this is purely additive: no existing table,
column, or row is touched.

Revision ID: e7f2a4c9d1b6
Revises: d6e1f3a8c9b2
Create Date: 2026-09-25 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e7f2a4c9d1b6'
down_revision = 'd6e1f3a8c9b2'
branch_labels = None
depends_on = None

PAGE_STATUSES = ("draft", "published", "archived")
_STATUS_CHECK = "status IN (" + ", ".join(f"'{s}'" for s in PAGE_STATUSES) + ")"

PAGE_TYPES = ("system", "general")
_TYPE_CHECK = "page_type IN (" + ", ".join(f"'{t}'" for t in PAGE_TYPES) + ")"


def upgrade():
    op.create_table(
        'pages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('page_type', sa.String(length=20), nullable=False, server_default='general'),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('internal_name', sa.String(length=200), nullable=True),
        sa.Column('subtitle', sa.Text(), nullable=True),
        sa.Column('content', sa.JSON(), nullable=False),
        sa.Column('hero_media_id', sa.Integer(), nullable=True),
        sa.Column('seo', sa.JSON(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'),
        sa.Column('effective_date', sa.Date(), nullable=True),
        sa.Column('last_reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_reviewed_by_id', sa.Integer(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
        sa.UniqueConstraint('slug'),
        sa.ForeignKeyConstraint(['hero_media_id'], ['media.id']),
        sa.ForeignKeyConstraint(['last_reviewed_by_id'], ['users.id']),
        sa.ForeignKeyConstraint(['updated_by_id'], ['users.id']),
        sa.CheckConstraint(_STATUS_CHECK, name='ck_pages_status'),
        sa.CheckConstraint(_TYPE_CHECK, name='ck_pages_page_type'),
    )
    op.create_index('ix_pages_key', 'pages', ['key'])
    op.create_index('ix_pages_slug', 'pages', ['slug'])

    op.create_table(
        'page_revisions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('page_id', sa.Integer(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=False),
        sa.Column('note', sa.String(length=300), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['page_id'], ['pages.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
    )


def downgrade():
    op.drop_table('page_revisions')
    op.drop_index('ix_pages_slug', table_name='pages')
    op.drop_index('ix_pages_key', table_name='pages')
    op.drop_table('pages')
