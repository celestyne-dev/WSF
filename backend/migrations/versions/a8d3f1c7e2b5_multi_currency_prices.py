"""multi-currency prices

Revision ID: a8d3f1c7e2b5
Revises: f2c6a8e4d1b9
Create Date: 2026-11-02 14:00:00.000000

WSF Checkout Phase 1: circle_plan_prices and resource_prices — one row per
(parent, ISO 4217 currency), amount in integer MINOR units, real FKs.

Data: every existing purchasable legacy price is EXPLICITLY converted
using its own stored currency's ISO 4217 minor unit (legacy prices were
whole currency units: KES 1000 -> 100000; a zero-decimal currency like
JPY 2500 -> 2500) — never silently reinterpreted:
  * circle_plans with price > 0 (any status, so an archived plan keeps
    its price if reactivated);
  * resources with access_type = 'premium' and price > 0.
A legacy row whose currency isn't a real ISO 4217 code is skipped (it
could never have been charged) and stays non-purchasable until an admin
prices it. Legacy price/currency columns are KEPT for compatibility.
Historical circle_payments/resource_payments amount_subunits snapshots
are not touched.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8d3f1c7e2b5'
down_revision = 'f2c6a8e4d1b9'
branch_labels = None
depends_on = None


def _minor_unit(code):
    # Imported lazily so the migration reads the same reviewed registry the
    # app uses; a frozen copy is not needed because the registry only ever
    # grows (ISO amendments), never changes an existing code's exponent.
    from app.services.currencies import UnknownCurrencyError, minor_unit

    try:
        return minor_unit(code)
    except UnknownCurrencyError:
        return None


def _create(table, parent_col, parent_table):
    op.create_table(
        table,
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(parent_col, sa.Integer(), sa.ForeignKey(f'{parent_table}.id', ondelete='CASCADE'), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('amount_minor', sa.BigInteger(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(parent_col, 'currency', name=f'uq_{table}_{parent_col.replace("_id", "")}_currency'),
        sa.CheckConstraint('amount_minor > 0', name=f'ck_{table}_amount_positive'),
    )
    op.create_index(f'ix_{table}_{parent_col}', table, [parent_col])


def _backfill(conn, select_sql, table, parent_col):
    rows = conn.execute(sa.text(select_sql)).fetchall()
    for parent_id, price, currency in rows:
        code = (currency or '').strip().upper()
        exponent = _minor_unit(code)
        if exponent is None or price is None or price <= 0:
            continue
        conn.execute(
            sa.text(f"INSERT INTO {table} ({parent_col}, currency, amount_minor, enabled) VALUES (:p, :c, :a, :e)"),
            {"p": parent_id, "c": code, "a": int(price) * (10 ** exponent), "e": True},
        )


def upgrade():
    _create('circle_plan_prices', 'plan_id', 'circle_plans')
    _create('resource_prices', 'resource_id', 'resources')
    conn = op.get_bind()
    _backfill(conn, "SELECT id, price, currency FROM circle_plans WHERE price > 0", 'circle_plan_prices', 'plan_id')
    _backfill(
        conn,
        "SELECT id, price, currency FROM resources WHERE access_type = 'premium' AND price > 0",
        'resource_prices',
        'resource_id',
    )


def downgrade():
    op.drop_index('ix_resource_prices_resource_id', table_name='resource_prices')
    op.drop_table('resource_prices')
    op.drop_index('ix_circle_plan_prices_plan_id', table_name='circle_plan_prices')
    op.drop_table('circle_plan_prices')
