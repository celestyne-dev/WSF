"""article sources

Revision ID: c3a9e5f1d2b7
Revises: b62f72a7c22e
Create Date: 2026-11-01 15:00:00.000000

AI Search / GEO Phase 3A: one new column, articles.sources — the ordered
list of editorial sources/references behind an article (see
app/models/article.py's own comment for the shape). Additive only:
NOT NULL with a server default of an empty JSON array, so every existing
row becomes [] (no sources are ever invented for existing articles).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a9e5f1d2b7'
down_revision = 'b62f72a7c22e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('sources', sa.JSON(), nullable=False, server_default='[]')
        )


def downgrade():
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_column('sources')
