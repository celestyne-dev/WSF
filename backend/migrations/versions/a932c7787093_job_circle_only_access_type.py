"""job circle_only access type

Revision ID: a932c7787093
Revises: 2fbced78e8a6
Create Date: 2026-10-05 03:48:03.035658

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a932c7787093'
down_revision = '2fbced78e8a6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('access_type', sa.String(length=20), nullable=False, server_default='public'))
        batch_op.create_check_constraint('ck_jobs_access_type', "access_type IN ('public', 'circle_only')")

    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.alter_column('access_type', server_default=None)


def downgrade():
    with op.batch_alter_table('jobs', schema=None) as batch_op:
        batch_op.drop_constraint('ck_jobs_access_type', type_='check')
        batch_op.drop_column('access_type')
