"""learning programs courses masterclasses

Revision ID: 760912c88a73
Revises: f0f9a6e94203
Create Date: 2026-09-28 09:36:56.732145

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '760912c88a73'
down_revision = 'f0f9a6e94203'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('learning_programs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('slug', sa.String(length=220), nullable=False),
    sa.Column('subtitle', sa.String(length=300), nullable=True),
    sa.Column('short_description', sa.Text(), nullable=True),
    sa.Column('program_type', sa.String(length=30), nullable=False),
    sa.Column('difficulty_level', sa.String(length=20), nullable=True),
    sa.Column('audience', sa.JSON(), nullable=True),
    sa.Column('overview', sa.JSON(), nullable=False),
    sa.Column('learning_outcomes', sa.JSON(), nullable=True),
    sa.Column('prerequisites', sa.JSON(), nullable=True),
    sa.Column('duration_value', sa.Integer(), nullable=True),
    sa.Column('duration_unit', sa.String(length=10), nullable=True),
    sa.Column('hero_media_id', sa.Integer(), nullable=True),
    sa.Column('primary_instructor_id', sa.Integer(), nullable=True),
    sa.Column('provider_organization_id', sa.Integer(), nullable=True),
    sa.Column('delivery_mode', sa.String(length=20), nullable=False),
    sa.Column('access_type', sa.String(length=20), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=True),
    sa.Column('external_url', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('featured', sa.Boolean(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('seo', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("access_type IN ('free', 'external', 'product')", name='ck_learning_programs_access_type'),
    sa.CheckConstraint("delivery_mode IN ('self_paced', 'live_online', 'in_person', 'hybrid')", name='ck_learning_programs_delivery_mode'),
    sa.CheckConstraint("difficulty_level IS NULL OR difficulty_level IN ('beginner', 'intermediate', 'advanced', 'all_levels')", name='ck_learning_programs_difficulty'),
    sa.CheckConstraint("duration_unit IS NULL OR duration_unit IN ('minutes', 'hours', 'days', 'weeks')", name='ck_learning_programs_duration_unit'),
    sa.CheckConstraint("program_type IN ('course', 'masterclass', 'program', 'learning_series')", name='ck_learning_programs_type'),
    sa.CheckConstraint("status IN ('draft', 'review', 'published', 'archived')", name='ck_learning_programs_status'),
    sa.CheckConstraint('duration_value IS NULL OR duration_value > 0', name='ck_learning_programs_duration_positive'),
    sa.ForeignKeyConstraint(['hero_media_id'], ['media.id'], ),
    sa.ForeignKeyConstraint(['primary_instructor_id'], ['authors.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
    sa.ForeignKeyConstraint(['provider_organization_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('learning_programs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_learning_programs_featured'), ['featured'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_programs_program_type'), ['program_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_learning_programs_slug'), ['slug'], unique=True)
        batch_op.create_index(batch_op.f('ix_learning_programs_status'), ['status'], unique=False)

    op.create_table('learning_modules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('learning_program_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('learning_program_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('learning_program_id', sa.Integer(), nullable=False),
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('learning_program_instructors',
    sa.Column('learning_program_id', sa.Integer(), nullable=False),
    sa.Column('author_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['authors.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('learning_program_id', 'author_id')
    )
    op.create_table('learning_program_related_articles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('learning_program_id', sa.Integer(), nullable=False),
    sa.Column('article_id', sa.Integer(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('learning_program_related_resources',
    sa.Column('learning_program_id', sa.Integer(), nullable=False),
    sa.Column('resource_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('learning_program_id', 'resource_id')
    )
    op.create_table('learning_program_topics',
    sa.Column('learning_program_id', sa.Integer(), nullable=False),
    sa.Column('topic_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['learning_program_id'], ['learning_programs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('learning_program_id', 'topic_id')
    )
    op.create_table('learning_lessons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('module_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('lesson_type', sa.String(length=20), nullable=False),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('content', sa.JSON(), nullable=False),
    sa.Column('article_id', sa.Integer(), nullable=True),
    sa.Column('resource_id', sa.Integer(), nullable=True),
    sa.Column('external_url', sa.String(length=500), nullable=True),
    sa.Column('duration_minutes', sa.Integer(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.CheckConstraint("lesson_type IN ('article', 'resource', 'video', 'activity', 'external_link', 'text')", name='ck_learning_lessons_type'),
    sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ),
    sa.ForeignKeyConstraint(['module_id'], ['learning_modules.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('learning_lessons')
    op.drop_table('learning_program_topics')
    op.drop_table('learning_program_related_resources')
    op.drop_table('learning_program_related_articles')
    op.drop_table('learning_program_instructors')
    op.drop_table('learning_program_events')
    op.drop_table('learning_modules')
    with op.batch_alter_table('learning_programs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_learning_programs_status'))
        batch_op.drop_index(batch_op.f('ix_learning_programs_slug'))
        batch_op.drop_index(batch_op.f('ix_learning_programs_program_type'))
        batch_op.drop_index(batch_op.f('ix_learning_programs_featured'))

    op.drop_table('learning_programs')
