"""newsletter cms: subscriber interests/unsubscribe tokens/expanded status,
issue content blocks/status/scheduling/audience/provider metadata

Revision ID: b2c8e1f4a6d7
Revises: f1a7c9d2b3e4
Create Date: 2026-09-23 13:50:00.000000

"""
import secrets

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c8e1f4a6d7'
down_revision = 'f1a7c9d2b3e4'
branch_labels = None
depends_on = None

SUBSCRIBER_STATUSES = ("active", "unsubscribed", "bounced", "complained")
ISSUE_STATUSES = ("draft", "scheduled", "sent", "archived")


def upgrade():
    op.create_table(
        'newsletter_subscriber_topics',
        sa.Column('subscriber_id', sa.Integer(), nullable=False),
        sa.Column('topic_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['subscriber_id'], ['newsletter_subscribers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['topic_id'], ['topics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('subscriber_id', 'topic_id'),
    )

    with op.batch_alter_table('newsletter_subscribers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('last_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('unsubscribe_token', sa.String(length=64), nullable=True))

    # Backfill a stable, unguessable token for every existing subscriber
    # before the column becomes NOT NULL/UNIQUE.
    conn = op.get_bind()
    subscribers = sa.table('newsletter_subscribers', sa.column('id', sa.Integer), sa.column('unsubscribe_token', sa.String))
    for row in conn.execute(sa.select(subscribers.c.id)).fetchall():
        conn.execute(
            subscribers.update().where(subscribers.c.id == row.id).values(unsubscribe_token=secrets.token_urlsafe(32))
        )

    with op.batch_alter_table('newsletter_subscribers', schema=None) as batch_op:
        batch_op.alter_column('unsubscribe_token', nullable=False)
        batch_op.create_unique_constraint('uq_newsletter_subscribers_unsubscribe_token', ['unsubscribe_token'])
        batch_op.create_index('ix_newsletter_subscribers_unsubscribe_token', ['unsubscribe_token'])
        batch_op.create_check_constraint(
            'ck_newsletter_subscribers_status',
            "status IN (" + ", ".join(f"'{s}'" for s in SUBSCRIBER_STATUSES) + ")",
        )

    with op.batch_alter_table('newsletter_issues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('title', sa.String(length=200), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('preheader', sa.String(length=300), nullable=True))
        batch_op.add_column(sa.Column('content', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('cover_media_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('status', sa.String(length=20), nullable=False, server_default='draft'))
        batch_op.add_column(sa.Column('audience_filter', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('send_timezone', sa.String(length=50), nullable=True, server_default='UTC'))
        batch_op.add_column(sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('provider', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('provider_campaign_id', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('provider_message_id', sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
        )
        batch_op.alter_column('issue_number', nullable=True)
        batch_op.alter_column('title', server_default=None)
        batch_op.alter_column('content', server_default=None)
        batch_op.alter_column('status', server_default=None)
        batch_op.alter_column('send_timezone', server_default=None)
        batch_op.create_foreign_key('fk_newsletter_issues_cover_media_id', 'media', ['cover_media_id'], ['id'])
        batch_op.create_check_constraint(
            'ck_newsletter_issues_status', "status IN (" + ", ".join(f"'{s}'" for s in ISSUE_STATUSES) + ")"
        )
        batch_op.drop_column('send_date')


def downgrade():
    with op.batch_alter_table('newsletter_issues', schema=None) as batch_op:
        batch_op.add_column(sa.Column('send_date', sa.Date(), nullable=True))

    op.execute("UPDATE newsletter_issues SET send_date = COALESCE(scheduled_at::date, CURRENT_DATE)")

    with op.batch_alter_table('newsletter_issues', schema=None) as batch_op:
        batch_op.alter_column('send_date', nullable=False)
        batch_op.drop_constraint('ck_newsletter_issues_status', type_='check')
        batch_op.drop_constraint('fk_newsletter_issues_cover_media_id', type_='foreignkey')
        batch_op.alter_column('issue_number', nullable=False)
        batch_op.drop_column('updated_at')
        batch_op.drop_column('provider_message_id')
        batch_op.drop_column('provider_campaign_id')
        batch_op.drop_column('provider')
        batch_op.drop_column('sent_at')
        batch_op.drop_column('send_timezone')
        batch_op.drop_column('scheduled_at')
        batch_op.drop_column('audience_filter')
        batch_op.drop_column('status')
        batch_op.drop_column('cover_media_id')
        batch_op.drop_column('content')
        batch_op.drop_column('preheader')
        batch_op.drop_column('title')

    with op.batch_alter_table('newsletter_subscribers', schema=None) as batch_op:
        batch_op.drop_constraint('ck_newsletter_subscribers_status', type_='check')
        batch_op.drop_index('ix_newsletter_subscribers_unsubscribe_token')
        batch_op.drop_constraint('uq_newsletter_subscribers_unsubscribe_token', type_='unique')
        batch_op.drop_column('unsubscribe_token')
        batch_op.drop_column('last_name')

    op.drop_table('newsletter_subscriber_topics')
