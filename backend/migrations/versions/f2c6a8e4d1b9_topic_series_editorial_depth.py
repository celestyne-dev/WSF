"""topic and series editorial depth

Revision ID: f2c6a8e4d1b9
Revises: e7a1c4d9b2f6
Create Date: 2026-11-02 12:00:00.000000

AI Search / GEO Phase 4C: long-form editorial `content`, `sources` and a
curated `featured_article_id` ("Start here") on topics and series.
Additive only: content/sources are NOT NULL with a server default of an
empty JSON array (every existing row becomes []); featured_article_id is
a nullable FK to articles.id with ON DELETE SET NULL (existing rows NULL).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c6a8e4d1b9'
down_revision = 'e7a1c4d9b2f6'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('topics', 'series'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('content', sa.JSON(), nullable=False, server_default='[]'))
            batch_op.add_column(sa.Column('sources', sa.JSON(), nullable=False, server_default='[]'))
            batch_op.add_column(sa.Column('featured_article_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f'fk_{table}_featured_article_id', 'articles', ['featured_article_id'], ['id'], ondelete='SET NULL'
            )


def downgrade():
    for table in ('series', 'topics'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'fk_{table}_featured_article_id', type_='foreignkey')
            batch_op.drop_column('featured_article_id')
            batch_op.drop_column('sources')
            batch_op.drop_column('content')
