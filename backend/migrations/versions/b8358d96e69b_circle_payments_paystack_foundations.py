"""circle payments: paystack payment foundations (module 1)

Revision ID: b8358d96e69b
Revises: a932c7787093
Create Date: 2026-10-05 00:00:00.000000

Additive only: one new table (circle_payments). No changes to
circle_plans or circle_subscriptions. See app/models/circle.py's
CirclePayment and app/services/paystack.py for the full design — this is
Module 1 (foundations) of the approved Paystack Circle integration;
checkout/webhook/activation endpoints are not part of this migration.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b8358d96e69b'
down_revision = 'a932c7787093'
branch_labels = None
depends_on = None

CIRCLE_PAYMENT_STATUSES = ("pending", "verified", "consumed", "failed", "abandoned")
CIRCLE_PAYMENT_PROVIDERS = ("paystack",)
CIRCLE_PLAN_BILLING_INTERVALS = ("monthly", "yearly")


def upgrade():
    op.create_table(
        'circle_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='paystack'),
        sa.Column('provider_transaction_id', sa.String(length=64), nullable=True),
        sa.Column('amount_subunits', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('billing_interval', sa.String(length=10), nullable=False),
        sa.Column('customer_email', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('authorization_url', sa.String(length=500), nullable=True),
        sa.Column('provider_channel', sa.String(length=30), nullable=True),
        sa.Column('provider_snapshot', sa.JSON(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verification_attempt_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['plan_id'], ['circle_plans.id']),
        sa.ForeignKeyConstraint(['subscription_id'], ['circle_subscriptions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in CIRCLE_PAYMENT_STATUSES) + ")",
            name='ck_circle_payments_status',
        ),
        sa.CheckConstraint(
            "provider IN (" + ", ".join(f"'{p}'" for p in CIRCLE_PAYMENT_PROVIDERS) + ")",
            name='ck_circle_payments_provider',
        ),
        sa.CheckConstraint(
            "billing_interval IN (" + ", ".join(f"'{b}'" for b in CIRCLE_PLAN_BILLING_INTERVALS) + ")",
            name='ck_circle_payments_billing_interval',
        ),
        sa.CheckConstraint('amount_subunits > 0', name='ck_circle_payments_amount_positive'),
    )
    op.create_index('ix_circle_payments_reference', 'circle_payments', ['reference'], unique=True)
    op.create_index('ix_circle_payments_user_id', 'circle_payments', ['user_id'], unique=False)
    op.create_index('ix_circle_payments_plan_id', 'circle_payments', ['plan_id'], unique=False)
    op.create_index('ix_circle_payments_subscription_id', 'circle_payments', ['subscription_id'], unique=False)
    op.create_index('ix_circle_payments_status', 'circle_payments', ['status'], unique=False)
    op.create_index(
        'uq_circle_payments_provider_transaction_id',
        'circle_payments',
        ['provider_transaction_id'],
        unique=True,
        postgresql_where=sa.text('provider_transaction_id IS NOT NULL'),
    )


def downgrade():
    op.drop_index('uq_circle_payments_provider_transaction_id', table_name='circle_payments')
    op.drop_index('ix_circle_payments_status', table_name='circle_payments')
    op.drop_index('ix_circle_payments_subscription_id', table_name='circle_payments')
    op.drop_index('ix_circle_payments_plan_id', table_name='circle_payments')
    op.drop_index('ix_circle_payments_user_id', table_name='circle_payments')
    op.drop_index('ix_circle_payments_reference', table_name='circle_payments')
    op.drop_table('circle_payments')
