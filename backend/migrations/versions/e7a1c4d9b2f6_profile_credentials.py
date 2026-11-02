"""profile credentials

Revision ID: e7a1c4d9b2f6
Revises: d4b8e2a6f1c3
Create Date: 2026-11-02 08:00:00.000000

AI Search / GEO Phase 4B: people.credentials and authors.credentials — the
ordered credentials & qualifications a profile states (see
app/schemas/credentials.py). Additive only: NOT NULL with a server
default of an empty JSON array, so every existing row becomes [].
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7a1c4d9b2f6'
down_revision = 'd4b8e2a6f1c3'
branch_labels = None
depends_on = None


def upgrade():
    for table in ('people', 'authors'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column('credentials', sa.JSON(), nullable=False, server_default='[]')
            )


def downgrade():
    for table in ('authors', 'people'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column('credentials')
