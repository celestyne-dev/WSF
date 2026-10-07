"""protected resource download tokens

Revision ID: 21f45add6f49
Revises: b8358d96e69b
Create Date: 2026-10-06 21:39:45.339145

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '21f45add6f49'
down_revision = 'b8358d96e69b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'resource_download_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('resource_download_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_resource_download_tokens_resource_id'), ['resource_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_resource_download_tokens_token_hash'), ['token_hash'], unique=True)

    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.add_column(sa.Column('protected_file_path', sa.String(length=500), nullable=True))


def downgrade():
    with op.batch_alter_table('resources', schema=None) as batch_op:
        batch_op.drop_column('protected_file_path')

    with op.batch_alter_table('resource_download_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_resource_download_tokens_token_hash'))
        batch_op.drop_index(batch_op.f('ix_resource_download_tokens_resource_id'))

    op.drop_table('resource_download_tokens')
