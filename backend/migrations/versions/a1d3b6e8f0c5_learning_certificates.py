"""Learning: first-party certificates of completion.

Creates learning_certificates (issued, snapshotted credentials) with a
status CHECK, unique public_id / certificate_number, and a partial unique
index allowing at most one ACTIVE certificate per enrollment (revoke +
reissue keeps history). No existing table changes. Downgrade drops the
table.

Revision ID: a1d3b6e8f0c5
Revises: f9c2a5d0e7b4
"""
from alembic import op
import sqlalchemy as sa

revision = "a1d3b6e8f0c5"
down_revision = "f9c2a5d0e7b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "learning_certificates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=36), nullable=False),
        sa.Column("certificate_number", sa.String(length=40), nullable=False),
        sa.Column("learning_program_id", sa.Integer(), nullable=False),
        sa.Column("enrollment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_name", sa.String(length=200), nullable=False),
        sa.Column("program_title", sa.String(length=200), nullable=False),
        sa.Column("instructor_names", sa.JSON(), nullable=False),
        sa.Column("issuer_name", sa.String(length=200), nullable=False),
        sa.Column("certificate_title", sa.String(length=120), nullable=False),
        sa.Column("signatory_name", sa.String(length=120), nullable=True),
        sa.Column("signatory_title", sa.String(length=120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("template_version", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revocation_reason", sa.String(length=500), nullable=True),
        sa.Column("replaces_certificate_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("status IN ('active', 'revoked')", name="ck_learning_certificates_status"),
        sa.ForeignKeyConstraint(["learning_program_id"], ["learning_programs.id"]),
        sa.ForeignKeyConstraint(["enrollment_id"], ["learning_enrollments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["replaces_certificate_id"], ["learning_certificates.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("certificate_number"),
    )
    op.create_index("ix_learning_certificates_public_id", "learning_certificates", ["public_id"], unique=True)
    op.create_index("ix_learning_certificates_learning_program_id", "learning_certificates", ["learning_program_id"])
    op.create_index("ix_learning_certificates_enrollment_id", "learning_certificates", ["enrollment_id"])
    op.create_index("ix_learning_certificates_user_id", "learning_certificates", ["user_id"])
    op.create_index(
        "uq_learning_certificates_one_active_per_enrollment", "learning_certificates", ["enrollment_id"], unique=True,
        postgresql_where=sa.text("status = 'active'"), sqlite_where=sa.text("status = 'active'"),
    )


def downgrade():
    op.drop_index("uq_learning_certificates_one_active_per_enrollment", table_name="learning_certificates")
    op.drop_index("ix_learning_certificates_user_id", table_name="learning_certificates")
    op.drop_index("ix_learning_certificates_enrollment_id", table_name="learning_certificates")
    op.drop_index("ix_learning_certificates_learning_program_id", table_name="learning_certificates")
    op.drop_index("ix_learning_certificates_public_id", table_name="learning_certificates")
    op.drop_table("learning_certificates")
