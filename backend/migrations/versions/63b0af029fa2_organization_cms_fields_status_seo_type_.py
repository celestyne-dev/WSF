"""organization cms fields: status, seo, type enum, description blocks

Revision ID: 63b0af029fa2
Revises: 43cc471681b6
Create Date: 2026-09-22 09:50:46.837005

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '63b0af029fa2'
down_revision = '43cc471681b6'
branch_labels = None
depends_on = None


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to these Organization CMS fields, already called out (and
    # left unaddressed) in prior migrations.
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('location', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('founded_year', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('short_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.alter_column('org_type', existing_type=sa.VARCHAR(length=80), type_=sa.String(length=40), existing_nullable=True)

    # Free-text org_type values that predate the controlled enum are
    # normalized to their closest match rather than left to violate the
    # new CHECK constraint below.
    op.execute("UPDATE organizations SET org_type = 'company' WHERE org_type = 'Startup'")

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.create_check_constraint('ck_organizations_status', "status IN ('draft', 'published', 'archived')")
        batch_op.create_check_constraint(
            'ck_organizations_org_type',
            "org_type IS NULL OR org_type IN ('company', 'nonprofit', 'foundation', 'government', "
            "'educational_institution', 'media_organization', 'professional_association', "
            "'social_enterprise', 'community_organization', 'other')",
        )

    # Every existing Organization row predates this status field and was
    # already publicly listed — backfill as published so this migration
    # doesn't silently pull already-live organizations off the public site.
    op.execute("UPDATE organizations SET status = 'published'")

    # description moves from plain Text to an ordered content-block list
    # (same shape as Article.content / Person.bio / Author.bio) —
    # existing plain-text descriptions are preserved as a single
    # paragraph block.
    op.execute(
        """
        ALTER TABLE organizations ALTER COLUMN description TYPE JSON USING (
            CASE
                WHEN description IS NULL OR description = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', description))
            END
        )
        """
    )
    op.execute("ALTER TABLE organizations ALTER COLUMN description SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE organizations ALTER COLUMN description SET NOT NULL")


def downgrade():
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_constraint('ck_organizations_org_type', type_='check')
        batch_op.drop_constraint('ck_organizations_status', type_='check')

    op.execute("ALTER TABLE organizations ALTER COLUMN description DROP DEFAULT")
    op.execute("ALTER TABLE organizations ALTER COLUMN description DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE organizations ALTER COLUMN description TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(description::jsonb) = 0 THEN NULL
                ELSE (description::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.alter_column('org_type', existing_type=sa.String(length=40), type_=sa.VARCHAR(length=80), existing_nullable=True)
        batch_op.drop_column('seo')
        batch_op.drop_column('status')
        batch_op.drop_column('short_description')
        batch_op.drop_column('founded_year')
        batch_op.drop_column('location')
