"""opportunity cms fields

Revision ID: aabcdab0aba4
Revises: ba50bd92566c
Create Date: 2026-09-22 10:59:02.641372

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'aabcdab0aba4'
down_revision = 'ba50bd92566c'
branch_labels = None
depends_on = None

OPPORTUNITY_TYPES = (
    "Scholarship",
    "Fellowship",
    "Grant",
    "Award",
    "Competition",
    "Accelerator",
    "Incubator",
    "Training Program",
    "Mentorship Program",
    "Internship",
    "Volunteer Opportunity",
    "Conference Opportunity",
    "Funding Opportunity",
    "Other",
)
OPPORTUNITY_STATUSES = ("draft", "published", "closed", "archived")
FUNDING_TYPES = ("fully_funded", "partially_funded", "stipend", "unpaid", "not_applicable")


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to these Opportunity CMS fields, already called out (and
    # left unaddressed) in prior migrations.
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('short_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('eligibility_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('career_stage', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('funding_type', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('funding_min', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('funding_max', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column('application_instructions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('opening_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('published_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('expiry_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.create_check_constraint(
            'ck_opportunities_type',
            "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in OPPORTUNITY_TYPES) + ")",
        )
        batch_op.create_check_constraint(
            'ck_opportunities_status', "status IN (" + ", ".join(f"'{s}'" for s in OPPORTUNITY_STATUSES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_opportunities_funding_type',
            "funding_type IS NULL OR funding_type IN (" + ", ".join(f"'{f}'" for f in FUNDING_TYPES) + ")",
        )

    # Existing rows predate the "published" workflow concept and were
    # always implicitly public — backfill published_date so they keep
    # sorting/behaving like normally-published listings.
    op.execute("UPDATE opportunities SET published_date = CURRENT_DATE WHERE status = 'published'")

    # description moves from plain Text to an ordered content-block list
    # (same shape as Job.description / Article.content) — existing
    # plain-text descriptions are preserved as a paragraph block.
    op.execute(
        """
        ALTER TABLE opportunities ALTER COLUMN description TYPE JSON USING (
            CASE
                WHEN description IS NULL OR description = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', description))
            END
        )
        """
    )
    op.execute("ALTER TABLE opportunities ALTER COLUMN description SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE opportunities ALTER COLUMN description SET NOT NULL")


def downgrade():
    op.execute("ALTER TABLE opportunities ALTER COLUMN description DROP DEFAULT")
    op.execute("ALTER TABLE opportunities ALTER COLUMN description DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE opportunities ALTER COLUMN description TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(description::jsonb) = 0 THEN NULL
                ELSE (description::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.drop_constraint('ck_opportunities_funding_type', type_='check')
        batch_op.drop_constraint('ck_opportunities_status', type_='check')
        batch_op.drop_constraint('ck_opportunities_type', type_='check')
        batch_op.drop_column('seo')
        batch_op.drop_column('expiry_date')
        batch_op.drop_column('published_date')
        batch_op.drop_column('opening_date')
        batch_op.drop_column('application_instructions')
        batch_op.drop_column('currency')
        batch_op.drop_column('funding_max')
        batch_op.drop_column('funding_min')
        batch_op.drop_column('funding_type')
        batch_op.drop_column('career_stage')
        batch_op.drop_column('eligibility_notes')
        batch_op.drop_column('short_description')
