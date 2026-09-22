"""author cms fields: status, seo, person link, topics, bio blocks

Revision ID: 43cc471681b6
Revises: a4a1d57e5dc4
Create Date: 2026-09-22 09:23:50.377133

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43cc471681b6'
down_revision = 'a4a1d57e5dc4'
branch_labels = None
depends_on = None


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to these Author CMS fields, already called out (and left
    # unaddressed) in prior migrations.
    op.create_table(
        'author_topics',
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['author_id'], ['authors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('author_id', 'topic_id'),
    )

    with op.batch_alter_table('authors', schema=None) as batch_op:
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('person_id', sa.Integer(), nullable=True))
        batch_op.create_check_constraint('ck_authors_status', "status IN ('draft', 'active', 'archived')")
        batch_op.create_foreign_key('fk_authors_person_id', 'people', ['person_id'], ['id'])

    # Every existing Author row predates this status field and was already
    # publicly listed (there was no draft/active distinction before) —
    # backfill them as active so this migration doesn't silently pull
    # already-live bylines off the public site. Only rows created after
    # this migration get the 'draft' default above.
    op.execute("UPDATE authors SET status = 'active'")

    # bio moves from plain Text to an ordered content-block list (same
    # shape as Article.content / Person.bio) — existing plain-text
    # biographies are preserved as a single paragraph block.
    op.execute(
        """
        ALTER TABLE authors ALTER COLUMN bio TYPE JSON USING (
            CASE
                WHEN bio IS NULL OR bio = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', bio))
            END
        )
        """
    )
    op.execute("ALTER TABLE authors ALTER COLUMN bio SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE authors ALTER COLUMN bio SET NOT NULL")


def downgrade():
    with op.batch_alter_table('authors', schema=None) as batch_op:
        batch_op.drop_constraint('fk_authors_person_id', type_='foreignkey')
        batch_op.drop_constraint('ck_authors_status', type_='check')

    op.execute("ALTER TABLE authors ALTER COLUMN bio DROP DEFAULT")
    op.execute("ALTER TABLE authors ALTER COLUMN bio DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE authors ALTER COLUMN bio TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(bio::jsonb) = 0 THEN NULL
                ELSE (bio::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('authors', schema=None) as batch_op:
        batch_op.drop_column('person_id')
        batch_op.drop_column('seo')
        batch_op.drop_column('status')

    op.drop_table('author_topics')
