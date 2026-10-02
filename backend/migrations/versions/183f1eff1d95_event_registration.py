"""event registration

Revision ID: 183f1eff1d95
Revises: 8810f944a069
Create Date: 2026-10-02 22:37:39.930054

Hand-pruned after autogenerate: this repo's users/media tables have a
circular FK (media.uploaded_by_id -> users.id, users.avatar_media_id ->
media.id, each declared with use_alter=True to break the cycle at
create-table time) that reliably makes `alembic revision --autogenerate`
emit a phantom add_foreign_key('fk_media_uploaded_by_id', ...) against
that cycle, plus a long tail of unrelated index/constraint drift between
historical migrations and current model metadata (see 950a29bb1ce9,
f60682752849 and 8810f944a069 for the same note). None of that belongs
in this migration — it contains only the two changes this module
actually needs: the new event_registrations table, and
events.registration_mode.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '183f1eff1d95'
down_revision = '8810f944a069'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'event_registrations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('registered', 'cancelled', 'attended')", name='ck_event_registrations_status'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('event_id', 'user_id', name='uq_event_registrations_event_user'),
    )
    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_event_registrations_event_id'), ['event_id'], unique=False)
        batch_op.create_index('ix_event_registrations_event_status', ['event_id', 'status'], unique=False)
        batch_op.create_index(batch_op.f('ix_event_registrations_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_event_registrations_user_status', ['user_id', 'status'], unique=False)

    with op.batch_alter_table('events', schema=None) as batch_op:
        # server_default so every existing event row (external
        # registration today, by definition — see Event.registration_mode's
        # own docstring) gets a real, correct value rather than failing
        # the NOT NULL constraint or needing a separate backfill step.
        batch_op.add_column(
            sa.Column('registration_mode', sa.String(length=20), nullable=False, server_default='external')
        )
        batch_op.create_check_constraint(
            'ck_events_registration_mode', "registration_mode IN ('external', 'wsf')"
        )


def downgrade():
    with op.batch_alter_table('events', schema=None) as batch_op:
        batch_op.drop_constraint('ck_events_registration_mode', type_='check')
        batch_op.drop_column('registration_mode')

    with op.batch_alter_table('event_registrations', schema=None) as batch_op:
        batch_op.drop_index('ix_event_registrations_user_status')
        batch_op.drop_index(batch_op.f('ix_event_registrations_user_id'))
        batch_op.drop_index('ix_event_registrations_event_status')
        batch_op.drop_index(batch_op.f('ix_event_registrations_event_id'))

    op.drop_table('event_registrations')
