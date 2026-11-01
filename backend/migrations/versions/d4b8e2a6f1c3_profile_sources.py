"""profile sources

Revision ID: d4b8e2a6f1c3
Revises: c3a9e5f1d2b7
Create Date: 2026-11-01 22:00:00.000000

AI Search / GEO Phase 4A: people.sources and authors.sources — the ordered
editorial sources & references behind a profile, same shape as
articles.sources (see app/schemas/sources.py). Additive only: NOT NULL
with a server default of an empty JSON array, so every existing row
becomes [] (no sources are ever invented for existing profiles).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4b8e2a6f1c3'
down_revision = 'c3a9e5f1d2b7'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('people', 'authors'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('sources', sa.JSON(), nullable=False, server_default='[]')
            )


def downgrade():
    for table in ('authors', 'people'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('sources')
