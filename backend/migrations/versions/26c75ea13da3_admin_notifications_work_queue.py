"""admin notifications work queue

Revision ID: 26c75ea13da3
Revises: 760912c88a73
Create Date: 2026-09-28 17:47:54.278876

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '26c75ea13da3'
down_revision = '760912c88a73'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('notifications',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipient_user_id', sa.Integer(), nullable=False),
    sa.Column('notification_type', sa.String(length=40), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('message', sa.String(length=400), nullable=False),
    sa.Column('entity_type', sa.String(length=40), nullable=True),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('priority', sa.String(length=10), nullable=False),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_archived', sa.Boolean(), nullable=False),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('dedupe_key', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("entity_type IS NULL OR entity_type IN ('article', 'story_submission', 'nomination', 'contact_inquiry', 'directory_submission', 'mentorship_application', 'partnership')", name='ck_notifications_entity_type'),
    sa.CheckConstraint("notification_type IN ('article_review_requested', 'article_approved', 'story_submission_received', 'nomination_received', 'contact_inquiry_received', 'directory_submission_received', 'mentorship_application_received', 'partnership_inquiry_received')", name='ck_notifications_type'),
    sa.CheckConstraint("priority IN ('normal', 'high')", name='ck_notifications_priority'),
    sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dedupe_key', name='uq_notifications_dedupe_key')
    )
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_notifications_created_at'), ['created_at'], unique=False)
        batch_op.create_index('ix_notifications_recipient_archived_read_created', ['recipient_user_id', 'is_archived', 'is_read', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('notifications', schema=None) as batch_op:
        batch_op.drop_index('ix_notifications_recipient_archived_read_created')
        batch_op.drop_index(batch_op.f('ix_notifications_created_at'))

    op.drop_table('notifications')
