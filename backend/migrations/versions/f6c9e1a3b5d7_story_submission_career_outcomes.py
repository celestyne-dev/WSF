"""Story submissions: optional career outcome fields.

Adds outcome_type, outcome_publish_consent (default false),
outcome_attribution (default 'anonymous'), outcome_status (default
'none', indexed), outcome_summary and outcome_approved_at to
story_submissions, with CHECK constraints for the controlled values.
Existing submissions get the safe defaults (no outcome, not public).
Downgrade drops the constraints, index and columns.

Revision ID: f6c9e1a3b5d7
Revises: e5b8d0f2a4c6
"""
from alembic import op
import sqlalchemy as sa

revision = "f6c9e1a3b5d7"
down_revision = "e5b8d0f2a4c6"
branch_labels = None
depends_on = None

_TYPES = ("new_job", "promotion", "pay_increase", "career_change", "returned_to_work",
          "started_business", "leadership_role", "new_qualification")


def _in(column, values, nullable=False):
    listed = ", ".join(f"'{v}'" for v in values)
    return f"{column} IS NULL OR {column} IN ({listed})" if nullable else f"{column} IN ({listed})"


def upgrade():
    with op.batch_alter_table("story_submissions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("outcome_type", sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column("outcome_publish_consent", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column("outcome_attribution", sa.String(length=20), nullable=False, server_default="anonymous"))
        batch_op.add_column(sa.Column("outcome_status", sa.String(length=20), nullable=False, server_default="none"))
        batch_op.add_column(sa.Column("outcome_summary", sa.String(length=280), nullable=True))
        batch_op.add_column(sa.Column("outcome_approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_story_submissions_outcome_status", ["outcome_status"], unique=False)
        batch_op.create_check_constraint("ck_story_submissions_outcome_type", _in("outcome_type", _TYPES, nullable=True))
        batch_op.create_check_constraint(
            "ck_story_submissions_outcome_status", _in("outcome_status", ("none", "pending", "approved", "rejected"))
        )
        batch_op.create_check_constraint(
            "ck_story_submissions_outcome_attribution", _in("outcome_attribution", ("anonymous", "first_name"))
        )


def downgrade():
    with op.batch_alter_table("story_submissions", schema=None) as batch_op:
        batch_op.drop_constraint("ck_story_submissions_outcome_attribution", type_="check")
        batch_op.drop_constraint("ck_story_submissions_outcome_status", type_="check")
        batch_op.drop_constraint("ck_story_submissions_outcome_type", type_="check")
        batch_op.drop_index("ix_story_submissions_outcome_status")
        batch_op.drop_column("outcome_approved_at")
        batch_op.drop_column("outcome_summary")
        batch_op.drop_column("outcome_status")
        batch_op.drop_column("outcome_attribution")
        batch_op.drop_column("outcome_publish_consent")
        batch_op.drop_column("outcome_type")
