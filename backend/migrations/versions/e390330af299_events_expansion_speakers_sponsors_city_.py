"""events expansion: speakers, sponsors, city, statuses

Revision ID: e390330af299
Revises: d0e7856c6bc2
Create Date: 2026-09-22 18:17:47.708996

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e390330af299'
down_revision = 'd0e7856c6bc2'
branch_labels = None
depends_on = None

EVENT_TYPES = (
    "Conference", "Summit", "Workshop", "Webinar", "Networking Event", "Panel", "Masterclass",
    "Training", "Community Event", "Career Event", "Leadership Event", "Founder Event",
    "Mentorship Event", "Awards Event", "Other",
)
EVENT_STATUSES = ("draft", "review", "scheduled", "published", "postponed", "cancelled", "archived")


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detects as missing from the live database — pre-existing drift
    # unrelated to this Events expansion, already called out (and left
    # unaddressed) in every prior migration this session.
    #
    # event_speakers/event_sponsors go from plain (event_id, person_id) /
    # (event_id, organization_id) association tables to fuller association
    # OBJECTS (id PK, ordering, fallback fields for a speaker/sponsor with
    # no linked Person/Organization yet). Both tables are effectively
    # empty in every environment this migration has run against so far
    # (1 demo speaker row, 0 sponsor rows), so a clean drop + recreate is
    # far simpler and less error-prone than an in-place composite-PK ->
    # single-PK migration for a couple of rows that seed-demo repopulates
    # anyway.
    op.drop_table('event_speakers')
    op.drop_table('event_sponsors')

    op.create_table(
        'event_speakers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('organization_name', sa.String(length=200), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('headshot_media_id', sa.Integer(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id']),
        sa.ForeignKeyConstraint(['headshot_media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'event_sponsors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=True),
        sa.Column('logo_media_id', sa.Integer(), nullable=True),
        sa.Column('url', sa.String(length=500), nullable=True),
        sa.Column('tier', sa.String(length=50), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['logo_media_id'], ['media.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('city', sa.String(length=120), nullable=True))
        batch_op.drop_constraint('ck_events_type', type_='check')
        batch_op.drop_constraint('ck_events_status', type_='check')
        batch_op.create_check_constraint(
            'ck_events_type', "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in EVENT_TYPES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_events_status', "status IN (" + ", ".join(f"'{s}'" for s in EVENT_STATUSES) + ")"
        )


def downgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_constraint('ck_events_status', type_='check')
        batch_op.drop_constraint('ck_events_type', type_='check')
        batch_op.create_check_constraint(
            'ck_events_type',
            "type IS NULL OR type IN ("
            + ", ".join(
                f"'{t}'"
                for t in (
                    "Conference", "Summit", "Workshop", "Webinar", "Networking Event", "Panel", "Masterclass",
                    "Training", "Community Event", "Career Event", "Founder Event", "Mentorship Event",
                    "Awards Event", "Other",
                )
            )
            + ")",
        )
        batch_op.create_check_constraint(
            'ck_events_status',
            "status IN (" + ", ".join(f"'{s}'" for s in ("draft", "published", "cancelled", "archived")) + ")",
        )
        batch_op.drop_column('city')

    op.drop_table('event_sponsors')
    op.drop_table('event_speakers')

    op.create_table(
        'event_speakers',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id', 'person_id'),
    )
    op.create_table(
        'event_sponsors',
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('event_id', 'organization_id'),
    )
