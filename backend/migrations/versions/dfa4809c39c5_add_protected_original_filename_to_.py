"""add protected_original_filename to resources

Revision ID: dfa4809c39c5
Revises: 21f45add6f49
Create Date: 2026-10-09 21:31:45.706724

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dfa4809c39c5'
down_revision = '21f45add6f49'
branch_labels = None
depends_on = None


def upgrade():
    # Module 13B: display/download metadata for a circle_only Resource's
    # uploaded protected file (see app/models/resource.py's column
    # docstring) — purely additive, no data rewrite, no backfill. A
    # pre-existing row keeps NULL here and falls back to
    # os.path.basename(protected_file_path) wherever this is displayed.
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('protected_original_filename', sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_column('protected_original_filename')
