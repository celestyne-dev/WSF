"""partnerships cms: contact/org/inquiry fields, controlled type/status,
organization link, assignment, commercial metadata, partnership notes

Revision ID: c4d9f2a8e1b6
Revises: b2c8e1f4a6d7
Create Date: 2026-09-24 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c4d9f2a8e1b6'
down_revision = 'b2c8e1f4a6d7'
branch_labels = None
depends_on = None

PARTNERSHIP_TYPES = (
    "Brand Partnership", "Content Partnership", "Employer Partnership", "Event Partnership",
    "Community Partnership", "Education Partnership", "Resource Partnership", "Recruitment Partnership",
    "Strategic Partnership", "Affiliate Partnership", "Research Partnership", "Other",
)
PARTNERSHIP_STATUSES = (
    "new", "reviewing", "contacted", "qualified", "proposal", "negotiating",
    "active", "completed", "declined", "archived",
)


def upgrade():
    op.create_table(
        'partnership_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('partnership_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['partnership_id'], ['partnership_inquiries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_partnership_notes_partnership_id', 'partnership_notes', ['partnership_id'])

    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('job_title', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('website', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('country_code', sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('partnership_type', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('goals', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('proposed_timing', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('budget_range', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('consent_given', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('assigned_to_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('estimated_value', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('currency', sa.String(length=3), nullable=True))
        batch_op.add_column(sa.Column('commercial_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('proposed_start_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('proposed_end_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('actual_start_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('actual_end_date', sa.Date(), nullable=True))
        batch_op.alter_column('consent_given', server_default=None)

    op.alter_column('partnership_inquiries', 'interest', new_column_name='subject')

    # Preserve any existing rows under the richer status set: "won" was
    # always a closed/active deal, "lost" a closed-out decline.
    op.execute("UPDATE partnership_inquiries SET status = 'active' WHERE status = 'won'")
    op.execute("UPDATE partnership_inquiries SET status = 'declined' WHERE status = 'lost'")

    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.create_foreign_key('fk_partnership_inquiries_country_code', 'countries', ['country_code'], ['code'])
        batch_op.create_foreign_key('fk_partnership_inquiries_organization_id', 'organizations', ['organization_id'], ['id'])
        batch_op.create_foreign_key('fk_partnership_inquiries_assigned_to_id', 'users', ['assigned_to_id'], ['id'])
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_type',
            "partnership_type IS NULL OR partnership_type IN (" + ", ".join(f"'{t}'" for t in PARTNERSHIP_TYPES) + ")",
        )
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_status', "status IN (" + ", ".join(f"'{s}'" for s in PARTNERSHIP_STATUSES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_partnership_inquiries_value_nonnegative', 'estimated_value IS NULL OR estimated_value >= 0'
        )


def downgrade():
    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.drop_constraint('ck_partnership_inquiries_value_nonnegative', type_='check')
        batch_op.drop_constraint('ck_partnership_inquiries_status', type_='check')
        batch_op.drop_constraint('ck_partnership_inquiries_type', type_='check')
        batch_op.drop_constraint('fk_partnership_inquiries_assigned_to_id', type_='foreignkey')
        batch_op.drop_constraint('fk_partnership_inquiries_organization_id', type_='foreignkey')
        batch_op.drop_constraint('fk_partnership_inquiries_country_code', type_='foreignkey')

    op.execute("UPDATE partnership_inquiries SET status = 'won' WHERE status IN ('active', 'completed', 'qualified', 'proposal', 'negotiating')")
    op.execute("UPDATE partnership_inquiries SET status = 'lost' WHERE status IN ('declined', 'archived')")
    op.execute("UPDATE partnership_inquiries SET status = 'new' WHERE status = 'reviewing'")

    op.alter_column('partnership_inquiries', 'subject', new_column_name='interest')

    with op.batch_alter_table('partnership_inquiries', schema=None) as batch_op:
        batch_op.drop_column('actual_end_date')
        batch_op.drop_column('actual_start_date')
        batch_op.drop_column('proposed_end_date')
        batch_op.drop_column('proposed_start_date')
        batch_op.drop_column('commercial_notes')
        batch_op.drop_column('currency')
        batch_op.drop_column('estimated_value')
        batch_op.drop_column('assigned_to_id')
        batch_op.drop_column('consent_given')
        batch_op.drop_column('budget_range')
        batch_op.drop_column('proposed_timing')
        batch_op.drop_column('goals')
        batch_op.drop_column('partnership_type')
        batch_op.drop_column('organization_id')
        batch_op.drop_column('country_code')
        batch_op.drop_column('website')
        batch_op.drop_column('job_title')
        batch_op.drop_column('phone')

    op.drop_index('ix_partnership_notes_partnership_id', table_name='partnership_notes')
    op.drop_table('partnership_notes')
