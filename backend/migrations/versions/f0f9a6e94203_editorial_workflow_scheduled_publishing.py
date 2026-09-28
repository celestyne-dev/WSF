"""editorial workflow scheduled publishing

Revision ID: f0f9a6e94203
Revises: 7989310265ab
Create Date: 2026-09-28 06:02:14.724875

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f0f9a6e94203'
down_revision = '7989310265ab'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('approved_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_articles_scheduled_at'), ['scheduled_at'], unique=False)
        batch_op.create_foreign_key('fk_articles_approved_by_user_id', 'users', ['approved_by_user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_constraint('fk_articles_approved_by_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_articles_scheduled_at'))
        batch_op.drop_column('approved_by_user_id')
        batch_op.drop_column('approved_at')
        batch_op.drop_column('scheduled_at')
