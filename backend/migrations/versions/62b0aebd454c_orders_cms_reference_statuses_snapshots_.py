"""orders cms: reference, statuses, snapshots, notes

Revision ID: 62b0aebd454c
Revises: e390330af299
Create Date: 2026-09-22 19:59:04.887852

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '62b0aebd454c'
down_revision = 'e390330af299'
branch_labels = None
depends_on = None

ORDER_STATUSES = ("pending", "confirmed", "processing", "completed", "cancelled", "refunded")
PAYMENT_STATUSES = ("unpaid", "pending", "paid", "failed", "partially_refunded", "refunded")
FULFILLMENT_STATUSES = ("not_applicable", "unfulfilled", "processing", "shipped", "delivered", "cancelled")


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detects as missing from the live database — pre-existing drift
    # unrelated to this Orders CMS work, already called out (and left
    # unaddressed) in every prior migration this session.
    op.create_table(
        'order_notes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # order_items/orders are both empty in every environment this
    # migration has run against so far, so new NOT NULL columns can be
    # added directly with a server default rather than needing the usual
    # add-nullable / backfill / tighten dance.
    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('product_name', sa.String(length=200), nullable=False, server_default=''))
        batch_op.add_column(sa.Column('product_sku', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('product_slug', sa.String(length=220), nullable=True))
        batch_op.add_column(sa.Column('product_type', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('line_total', sa.Integer(), nullable=False, server_default='0'))
        batch_op.alter_column('product_name', server_default=None)
        batch_op.alter_column('line_total', server_default=None)
        batch_op.create_check_constraint('ck_order_items_quantity_positive', 'quantity > 0')
        batch_op.create_check_constraint('ck_order_items_unit_price_nonnegative', 'unit_price >= 0')
        batch_op.create_check_constraint('ck_order_items_line_total_nonnegative', 'line_total >= 0')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reference', sa.String(length=30), nullable=True))
        batch_op.add_column(sa.Column('customer_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('phone', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('billing_address', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('shipping_address', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('order_status', sa.String(length=20), nullable=False, server_default='pending'))
        batch_op.add_column(sa.Column('subtotal_amount', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('discount_amount', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('tax_amount', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('shipping_amount', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('fulfillment_status', sa.String(length=20), nullable=False, server_default='unfulfilled'))
        batch_op.add_column(sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('refund_amount', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('refund_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('refunded_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('cancellation_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('archived', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_orders_reference'), ['reference'], unique=True)
        # `status` (values pending_payment/paid/failed/refunded) really
        # only ever tracked payment state — renamed to `payment_status`
        # and given the fuller PAYMENT_STATUSES vocabulary rather than
        # keeping a second, competing status column.
        batch_op.alter_column('status', new_column_name='payment_status', server_default='pending')
        batch_op.create_check_constraint(
            'ck_orders_order_status', "order_status IN (" + ", ".join(f"'{s}'" for s in ORDER_STATUSES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_orders_payment_status', "payment_status IN (" + ", ".join(f"'{s}'" for s in PAYMENT_STATUSES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_orders_fulfillment_status',
            "fulfillment_status IN (" + ", ".join(f"'{s}'" for s in FULFILLMENT_STATUSES) + ")",
        )
        batch_op.create_check_constraint('ck_orders_total_nonnegative', 'total_amount >= 0')
        batch_op.create_check_constraint('ck_orders_subtotal_nonnegative', 'subtotal_amount >= 0')
        batch_op.create_check_constraint('ck_orders_discount_nonnegative', 'discount_amount >= 0')
        batch_op.create_check_constraint('ck_orders_tax_nonnegative', 'tax_amount >= 0')
        batch_op.create_check_constraint('ck_orders_shipping_nonnegative', 'shipping_amount >= 0')
        batch_op.create_check_constraint('ck_orders_refund_nonnegative', 'refund_amount IS NULL OR refund_amount >= 0')


def downgrade():
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('ck_orders_refund_nonnegative', type_='check')
        batch_op.drop_constraint('ck_orders_shipping_nonnegative', type_='check')
        batch_op.drop_constraint('ck_orders_tax_nonnegative', type_='check')
        batch_op.drop_constraint('ck_orders_discount_nonnegative', type_='check')
        batch_op.drop_constraint('ck_orders_subtotal_nonnegative', type_='check')
        batch_op.drop_constraint('ck_orders_total_nonnegative', type_='check')
        batch_op.drop_constraint('ck_orders_fulfillment_status', type_='check')
        batch_op.drop_constraint('ck_orders_payment_status', type_='check')
        batch_op.drop_constraint('ck_orders_order_status', type_='check')
        batch_op.alter_column('payment_status', new_column_name='status', server_default='pending_payment')
        batch_op.drop_index(batch_op.f('ix_orders_reference'))
        batch_op.drop_column('archived_at')
        batch_op.drop_column('archived')
        batch_op.drop_column('cancellation_reason')
        batch_op.drop_column('cancelled_at')
        batch_op.drop_column('refunded_at')
        batch_op.drop_column('refund_reason')
        batch_op.drop_column('refund_amount')
        batch_op.drop_column('paid_at')
        batch_op.drop_column('fulfillment_status')
        batch_op.drop_column('shipping_amount')
        batch_op.drop_column('tax_amount')
        batch_op.drop_column('discount_amount')
        batch_op.drop_column('subtotal_amount')
        batch_op.drop_column('order_status')
        batch_op.drop_column('shipping_address')
        batch_op.drop_column('billing_address')
        batch_op.drop_column('phone')
        batch_op.drop_column('customer_name')
        batch_op.drop_column('reference')

    with op.batch_alter_table('order_items', schema=None) as batch_op:
        batch_op.drop_constraint('ck_order_items_line_total_nonnegative', type_='check')
        batch_op.drop_constraint('ck_order_items_unit_price_nonnegative', type_='check')
        batch_op.drop_constraint('ck_order_items_quantity_positive', type_='check')
        batch_op.drop_column('line_total')
        batch_op.drop_column('product_type')
        batch_op.drop_column('product_slug')
        batch_op.drop_column('product_sku')
        batch_op.drop_column('product_name')

    op.drop_table('order_notes')
