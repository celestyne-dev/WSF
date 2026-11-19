"""Learning: recording lesson type + video lesson metadata.

Widens ck_learning_lessons_type to allow "recording" and adds nullable
video metadata to learning_lessons (video_provider, transcript,
captions_url, thumbnail_media_id). Existing rows are untouched. Downgrade
converts any "recording" lessons to "video" (keeping their URL) before
restoring the narrower CHECK, then drops the new columns.

Revision ID: b2e4c7f9a1d6
Revises: a1d3b6e8f0c5
"""
from alembic import op
import sqlalchemy as sa

revision = "b2e4c7f9a1d6"
down_revision = "a1d3b6e8f0c5"
branch_labels = None
depends_on = None

_OLD = "lesson_type IN ('article', 'resource', 'video', 'activity', 'external_link', 'text')"
_NEW = "lesson_type IN ('article', 'resource', 'video', 'recording', 'activity', 'external_link', 'text')"


def upgrade():
    with op.batch_alter_table("learning_lessons", schema=None) as batch_op:
        batch_op.drop_constraint("ck_learning_lessons_type", type_="check")
        batch_op.create_check_constraint("ck_learning_lessons_type", _NEW)
        batch_op.add_column(sa.Column("video_provider", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("transcript", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("captions_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("thumbnail_media_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_learning_lessons_thumbnail_media_id", "media", ["thumbnail_media_id"], ["id"], ondelete="SET NULL"
        )


def downgrade():
    op.execute("UPDATE learning_lessons SET lesson_type = 'video' WHERE lesson_type = 'recording'")
    with op.batch_alter_table("learning_lessons", schema=None) as batch_op:
        batch_op.drop_constraint("fk_learning_lessons_thumbnail_media_id", type_="foreignkey")
        batch_op.drop_column("thumbnail_media_id")
        batch_op.drop_column("captions_url")
        batch_op.drop_column("transcript")
        batch_op.drop_column("video_provider")
        batch_op.drop_constraint("ck_learning_lessons_type", type_="check")
        batch_op.create_check_constraint("ck_learning_lessons_type", _OLD)
