"""premium resource payment foundation (stage 1)

Revision ID: 9e40ec084a5f
Revises: 3d7be77e4b73
Create Date: 2026-10-14 00:00:00.000000

Additive only: two new tables (resource_purchases, resource_payments).
No changes to any existing Resource row, no currency conversion, no
changes to circle_plans/circle_subscriptions/circle_payments. See
app/models/resource.py's ResourcePurchase/ResourcePayment and
app/services/resource_payments.py for the full design — Stage 1 of the
premium Resource Paystack integration (checkout/webhook/entitlement
backend only; no frontend checkout UI yet).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '9e40ec084a5f'
down_revision = '3d7be77e4b73'
branch_labels = None
depends_on = None

RESOURCE_PURCHASE_STATUSES = ("active",)
RESOURCE_PAYMENT_STATUSES = ("pending", "verified", "consumed", "failed", "abandoned")
RESOURCE_PAYMENT_PROVIDERS = ("paystack",)


def upgrade():
    op.create_table(
        'resource_purchases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('payment_reference', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('purchased_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_PURCHASE_STATUSES) + ")",
            name='ck_resource_purchases_status',
        ),
    )
    op.create_index('ix_resource_purchases_user_id', 'resource_purchases', ['user_id'], unique=False)
    op.create_index('ix_resource_purchases_resource_id', 'resource_purchases', ['resource_id'], unique=False)
    op.create_index(
        'uq_resource_purchases_user_resource', 'resource_purchases', ['user_id', 'resource_id'], unique=True,
    )

    op.create_table(
        'resource_payments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference', sa.String(length=100), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('resource_id', sa.Integer(), nullable=False),
        sa.Column('purchase_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=30), nullable=False, server_default='paystack'),
        sa.Column('provider_transaction_id', sa.String(length=64), nullable=True),
        sa.Column('amount_subunits', sa.Integer(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
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
        sa.ForeignKeyConstraint(['resource_id'], ['resources.id']),
        sa.ForeignKeyConstraint(['purchase_id'], ['resource_purchases.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_PAYMENT_STATUSES) + ")",
            name='ck_resource_payments_status',
        ),
        sa.CheckConstraint(
            "provider IN (" + ", ".join(f"'{p}'" for p in RESOURCE_PAYMENT_PROVIDERS) + ")",
            name='ck_resource_payments_provider',
        ),
        sa.CheckConstraint('amount_subunits > 0', name='ck_resource_payments_amount_positive'),
    )
    op.create_index('ix_resource_payments_reference', 'resource_payments', ['reference'], unique=True)
    op.create_index('ix_resource_payments_user_id', 'resource_payments', ['user_id'], unique=False)
    op.create_index('ix_resource_payments_resource_id', 'resource_payments', ['resource_id'], unique=False)
    op.create_index('ix_resource_payments_purchase_id', 'resource_payments', ['purchase_id'], unique=False)
    op.create_index('ix_resource_payments_status', 'resource_payments', ['status'], unique=False)
    op.create_index(
        'uq_resource_payments_provider_transaction_id',
        'resource_payments',
        ['provider_transaction_id'],
        unique=True,
        postgresql_where=sa.text('provider_transaction_id IS NOT NULL'),
    )


def downgrade():
    op.drop_index('uq_resource_payments_provider_transaction_id', table_name='resource_payments')
    op.drop_index('ix_resource_payments_status', table_name='resource_payments')
    op.drop_index('ix_resource_payments_purchase_id', table_name='resource_payments')
    op.drop_index('ix_resource_payments_resource_id', table_name='resource_payments')
    op.drop_index('ix_resource_payments_user_id', table_name='resource_payments')
    op.drop_index('ix_resource_payments_reference', table_name='resource_payments')
    op.drop_table('resource_payments')

    op.drop_index('uq_resource_purchases_user_resource', table_name='resource_purchases')
    op.drop_index('ix_resource_purchases_resource_id', table_name='resource_purchases')
    op.drop_index('ix_resource_purchases_user_id', table_name='resource_purchases')
    op.drop_table('resource_purchases')
