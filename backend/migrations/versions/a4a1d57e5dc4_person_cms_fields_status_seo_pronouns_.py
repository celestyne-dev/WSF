"""person cms fields: status, seo, pronouns, bio blocks

Revision ID: a4a1d57e5dc4
Revises: e2a0af293ffb
Create Date: 2026-09-22 04:23:26.416762

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4a1d57e5dc4'
down_revision = 'e2a0af293ffb'
branch_labels = None
depends_on = None


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to these Person CMS fields, already called out (and left
    # unaddressed) in the prior e2a0af293ffb migration.
    with op.batch_alter_table('people', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pronouns', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.create_check_constraint('ck_people_status', "status IN ('draft', 'published', 'archived')")

    # Every existing Person row predates this status field and was already
    # publicly visible (there was no draft/published distinction before) —
    # backfill them as published so this migration doesn't silently pull
    # already-live profiles off the public site. Only rows created after
    # this migration get the 'draft' default above.
    op.execute("UPDATE people SET status = 'published'")

    # bio moves from plain Text to an ordered content-block list (same
    # shape as Article.content) — existing plain-text biographies are
    # preserved as a single paragraph block rather than discarded.
    op.execute(
        """
        ALTER TABLE people ALTER COLUMN bio TYPE JSON USING (
            CASE
                WHEN bio IS NULL OR bio = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', bio))
            END
        )
        """
    )
    op.execute("ALTER TABLE people ALTER COLUMN bio SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE people ALTER COLUMN bio SET NOT NULL")


def downgrade():
    with op.batch_alter_table('people', schema=None) as batch_op:
        batch_op.drop_constraint('ck_people_status', type_='check')

    op.execute("ALTER TABLE people ALTER COLUMN bio DROP DEFAULT")
    op.execute("ALTER TABLE people ALTER COLUMN bio DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE people ALTER COLUMN bio TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(bio::jsonb) = 0 THEN NULL
                ELSE (bio::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('people', schema=None) as batch_op:
        batch_op.drop_column('seo')
        batch_op.drop_column('status')
        batch_op.drop_column('pronouns')
