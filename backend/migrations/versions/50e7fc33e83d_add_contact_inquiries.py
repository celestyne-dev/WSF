"""add contact inquiries

Revision ID: 50e7fc33e83d
Revises: 4a27ad0d16db
Create Date: 2026-09-27 19:11:06.809687

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '50e7fc33e83d'
down_revision = '4a27ad0d16db'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('contact_inquiries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=30), nullable=True),
    sa.Column('first_name', sa.String(length=120), nullable=False),
    sa.Column('last_name', sa.String(length=120), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('inquiry_type', sa.String(length=30), nullable=False),
    sa.Column('subject', sa.String(length=200), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('source', sa.String(length=50), nullable=False),
    sa.Column('privacy_acknowledged', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('assigned_to_user_id', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('resolved_by_user_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("inquiry_type IN ('general', 'editorial', 'feedback', 'technical', 'media_press', 'speaking', 'other')", name='ck_contact_inquiries_inquiry_type'),
    sa.CheckConstraint("status IN ('new', 'in_progress', 'resolved', 'closed', 'spam')", name='ck_contact_inquiries_status'),
    sa.ForeignKeyConstraint(['assigned_to_user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('contact_inquiries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_contact_inquiries_assigned_to_user_id'), ['assigned_to_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_contact_inquiries_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_contact_inquiries_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_contact_inquiries_inquiry_type'), ['inquiry_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_contact_inquiries_reference'), ['reference'], unique=True)
        batch_op.create_index(batch_op.f('ix_contact_inquiries_status'), ['status'], unique=False)

    op.create_table('contact_notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('inquiry_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('body', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['inquiry_id'], ['contact_inquiries.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('contact_notes')
    with op.batch_alter_table('contact_inquiries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_contact_inquiries_status'))
        batch_op.drop_index(batch_op.f('ix_contact_inquiries_reference'))
        batch_op.drop_index(batch_op.f('ix_contact_inquiries_inquiry_type'))
        batch_op.drop_index(batch_op.f('ix_contact_inquiries_email'))
        batch_op.drop_index(batch_op.f('ix_contact_inquiries_created_at'))
        batch_op.drop_index(batch_op.f('ix_contact_inquiries_assigned_to_user_id'))

    op.drop_table('contact_inquiries')
