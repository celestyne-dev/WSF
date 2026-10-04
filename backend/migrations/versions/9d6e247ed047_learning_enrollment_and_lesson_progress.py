"""learning enrollment and lesson progress

Revision ID: 9d6e247ed047
Revises: 183f1eff1d95
Create Date: 2026-10-03 05:07:47.340005

Hand-pruned after autogenerate: this repo has a known phantom-FK/index
drift issue (see the same note in 950a29bb1ce9, f60682752849,
8810f944a069 and 183f1eff1d95) where autogenerate against a scratch DB
always proposes a spurious `fk_media_uploaded_by_id` circular FK plus
unrelated index/constraint churn across articles, events, jobs,
newsletter_subscribers, opportunities, pages, partnership_notes,
people, resource_leads, resources, and sponsor_placements — none of it
real schema drift, all removed here. Only this module's own
learning_enrollments / learning_lesson_progress tables remain.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9d6e247ed047'
down_revision = '183f1eff1d95'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'learning_enrollments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learning_program_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('active', 'withdrawn')", name='ck_learning_enrollments_status'),
        sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('learning_program_id', 'user_id', name='uq_learning_enrollments_program_user'),
    )
    with op.batch_alter_table('learning_enrollments', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_enrollments_learning_program_id'), ['learning_program_id'], unique=False)
        batch_op.create_index('ix_learning_enrollments_program_status', ['learning_program_id', 'status'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_enrollments_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_learning_enrollments_user_status', ['user_id', 'status'], unique=False)

    op.create_table(
        'learning_lesson_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('enrollment_id', sa.Integer(), nullable=False),
        sa.Column('lesson_id', sa.Integer(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['enrollment_id'], ['learning_enrollments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lesson_id'], ['learning_lessons.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('enrollment_id', 'lesson_id', name='uq_learning_lesson_progress_enrollment_lesson'),
    )
    with op.batch_alter_table('learning_lesson_progress', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_lesson_progress_enrollment_id'), ['enrollment_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_lesson_progress_lesson_id'), ['lesson_id'], unique=False)


def downgrade():
    with op.batch_alter_table('learning_lesson_progress', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_lesson_progress_lesson_id'))
        batch_op.drop_index(batch_op.f('ix_learning_lesson_progress_enrollment_id'))

    op.drop_table('learning_lesson_progress')

    with op.batch_alter_table('learning_enrollments', schema=None) as batch_op:
        batch_op.drop_index('ix_learning_enrollments_user_status')
        batch_op.drop_index(batch_op.f('ix_learning_enrollments_user_id'))
        batch_op.drop_index('ix_learning_enrollments_program_status')
        batch_op.drop_index(batch_op.f('ix_learning_enrollments_learning_program_id'))

    op.drop_table('learning_enrollments')
