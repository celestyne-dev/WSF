"""wsf circle plans and subscriptions

Revision ID: 8997e4aeceae
Revises: 509f03b3fbc1
Create Date: 2026-10-04 11:00:34.347551

Note: autogenerate against this schema always proposes a spurious
circular fk_media_uploaded_by_id FK plus unrelated index/constraint churn
across articles, events, jobs, newsletter_subscribers, opportunities,
pages, partnership_notes, people, resource_leads, resources, and
sponsor_placements (same known drift documented in migrations
950a29bb1ce9, f60682752849, 8810f944a069, 183f1eff1d95, 9d6e247ed047,
509f03b3fbc1). All of that has been pruned from this migration — it
contains only the new circle_plans/circle_subscriptions tables.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8997e4aeceae'
down_revision = '509f03b3fbc1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'circle_plans',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('short_description', sa.Text(), nullable=True),
        sa.Column('description', sa.JSON(), nullable=False),
        sa.Column('billing_interval', sa.String(length=10), nullable=False),
        sa.Column('price', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('featured', sa.Boolean(), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False),
        sa.Column('checkout_url', sa.String(length=500), nullable=True),
        sa.Column('manage_billing_url', sa.String(length=500), nullable=True),
        sa.Column('benefits', sa.JSON(), nullable=False),
        sa.Column('seo', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("billing_interval IN ('monthly', 'yearly')", name='ck_circle_plans_billing_interval'),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived')", name='ck_circle_plans_status'),
        sa.CheckConstraint('price >= 0', name='ck_circle_plans_price_nonnegative'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('circle_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_circle_plans_slug'), ['slug'], unique=True)

    op.create_table(
        'circle_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('provider_customer_id', sa.String(length=200), nullable=True),
        sa.Column('provider_subscription_id', sa.String(length=200), nullable=True),
        sa.Column('payment_reference', sa.String(length=200), nullable=True),
        sa.Column('starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("source IN ('external', 'manual', 'complimentary')", name='ck_circle_subscriptions_source'),
        sa.CheckConstraint(
            "status IN ('pending', 'active', 'past_due', 'cancelled', 'expired', 'revoked')",
            name='ck_circle_subscriptions_status',
        ),
        sa.CheckConstraint(
            'current_period_end IS NULL OR current_period_start IS NULL OR current_period_end >= current_period_start',
            name='ck_circle_subscriptions_period_order',
        ),
        sa.ForeignKeyConstraint(['plan_id'], ['circle_plans.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('circle_subscriptions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_circle_subscriptions_plan_id'), ['plan_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_circle_subscriptions_user_id'), ['user_id'], unique=False)
        batch_op.create_index(
            'uq_circle_subscriptions_one_current_per_user',
            ['user_id'],
            unique=True,
            postgresql_where=sa.text("status IN ('pending', 'active', 'past_due')"),
        )


def downgrade():
    with op.batch_alter_table('circle_subscriptions', schema=None) as batch_op:
        batch_op.drop_index(
            'uq_circle_subscriptions_one_current_per_user',
            postgresql_where=sa.text("status IN ('pending', 'active', 'past_due')"),
        )
        batch_op.drop_index(batch_op.f('ix_circle_subscriptions_user_id'))
        batch_op.drop_index(batch_op.f('ix_circle_subscriptions_plan_id'))

    op.drop_table('circle_subscriptions')
    with op.batch_alter_table('circle_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_circle_plans_slug'))

    op.drop_table('circle_plans')
