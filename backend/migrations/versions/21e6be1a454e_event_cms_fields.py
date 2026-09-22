"""event cms fields

Revision ID: 21e6be1a454e
Revises: aabcdab0aba4
Create Date: 2026-09-22 15:34:37.801888

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '21e6be1a454e'
down_revision = 'aabcdab0aba4'
branch_labels = None
depends_on = None

EVENT_TYPES = (
    "Conference",
    "Summit",
    "Workshop",
    "Webinar",
    "Networking Event",
    "Panel",
    "Masterclass",
    "Training",
    "Community Event",
    "Career Event",
    "Founder Event",
    "Mentorship Event",
    "Awards Event",
    "Other",
)
EVENT_FORMATS = ("in-person", "virtual", "hybrid")
EVENT_STATUSES = ("draft", "published", "cancelled", "archived")


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to these Event CMS fields, already called out (and left
    # unaddressed) in prior migrations.
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('short_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('end_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('address', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('virtual_link_public', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('organizer_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('organizer_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('registration_required', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('registration_deadline', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('registration_instructions', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('sold_out', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('published_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('sponsored', sa.Boolean(), nullable=True))
        batch_op.create_foreign_key('fk_events_organizer_id', 'organizations', ['organizer_id'], ['id'])

    # Backfill booleans and published_date for pre-existing rows before
    # tightening to NOT NULL below.
    op.execute("UPDATE events SET virtual_link_public = false WHERE virtual_link_public IS NULL")
    op.execute("UPDATE events SET registration_required = true WHERE registration_required IS NULL")
    op.execute("UPDATE events SET sold_out = false WHERE sold_out IS NULL")
    op.execute("UPDATE events SET sponsored = false WHERE sponsored IS NULL")
    # Existing rows predate the draft/published/cancelled/archived status
    # concept: "upcoming" and "past" were time-computed, not real lifecycle
    # states, so both map to "published" (whether a published event is
    # upcoming or past is now computed from `date`/`end_date` at read
    # time); "cancelled" carries over unchanged.
    op.execute("UPDATE events SET status = 'published' WHERE status IN ('upcoming', 'past')")
    op.execute("UPDATE events SET published_date = CURRENT_DATE WHERE status = 'published'")

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.alter_column('virtual_link_public', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('registration_required', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('sold_out', existing_type=sa.Boolean(), nullable=False)
        batch_op.alter_column('sponsored', existing_type=sa.Boolean(), nullable=False)
        batch_op.create_check_constraint(
            'ck_events_type', "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in EVENT_TYPES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_events_format', "format IS NULL OR format IN (" + ", ".join(f"'{f}'" for f in EVENT_FORMATS) + ")"
        )
        batch_op.create_check_constraint(
            'ck_events_status', "status IN (" + ", ".join(f"'{s}'" for s in EVENT_STATUSES) + ")"
        )

    # description moves from plain Text to an ordered content-block list
    # (same shape as Job.description / Opportunity.description) —
    # existing plain-text descriptions are preserved as a paragraph block.
    op.execute(
        """
        ALTER TABLE events ALTER COLUMN description TYPE JSON USING (
            CASE
                WHEN description IS NULL OR description = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', description))
            END
        )
        """
    )
    op.execute("ALTER TABLE events ALTER COLUMN description SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE events ALTER COLUMN description SET NOT NULL")


def downgrade():
    op.execute("ALTER TABLE events ALTER COLUMN description DROP DEFAULT")
    op.execute("ALTER TABLE events ALTER COLUMN description DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE events ALTER COLUMN description TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(description::jsonb) = 0 THEN NULL
                ELSE (description::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_constraint('ck_events_status', type_='check')
        batch_op.drop_constraint('ck_events_format', type_='check')
        batch_op.drop_constraint('ck_events_type', type_='check')
        batch_op.drop_constraint('fk_events_organizer_id', type_='foreignkey')
        batch_op.drop_column('sponsored')
        batch_op.drop_column('seo')
        batch_op.drop_column('published_date')
        batch_op.drop_column('sold_out')
        batch_op.drop_column('registration_instructions')
        batch_op.drop_column('registration_deadline')
        batch_op.drop_column('registration_required')
        batch_op.drop_column('organizer_name')
        batch_op.drop_column('organizer_id')
        batch_op.drop_column('virtual_link_public')
        batch_op.drop_column('address')
        batch_op.drop_column('end_date')
        batch_op.drop_column('short_description')
