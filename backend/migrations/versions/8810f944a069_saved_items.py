"""saved items

Revision ID: 8810f944a069
Revises: f60682752849
Create Date: 2026-10-02 20:27:20.801126

Hand-pruned after autogenerate: this repo's users/media tables have a
circular FK (media.uploaded_by_id -> users.id, users.avatar_media_id ->
media.id, each declared with use_alter=True to break the cycle at
create-table time) that reliably makes `alembic revision --autogenerate`
emit a phantom add_foreign_key('fk_media_uploaded_by_id', ...) against
that cycle, plus a long tail of unrelated index/constraint drift between
historical migrations and current model metadata (see 950a29bb1ce9 and
f60682752849 for the same note). None of that belongs in this migration —
it contains only the one table this module actually needs.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8810f944a069'
down_revision = 'f60682752849'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'saved_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('content_type', sa.String(length=30), nullable=False),
        sa.Column('content_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint(
            "content_type IN ('article', 'job', 'opportunity', 'resource', 'event', 'learning_program')",
            name='ck_saved_items_content_type',
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'content_type', 'content_id', name='uq_saved_items_user_content'),
    )
    with op.batch_alter_table('saved_items', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_saved_items_user_id'), ['user_id'], unique=False)
        batch_op.create_index('ix_saved_items_user_type_created', ['user_id', 'content_type', 'created_at'], unique=False)


def downgrade():
    with op.batch_alter_table('saved_items', schema=None) as batch_op:
        batch_op.drop_index('ix_saved_items_user_type_created')
        batch_op.drop_index(batch_op.f('ix_saved_items_user_id'))

    op.drop_table('saved_items')
