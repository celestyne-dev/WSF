"""Events: post-event content references.

Adds nullable recording_url / recording_provider and SET NULL foreign
keys to an existing Resource, Article and Learning program. References
only (no files, no copies); existing rows are untouched. Downgrade drops
the columns.

Revision ID: c3f5d8a0b2e7
Revises: b2e4c7f9a1d6
"""
from alembic import op
import sqlalchemy as sa

revision = "c3f5d8a0b2e7"
down_revision = "b2e4c7f9a1d6"
branch_labels = None
depends_on = None

_LINKS = (
    ("post_event_resource_id", "resources"),
    ("post_event_article_id", "articles"),
    ("post_event_learning_program_id", "learning_programs"),
)


def upgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("recording_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("recording_provider", sa.String(length=20), nullable=True))
        for column, table in _LINKS:
            batch_op.add_column(sa.Column(column, sa.Integer(), nullable=True))
            batch_op.create_foreign_key(f"fk_events_{column}", table, [column], ["id"], ondelete="SET NULL")


def downgrade():
    with op.batch_alter_table("events", schema=None) as batch_op:
        for column, _table in reversed(_LINKS):
            batch_op.drop_constraint(f"fk_events_{column}", type_="foreignkey")
            batch_op.drop_column(column)
        batch_op.drop_column("recording_provider")
        batch_op.drop_column("recording_url")
