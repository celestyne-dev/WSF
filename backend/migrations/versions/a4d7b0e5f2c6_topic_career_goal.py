"""WSF Career Hub: optional career goal on Topics.

Adds topics.career_goal (nullable, indexed) with a CHECK over the frozen
goal list. Resources and Learning programs inherit goals from the Topics
they already carry, so no content table changes. Existing topics get NULL.
Downgrade drops only this column, its index and constraint.

Revision ID: a4d7b0e5f2c6
Revises: f3c6a9d4e1b5
"""
from alembic import op
import sqlalchemy as sa

revision = "a4d7b0e5f2c6"
down_revision = "f3c6a9d4e1b5"
branch_labels = None
depends_on = None

_GOALS = (
    "find_a_job", "get_promoted", "earn_more", "build_visibility", "leadership", "career_change",
    "return_to_work", "networking", "workplace_challenges", "productivity", "confidence", "ai_at_work",
    "entrepreneurship",
)
_CHECK = "career_goal IS NULL OR career_goal IN (" + ", ".join(f"'{g}'" for g in _GOALS) + ")"


def upgrade():
    with op.batch_alter_table("topics", schema=None) as batch_op:
        batch_op.add_column(sa.Column("career_goal", sa.String(length=30), nullable=True))
        batch_op.create_index("ix_topics_career_goal", ["career_goal"], unique=False)
        batch_op.create_check_constraint("ck_topics_career_goal", _CHECK)


def downgrade():
    with op.batch_alter_table("topics", schema=None) as batch_op:
        batch_op.drop_constraint("ck_topics_career_goal", type_="check")
        batch_op.drop_index("ix_topics_career_goal")
        batch_op.drop_column("career_goal")
