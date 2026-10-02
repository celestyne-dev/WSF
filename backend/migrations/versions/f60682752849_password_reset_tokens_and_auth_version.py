"""password reset tokens and auth_version

Revision ID: f60682752849
Revises: 950a29bb1ce9
Create Date: 2026-10-02 16:13:10.241666

Hand-pruned after autogenerate: this repo's users/media tables have a
circular FK (media.uploaded_by_id -> users.id, users.avatar_media_id ->
media.id, each declared with use_alter=True to break the cycle at
create-table time) that reliably makes `alembic revision --autogenerate`
emit a phantom add_foreign_key('fk_media_uploaded_by_id', ...) against
that cycle, plus a long tail of unrelated index/constraint drift between
historical migrations and current model metadata (see 950a29bb1ce9 for
the same note). None of that belongs in this migration — it contains only
the two changes this module actually needs: a new password_reset_tokens
table, and users.auth_version.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f60682752849'
down_revision = '950a29bb1ce9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_password_reset_tokens_token_hash'), ['token_hash'], unique=True)
        batch_op.create_index(batch_op.f('ix_password_reset_tokens_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('auth_version', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('auth_version')

    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_password_reset_tokens_user_id'))
        batch_op.drop_index(batch_op.f('ix_password_reset_tokens_token_hash'))

    op.drop_table('password_reset_tokens')
