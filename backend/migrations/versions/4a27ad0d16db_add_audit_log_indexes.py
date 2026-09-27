"""add audit log indexes

Revision ID: 4a27ad0d16db
Revises: d4f8b1e6a930
Create Date: 2026-09-27 17:17:43.362940

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '4a27ad0d16db'
down_revision = 'd4f8b1e6a930'
branch_labels = None
depends_on = None


def upgrade():
    # Supports the new Admin Audit Log's filters/sort (app/api/v1/admin_audit.py):
    # created_at (default sort + date range), action, entity_type+entity_id, actor.
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_logs_action'), ['action'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index('ix_audit_logs_entity_type_entity_id', ['entity_type', 'entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_logs_user_id'), ['user_id'], unique=False)


def downgrade():
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_logs_user_id'))
        batch_op.drop_index('ix_audit_logs_entity_type_entity_id')
        batch_op.drop_index(batch_op.f('ix_audit_logs_created_at'))
        batch_op.drop_index(batch_op.f('ix_audit_logs_action'))
