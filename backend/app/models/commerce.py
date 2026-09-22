import uuid as uuid_lib

from app.extensions import db


class PartnershipInquiry(db.Model):
    __tablename__ = "partnership_inquiries"

    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(200), nullable=False)
    contact_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    interest = db.Column(db.String(200))  # e.g. "Newsletter sponsorship"
    message = db.Column(db.Text)
    status = db.Column(db.String(20), nullable=False, default="new")  # new/contacted/won/lost
    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class Sponsor(db.Model):
    """A currently-active (or scheduled) sponsorship deal — distinct from
    Organization, which is just the company's editorial profile. The same
    Organization can be featured editorially without being a paying
    sponsor, and vice versa.
    """

    __tablename__ = "sponsors"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False)
    tier = db.Column(db.String(50))  # Presenting / Gold / Silver / Community
    active = db.Column(db.Boolean, nullable=False, default=True)
    starts_at = db.Column(db.Date)
    ends_at = db.Column(db.Date)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])


PRODUCT_TYPES = ("digital", "physical", "downloadable", "service", "other")
_PRODUCT_TYPE_CHECK_SQL = "type IN (" + ", ".join(f"'{t}'" for t in PRODUCT_TYPES) + ")"

# draft: incomplete, not yet shown in the Shop. active: live and (subject
# to inventory below) purchasable. unavailable: manually taken off sale by
# an editor but kept visible for record (e.g. temporarily out of stock
# with no restock date). archived: retired, hidden from normal Shop
# results. Availability for an "active" product is further narrowed by
# inventory tracking — see Product.is_available.
PRODUCT_STATUSES = ("draft", "active", "unavailable", "archived")
_PRODUCT_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in PRODUCT_STATUSES) + ")"


class ProductCategory(db.Model):
    """A small, flat Shop-specific taxonomy (Books/Ebooks, Guides,
    Templates, Merchandise, ...) — deliberately separate from the
    editorial Article `Category`/`Topic` models, which describe content
    subject matter rather than a retail catalog structure.
    """

    __tablename__ = "product_categories"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


class ProductImage(db.Model):
    """An ordered supplementary gallery image for a Product, beyond its
    single `cover_media` (the designated primary/hero image). Kept as its
    own small table — rather than a JSON list of media IDs — so ordering
    is a real, queryable column instead of living only in JSON.
    """

    __tablename__ = "product_images"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    media = db.relationship("Media", foreign_keys=[media_id])


class Product(db.Model):
    """WSF Shop catalog entry. Today this mostly wraps a premium
    downloadable Resource (see frontend's ShopPage, which lists premium
    resources directly); `resource_id` is optional so future product
    types (event tickets, memberships) don't need one.
    """

    __tablename__ = "products"
    __table_args__ = (
        db.CheckConstraint(_PRODUCT_TYPE_CHECK_SQL, name="ck_products_type"),
        db.CheckConstraint(_PRODUCT_STATUS_CHECK_SQL, name="ck_products_status"),
        db.CheckConstraint("price >= 0", name="ck_products_price_nonnegative"),
        db.CheckConstraint("sale_price IS NULL OR sale_price >= 0", name="ck_products_sale_price_nonnegative"),
        db.CheckConstraint("stock_quantity IS NULL OR stock_quantity >= 0", name="ck_products_stock_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)

    short_description = db.Column(db.Text)  # one or two sentences, for cards
    # Ordered content-block list — same shape/sanitizer/editor as
    # Job.description/Opportunity.description/Event.description. The
    # editor structures "About", "What's included", "Specifications" etc.
    # themselves rather than the app hard-coding those sections.
    description = db.Column(db.JSON, nullable=False, default=list)

    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("product_categories.id"), nullable=True)

    type = db.Column(db.String(30), nullable=False, default="digital")
    sku = db.Column(db.String(64))  # optional, internal — not necessarily unique across every legacy row

    price = db.Column(db.Integer, nullable=False, default=0)  # whole currency units, paired with `currency`
    sale_price = db.Column(db.Integer)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    price_visible = db.Column(db.Boolean, nullable=False, default=True)

    track_inventory = db.Column(db.Boolean, nullable=False, default=False)
    stock_quantity = db.Column(db.Integer)
    shipping_notes = db.Column(db.Text)  # physical products only — no shipping calculation

    purchase_url = db.Column(db.String(500))

    featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="active")
    # Kept in sync with `status` (true only when status == "active") so the
    # existing Orders flow — which was built against this flag before this
    # task — keeps working unmodified; Orders/checkout are out of scope
    # here.
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    published_date = db.Column(db.Date)
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    resource = db.relationship("Resource", foreign_keys=[resource_id])
    category = db.relationship("ProductCategory", foreign_keys=[category_id])
    images = db.relationship(
        "ProductImage", order_by="ProductImage.position", cascade="all, delete-orphan", backref="product"
    )


class Order(db.Model):
    """Payment gateway integration (M-Pesa Daraja/STK Push first, per
    config.py's MPESA_* settings) is a pluggable payments.py service that
    isn't wired up yet — this table exists so checkout can be built and
    tested end-to-end against a 'pending_payment' -> 'paid' transition
    an admin (or, later, a webhook) triggers.
    """

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # nullable: guest checkout
    email = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending_payment")
    total_amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")
    payment_provider = db.Column(db.String(30))
    payment_reference = db.Column(db.String(200))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id])
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")


class OrderItem(db.Model):
    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")

    product = db.relationship("Product", foreign_keys=[product_id])
