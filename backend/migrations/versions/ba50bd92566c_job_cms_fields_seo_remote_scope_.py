"""job cms fields: seo, remote scope, controlled enums, description blocks

Revision ID: ba50bd92566c
Revises: 63b0af029fa2
Create Date: 2026-09-22 10:12:51.435997

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'ba50bd92566c'
down_revision = '63b0af029fa2'
branch_labels = None
depends_on = None

WORK_MODES = ("On-site", "Hybrid", "Remote")
EMPLOYMENT_TYPES = ("Full-time", "Part-time", "Contract", "Temporary", "Internship")
CAREER_LEVELS = ("Entry level", "Junior", "Mid-level", "Senior", "Manager", "Director", "Executive")
REMOTE_SCOPES = ("worldwide", "country", "region")
REGIONS = (
    "North America",
    "Latin America & Caribbean",
    "Europe",
    "Africa",
    "Asia",
    "Middle East",
    "Oceania",
    "Global",
)


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to these Job CMS fields, already called out (and left
    # unaddressed) in prior migrations.
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('remote_scope', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('remote_region', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('short_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.create_check_constraint(
            'ck_jobs_status', "status IN ('draft', 'published', 'expired', 'closed')"
        )
        batch_op.create_check_constraint(
            'ck_jobs_work_mode', "work_mode IS NULL OR work_mode IN (" + ", ".join(f"'{w}'" for w in WORK_MODES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_jobs_employment_type',
            "employment_type IS NULL OR employment_type IN (" + ", ".join(f"'{e}'" for e in EMPLOYMENT_TYPES) + ")",
        )
        batch_op.create_check_constraint(
            'ck_jobs_career_level',
            "career_level IS NULL OR career_level IN (" + ", ".join(f"'{c}'" for c in CAREER_LEVELS) + ")",
        )
        batch_op.create_check_constraint(
            'ck_jobs_remote_scope',
            "remote_scope IS NULL OR remote_scope IN (" + ", ".join(f"'{s}'" for s in REMOTE_SCOPES) + ")",
        )
        batch_op.create_check_constraint(
            'ck_jobs_remote_region', "remote_region IS NULL OR remote_region IN (" + ", ".join(f"'{r}'" for r in REGIONS) + ")"
        )

    # description moves from plain Text to an ordered content-block list
    # (same shape as Article.content / Person.bio / Organization.description)
    # — existing plain-text descriptions are preserved as a paragraph block.
    op.execute(
        """
        ALTER TABLE jobs ALTER COLUMN description TYPE JSON USING (
            CASE
                WHEN description IS NULL OR description = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', description))
            END
        )
        """
    )
    op.execute("ALTER TABLE jobs ALTER COLUMN description SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE jobs ALTER COLUMN description SET NOT NULL")

    # Fold the old hard-coded Responsibilities/Requirements/Benefits list
    # fields into the now-flexible description content as heading + list
    # blocks — preserving existing data rather than discarding it — before
    # dropping those three now-redundant columns. The app no longer forces
    # these three headings; an editor is free to structure the description
    # however they choose going forward.
    conn = op.get_bind()
    jobs_table = sa.table(
        'jobs',
        sa.column('id', sa.Integer),
        sa.column('description', sa.JSON),
        sa.column('responsibilities', sa.JSON),
        sa.column('requirements', sa.JSON),
        sa.column('benefits', sa.JSON),
    )
    rows = conn.execute(
        sa.select(
            jobs_table.c.id,
            jobs_table.c.description,
            jobs_table.c.responsibilities,
            jobs_table.c.requirements,
            jobs_table.c.benefits,
        )
    ).fetchall()
    for row in rows:
        blocks = list(row.description or [])
        for heading, items in (
            ("Responsibilities", row.responsibilities),
            ("Requirements", row.requirements),
            ("Benefits", row.benefits),
        ):
            if items:
                blocks.append({"type": "heading", "level": 2, "text": heading})
                blocks.append({"type": "list", "style": "bullet", "items": list(items)})
        if blocks != list(row.description or []):
            conn.execute(jobs_table.update().where(jobs_table.c.id == row.id).values(description=blocks))

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_column('requirements')
        batch_op.drop_column('benefits')
        batch_op.drop_column('responsibilities')


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('responsibilities', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('benefits', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))
        batch_op.add_column(sa.Column('requirements', postgresql.JSON(astext_type=sa.Text()), autoincrement=False, nullable=True))

    op.execute("ALTER TABLE jobs ALTER COLUMN description DROP DEFAULT")
    op.execute("ALTER TABLE jobs ALTER COLUMN description DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE jobs ALTER COLUMN description TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(description::jsonb) = 0 THEN NULL
                ELSE (description::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('ck_jobs_remote_region', type_='check')
        batch_op.drop_constraint('ck_jobs_remote_scope', type_='check')
        batch_op.drop_constraint('ck_jobs_career_level', type_='check')
        batch_op.drop_constraint('ck_jobs_employment_type', type_='check')
        batch_op.drop_constraint('ck_jobs_work_mode', type_='check')
        batch_op.drop_constraint('ck_jobs_status', type_='check')
        batch_op.drop_column('seo')
        batch_op.drop_column('short_description')
        batch_op.drop_column('remote_region')
        batch_op.drop_column('remote_scope')
