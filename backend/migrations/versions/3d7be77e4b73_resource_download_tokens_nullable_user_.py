"""resource download tokens nullable user id

Revision ID: 3d7be77e4b73
Revises: dfa4809c39c5
Create Date: 2026-10-12 15:03:08.370487

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3d7be77e4b73'
down_revision = 'dfa4809c39c5'
branch_labels = None
depends_on = None


def upgrade():
    # Generalizes resource_download_tokens beyond circle_only: a
    # direct_download/email_gate/member_only Resource's uploaded file now
    # also issues a short-lived token through this table, including for an
    # anonymous visitor (direct_download) or one who hasn't authenticated
    # yet at issuance time (email_gate) — see
    # app/services/resource_downloads.py's issue_download_token(). user_id
    # stays purely an audit field (never re-checked at redemption) and the
    # FK/ondelete=CASCADE relationship is unchanged.
    with op.batch_alter_table('resource_download_tokens', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)


def downgrade():
    with op.batch_alter_table('resource_download_tokens', schema=None) as batch_op:
        batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)
