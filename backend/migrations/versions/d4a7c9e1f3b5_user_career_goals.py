"""Users: private Career Hub goal preferences.

Adds nullable users.career_goals (JSONB list of Career Hub goal keys;
JSONB rather than JSON because existing queries SELECT DISTINCT over
users and Postgres json has no equality operator) and
users.career_goals_prompted_at. Existing users keep null (no goals, not
yet prompted). Downgrade drops both columns.

Revision ID: d4a7c9e1f3b5
Revises: c3f5d8a0b2e7
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "d4a7c9e1f3b5"
down_revision = "c3f5d8a0b2e7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("career_goals", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True))
        batch_op.add_column(sa.Column("career_goals_prompted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("career_goals_prompted_at")
        batch_op.drop_column("career_goals")
