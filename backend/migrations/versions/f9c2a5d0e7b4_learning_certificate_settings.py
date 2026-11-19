"""Learning: per-program certificate settings.

Adds learning_programs.certificate_enabled (NOT NULL, server default false)
and three nullable display columns (certificate_title,
certificate_signatory_name, certificate_signatory_title). Existing
programs stay certificate-disabled. Downgrade drops only these columns.

Revision ID: f9c2a5d0e7b4
Revises: e8b1f4c9d6a3
"""
from alembic import op
import sqlalchemy as sa

revision = "f9c2a5d0e7b4"
down_revision = "e8b1f4c9d6a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("learning_programs", schema=None) as batch_op:
        batch_op.add_column(sa.Column("certificate_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("certificate_title", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("certificate_signatory_name", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("certificate_signatory_title", sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table("learning_programs", schema=None) as batch_op:
        batch_op.drop_column("certificate_signatory_title")
        batch_op.drop_column("certificate_signatory_name")
        batch_op.drop_column("certificate_title")
        batch_op.drop_column("certificate_enabled")
