"""Article AI editorial transparency fields

Revision ID: e2a0af293ffb
Revises: be764f52c822
Create Date: 2026-09-21 19:33:08.855706

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e2a0af293ffb'
down_revision = 'be764f52c822'
branch_labels = None
depends_on = None


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to the article AI fields this migration adds, left for a
    # separate, dedicated fix.
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.add_column(sa.Column('ai_involvement', sa.String(length=30), nullable=False, server_default='none'))
        batch_op.add_column(sa.Column('human_reviewed', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('ai_disclosure_required', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('ai_disclosure_text', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('ai_editorial_notes', sa.Text(), nullable=True))
        batch_op.create_check_constraint(
            'ck_articles_ai_involvement', "ai_involvement IN ('none', 'ai_assisted', 'ai_generated_reviewed')"
        )


def downgrade():
    with op.batch_alter_table('articles', schema=None) as batch_op:
        batch_op.drop_constraint('ck_articles_ai_involvement', type_='check')
        batch_op.drop_column('ai_editorial_notes')
        batch_op.drop_column('ai_disclosure_text')
        batch_op.drop_column('ai_disclosure_required')
        batch_op.drop_column('human_reviewed')
        batch_op.drop_column('ai_involvement')
