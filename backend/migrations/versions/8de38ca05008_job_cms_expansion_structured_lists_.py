"""job cms expansion: structured lists, status expansion, sponsor

Revision ID: 8de38ca05008
Revises: 21e6be1a454e
Create Date: 2026-09-22 16:52:50.175910

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8de38ca05008'
down_revision = '21e6be1a454e'
branch_labels = None
depends_on = None

OLD_JOB_STATUSES = ("draft", "published", "expired", "closed")
NEW_JOB_STATUSES = ("draft", "review", "scheduled", "published", "expired", "archived")


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to this Job CMS expansion, already called out (and left
    # unaddressed) in prior migrations.
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('salary_visible', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('responsibilities', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('requirements', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('qualifications', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('skills', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('benefits', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('application_email', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('sponsor_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_jobs_sponsor_id', 'sponsors', ['sponsor_id'], ['id'])

    # Drop the old status CHECK constraint before backfilling below —
    # "archived" isn't a valid value under it yet.
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('ck_jobs_status', type_='check')

    # Backfill pre-existing rows before tightening to NOT NULL below.
    op.execute("UPDATE jobs SET salary_visible = true WHERE salary_visible IS NULL")
    op.execute("UPDATE jobs SET responsibilities = '[]'::json WHERE responsibilities IS NULL")
    op.execute("UPDATE jobs SET requirements = '[]'::json WHERE requirements IS NULL")
    op.execute("UPDATE jobs SET qualifications = '[]'::json WHERE qualifications IS NULL")
    op.execute("UPDATE jobs SET skills = '[]'::json WHERE skills IS NULL")
    op.execute("UPDATE jobs SET benefits = '[]'::json WHERE benefits IS NULL")
    # "closed" (manually closed to applications) folds into "archived"
    # (retained for record, not promoted) — the new "expired" status now
    # covers both the automatic deadline-passed case and a poster's manual
    # close, matching the archived/expired split already used by
    # Opportunities and Events.
    op.execute("UPDATE jobs SET status = 'archived' WHERE status = 'closed'")

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('salary_visible', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('responsibilities', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('requirements', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('qualifications', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('skills', existing_type=sa.JSON(), nullable=False)
        batch_op.alter_column('benefits', existing_type=sa.JSON(), nullable=False)
        batch_op.create_check_constraint(
            'ck_jobs_status', "status IN (" + ", ".join(f"'{s}'" for s in NEW_JOB_STATUSES) + ")"
        )


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('ck_jobs_status', type_='check')

    op.execute("UPDATE jobs SET status = 'closed' WHERE status = 'archived'")
    op.execute("UPDATE jobs SET status = 'draft' WHERE status IN ('review', 'scheduled')")

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.create_check_constraint(
            'ck_jobs_status', "status IN (" + ", ".join(f"'{s}'" for s in OLD_JOB_STATUSES) + ")"
        )
        batch_op.drop_constraint('fk_jobs_sponsor_id', type_='foreignkey')
        batch_op.drop_column('sponsor_id')
        batch_op.drop_column('application_email')
        batch_op.drop_column('benefits')
        batch_op.drop_column('skills')
        batch_op.drop_column('qualifications')
        batch_op.drop_column('requirements')
        batch_op.drop_column('responsibilities')
        batch_op.drop_column('salary_visible')
        batch_op.drop_column('city')
