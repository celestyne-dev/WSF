"""products cms expansion: categories, gallery, pricing, status

Revision ID: d0e7856c6bc2
Revises: 8de38ca05008
Create Date: 2026-09-22 17:24:41.960763

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd0e7856c6bc2'
down_revision = '8de38ca05008'
branch_labels = None
depends_on = None

PRODUCT_TYPES = ("digital", "physical", "downloadable", "service", "other")
PRODUCT_STATUSES = ("draft", "active", "unavailable", "archived")


def upgrade():
    # Note: this migration intentionally excludes an unrelated
    # `media.fk_media_uploaded_by_id` foreign key that autogenerate also
    # detected as missing from the live database — pre-existing drift
    # unrelated to this Products CMS expansion, already called out (and
    # left unaddressed) in prior migrations.
    op.create_table(
        'product_categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=140), nullable=False),
        sa.Column('name', sa.String(length=140), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_product_categories_slug'), ['slug'], unique=True)

    op.create_table(
        'product_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('media_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['media_id'], ['media.id']),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # The products table is empty in every environment this migration has
    # run against so far, so new NOT NULL columns can be added directly
    # with a server default rather than needing the usual
    # add-nullable / backfill / tighten dance.
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('short_description', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('category_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sku', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('sale_price', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('price_visible', sa.Boolean(), server_default=sa.true(), nullable=False))
        batch_op.add_column(sa.Column('track_inventory', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('stock_quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('shipping_notes', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('purchase_url', sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column('featured', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.add_column(sa.Column('status', sa.String(length=20), server_default='active', nullable=False))
        batch_op.add_column(sa.Column('published_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('seo', sa.JSON(), nullable=True))
        batch_op.alter_column('price', existing_type=sa.Integer(), server_default='0', nullable=False)
        batch_op.create_foreign_key('fk_products_category_id', 'product_categories', ['category_id'], ['id'])
        batch_op.create_check_constraint(
            'ck_products_type', "type IN (" + ", ".join(f"'{t}'" for t in PRODUCT_TYPES) + ")"
        )
        batch_op.create_check_constraint(
            'ck_products_status', "status IN (" + ", ".join(f"'{s}'" for s in PRODUCT_STATUSES) + ")"
        )
        batch_op.create_check_constraint('ck_products_price_nonnegative', 'price >= 0')
        batch_op.create_check_constraint('ck_products_sale_price_nonnegative', 'sale_price IS NULL OR sale_price >= 0')
        batch_op.create_check_constraint('ck_products_stock_nonnegative', 'stock_quantity IS NULL OR stock_quantity >= 0')

    # description moves from plain Text to an ordered content-block list
    # (same shape as Job.description / Opportunity.description) —
    # existing plain-text descriptions are preserved as a paragraph block.
    op.execute(
        """
        ALTER TABLE products ALTER COLUMN description TYPE JSON USING (
            CASE
                WHEN description IS NULL OR description = '' THEN '[]'::json
                ELSE json_build_array(json_build_object('type', 'paragraph', 'text', description))
            END
        )
        """
    )
    op.execute("ALTER TABLE products ALTER COLUMN description SET DEFAULT '[]'::json")
    op.execute("ALTER TABLE products ALTER COLUMN description SET NOT NULL")


def downgrade():
    op.execute("ALTER TABLE products ALTER COLUMN description DROP DEFAULT")
    op.execute("ALTER TABLE products ALTER COLUMN description DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE products ALTER COLUMN description TYPE TEXT USING (
            CASE
                WHEN jsonb_array_length(description::jsonb) = 0 THEN NULL
                ELSE (description::jsonb -> 0 ->> 'text')
            END
        )
        """
    )

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_constraint('ck_products_stock_nonnegative', type_='check')
        batch_op.drop_constraint('ck_products_sale_price_nonnegative', type_='check')
        batch_op.drop_constraint('ck_products_price_nonnegative', type_='check')
        batch_op.drop_constraint('ck_products_status', type_='check')
        batch_op.drop_constraint('ck_products_type', type_='check')
        batch_op.drop_constraint('fk_products_category_id', type_='foreignkey')
        batch_op.alter_column('price', existing_type=sa.Integer(), server_default=None, nullable=False)
        batch_op.drop_column('seo')
        batch_op.drop_column('published_date')
        batch_op.drop_column('status')
        batch_op.drop_column('featured')
        batch_op.drop_column('purchase_url')
        batch_op.drop_column('shipping_notes')
        batch_op.drop_column('stock_quantity')
        batch_op.drop_column('track_inventory')
        batch_op.drop_column('price_visible')
        batch_op.drop_column('sale_price')
        batch_op.drop_column('sku')
        batch_op.drop_column('category_id')
        batch_op.drop_column('short_description')

    op.drop_table('product_images')
    with op.batch_alter_table('product_categories', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_product_categories_slug'))

    op.drop_table('product_categories')
