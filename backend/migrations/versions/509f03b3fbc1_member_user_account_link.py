"""member user account link

Revision ID: 509f03b3fbc1
Revises: 9d6e247ed047
Create Date: 2026-10-04 06:08:31.917320

Note: autogenerate against this schema always proposes a spurious
circular fk_media_uploaded_by_id FK plus unrelated index/constraint churn
across articles, events, jobs, newsletter_subscribers, opportunities,
pages, partnership_notes, people, resource_leads, resources, and
sponsor_placements (same known drift documented in migrations
950a29bb1ce9, f60682752849, 8810f944a069, 183f1eff1d95, 9d6e247ed047).
All of that has been pruned from this migration — it contains only the
members.user_id account-link change.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '509f03b3fbc1'
down_revision = '9d6e247ed047'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_members_user_id'), ['user_id'], unique=True)
        batch_op.create_foreign_key('fk_members_user_id', 'users', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade():
    with op.batch_alter_table('members', schema=None) as batch_op:
        batch_op.drop_constraint('fk_members_user_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_members_user_id'))
        batch_op.drop_column('user_id')
