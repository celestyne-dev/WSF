import uuid as uuid_lib

from app.extensions import db

PARTNERSHIP_TYPES = (
    "Brand Partnership",
    "Content Partnership",
    "Employer Partnership",
    "Event Partnership",
    "Community Partnership",
    "Education Partnership",
    "Resource Partnership",
    "Recruitment Partnership",
    "Strategic Partnership",
    "Affiliate Partnership",
    "Research Partnership",
    "Other",
)
_PARTNERSHIP_TYPE_CHECK_SQL = "partnership_type IS NULL OR partnership_type IN (" + ", ".join(
    f"'{t}'" for t in PARTNERSHIP_TYPES
) + ")"

# new: just submitted, untouched. reviewing: an admin is evaluating it.
# contacted: WSF has replied. qualified: a real opportunity worth
# pursuing. proposal: a proposal/discussion is underway. negotiating:
# terms are being worked out. active: a live partnership. completed: ran
# its course. declined: WSF or the partner passed. archived: retired from
# active view, record kept for business history.
PARTNERSHIP_STATUSES = (
    "new",
    "reviewing",
    "contacted",
    "qualified",
    "proposal",
    "negotiating",
    "active",
    "completed",
    "declined",
    "archived",
)
_PARTNERSHIP_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in PARTNERSHIP_STATUSES) + ")"


class PartnershipInquiry(db.Model):
    """A partnership opportunity, from first public inquiry through to an
    active (and eventually completed/declined) partnership — one evolving
    record rather than a separate "lead" and "partnership" table, since
    nothing about this app's existing architecture draws that line and a
    second table would just duplicate contact/organization/commercial
    fields for no benefit. `status` is what tracks which stage it's in.
    """

    __tablename__ = "partnership_inquiries"
    __table_args__ = (
        db.CheckConstraint(_PARTNERSHIP_TYPE_CHECK_SQL, name="ck_partnership_inquiries_type"),
        db.CheckConstraint(_PARTNERSHIP_STATUS_CHECK_SQL, name="ck_partnership_inquiries_status"),
        db.CheckConstraint(
            "estimated_value IS NULL OR estimated_value >= 0", name="ck_partnership_inquiries_value_nonnegative"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Contact
    contact_name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(50))
    job_title = db.Column(db.String(150))

    # Organization — submitted free-text, since a public inquiry may come
    # from a company that doesn't exist in WSF's Organizations yet.
    # organization_id is set later, only by an admin who deliberately
    # links (or a future Organizations-CMS-created) an existing record —
    # never auto-created from a raw form submission.
    company = db.Column(db.String(200), nullable=False)
    website = db.Column(db.String(500))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)

    # Inquiry
    partnership_type = db.Column(db.String(50))
    subject = db.Column(db.String(200))  # short subject/title, e.g. "Newsletter sponsorship for Q1 launch"
    message = db.Column(db.Text)
    goals = db.Column(db.Text)
    proposed_timing = db.Column(db.String(100))  # freeform, e.g. "Q1 2026" — no fixed calendar structure assumed
    # Freeform, not a hard-coded set of ranges — WSF has no established
    # public pricing strategy to encode into fixed tiers (see PR notes).
    budget_range = db.Column(db.String(100))
    consent_given = db.Column(db.Boolean, nullable=False, default=False)

    status = db.Column(db.String(20), nullable=False, default="new")

    # Internal-only — never serialized to any public response.
    assigned_to_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    estimated_value = db.Column(db.Integer)  # whole currency units, paired with `currency`
    currency = db.Column(db.String(3))  # ISO 4217; no default — never assume USD
    commercial_notes = db.Column(db.Text)

    proposed_start_date = db.Column(db.Date)
    proposed_end_date = db.Column(db.Date)
    actual_start_date = db.Column(db.Date)
    actual_end_date = db.Column(db.Date)

    acquisition = db.Column(db.JSON)
    submitted_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    organization = db.relationship("Organization", foreign_keys=[organization_id])
    assigned_to = db.relationship("User", foreign_keys=[assigned_to_id])
    notes = db.relationship(
        "PartnershipNote",
        order_by="PartnershipNote.created_at.desc()",
        cascade="all, delete-orphan",
        backref="partnership",
    )


class PartnershipNote(db.Model):
    """An internal, staff-only note on a partnership — never returned by
    any public response. Same append-only association-object pattern as
    OrderNote, so each entry carries its own author and timestamp.
    """

    __tablename__ = "partnership_notes"

    id = db.Column(db.Integer, primary_key=True)
    partnership_id = db.Column(db.Integer, db.ForeignKey("partnership_inquiries.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])


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


# pending: just created, nothing confirmed yet. confirmed: reviewed and
# accepted by staff (or auto-confirmed once paid, at admin discretion).
# processing: actively being prepared/fulfilled. completed: done — the
# order's full lifecycle. cancelled/refunded: terminal, non-fulfillment
# outcomes. completed/cancelled/refunded are treated as terminal — the
# route layer refuses a transition back to pending/confirmed/processing
# from any of them, so "Completed" never casually reverts to "Pending".
ORDER_STATUSES = ("pending", "confirmed", "processing", "completed", "cancelled", "refunded")
_ORDER_STATUS_CHECK_SQL = "order_status IN (" + ", ".join(f"'{s}'" for s in ORDER_STATUSES) + ")"
ORDER_STATUS_TERMINAL = ("completed", "cancelled", "refunded")

# Deliberately separate from order_status — a "processing" order can be
# unpaid (invoice sent, payment pending) or a "completed" order can still
# show a manual "paid" record an admin entered by hand. No payment
# gateway is wired up; these are administrative records, not the result of
# real payment processing.
PAYMENT_STATUSES = ("unpaid", "pending", "paid", "failed", "partially_refunded", "refunded")
_PAYMENT_STATUS_CHECK_SQL = "payment_status IN (" + ", ".join(f"'{s}'" for s in PAYMENT_STATUSES) + ")"
PAYMENT_STATUS_TERMINAL = ("refunded",)

# not_applicable: no physical items in the order (pure digital/service) —
# there's nothing to ship. Distinct from "unfulfilled" so a digital-only
# order's list row doesn't read as an outstanding shipping task.
FULFILLMENT_STATUSES = ("not_applicable", "unfulfilled", "processing", "shipped", "delivered", "cancelled")
_FULFILLMENT_STATUS_CHECK_SQL = "fulfillment_status IN (" + ", ".join(f"'{s}'" for s in FULFILLMENT_STATUSES) + ")"


class Order(db.Model):
    """An administrative record of a purchase. No payment gateway is wired
    up (M-Pesa Daraja/STK Push first, per config.py's MPESA_* settings, is
    a pluggable payments.py service that doesn't exist yet) — `reference`
    is what staff and customers use to identify an order; `uuid` remains
    the unguessable lookup key for the existing guest order-confirmation
    endpoint (same access-control role a confirmation-email link plays
    anywhere else), and stays separate from the human-facing reference so
    neither has to serve both purposes.
    """

    __tablename__ = "orders"
    __table_args__ = (
        db.CheckConstraint(_ORDER_STATUS_CHECK_SQL, name="ck_orders_order_status"),
        db.CheckConstraint(_PAYMENT_STATUS_CHECK_SQL, name="ck_orders_payment_status"),
        db.CheckConstraint(_FULFILLMENT_STATUS_CHECK_SQL, name="ck_orders_fulfillment_status"),
        db.CheckConstraint("total_amount >= 0", name="ck_orders_total_nonnegative"),
        db.CheckConstraint("subtotal_amount >= 0", name="ck_orders_subtotal_nonnegative"),
        db.CheckConstraint("discount_amount >= 0", name="ck_orders_discount_nonnegative"),
        db.CheckConstraint("tax_amount >= 0", name="ck_orders_tax_nonnegative"),
        db.CheckConstraint("shipping_amount >= 0", name="ck_orders_shipping_nonnegative"),
        db.CheckConstraint("refund_amount IS NULL OR refund_amount >= 0", name="ck_orders_refund_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    # Human-friendly, unique, immutable after creation — e.g.
    # "WSF-2026-000123". Generated once the row has an id (see
    # app/services/orders.py:generate_order_reference) and never rewritten.
    reference = db.Column(db.String(30), unique=True, nullable=True, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # nullable: guest checkout
    email = db.Column(db.String(255), nullable=False)
    customer_name = db.Column(db.String(200))
    phone = db.Column(db.String(50))
    # {line1, line2, city, region, postalCode, countryCode} — optional,
    # only meaningful when an order actually contains a physical item.
    billing_address = db.Column(db.JSON)
    shipping_address = db.Column(db.JSON)

    order_status = db.Column(db.String(20), nullable=False, default="pending")
    payment_status = db.Column(db.String(20), nullable=False, default="pending")
    fulfillment_status = db.Column(db.String(20), nullable=False, default="unfulfilled")

    # Whole currency units (matches Product.price/Event.ticket_price
    # throughout this app) — integer arithmetic, never floating-point.
    # subtotal is the sum of OrderItem.line_total at creation; discount/
    # tax/shipping default to 0 since checkout doesn't collect them yet.
    # total_amount is fixed at creation and never silently recalculated
    # from current Product prices.
    subtotal_amount = db.Column(db.Integer, nullable=False, default=0)
    discount_amount = db.Column(db.Integer, nullable=False, default=0)
    tax_amount = db.Column(db.Integer, nullable=False, default=0)
    shipping_amount = db.Column(db.Integer, nullable=False, default=0)
    total_amount = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="USD")

    payment_provider = db.Column(db.String(30))
    payment_reference = db.Column(db.String(200))
    paid_at = db.Column(db.DateTime(timezone=True))

    # A manual record of a refund decision — never an instruction to a
    # payment provider to actually move money. payment_status carries the
    # refunded/partially_refunded state; these carry the record details.
    refund_amount = db.Column(db.Integer)
    refund_reason = db.Column(db.Text)
    refunded_at = db.Column(db.DateTime(timezone=True))

    cancelled_at = db.Column(db.DateTime(timezone=True))
    cancellation_reason = db.Column(db.Text)

    archived = db.Column(db.Boolean, nullable=False, default=False)
    archived_at = db.Column(db.DateTime(timezone=True))

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id])
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan")
    notes = db.relationship(
        "OrderNote", order_by="OrderNote.created_at.desc()", cascade="all, delete-orphan", backref="order"
    )


class OrderItem(db.Model):
    """Preserves the commercial facts of a purchase at the time it was
    made. Never re-derive product_name/sku/unit_price/line_total from the
    current Product record — if the Product's price, name, or type
    changes later (or it's archived), this row must keep reading exactly
    as it did on the day of purchase.
    """

    __tablename__ = "order_items"
    __table_args__ = (
        db.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        db.CheckConstraint("unit_price >= 0", name="ck_order_items_unit_price_nonnegative"),
        db.CheckConstraint("line_total >= 0", name="ck_order_items_line_total_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)

    # Snapshots — copied from Product at purchase time, immutable after.
    product_name = db.Column(db.String(200), nullable=False)
    product_sku = db.Column(db.String(64))
    product_slug = db.Column(db.String(220))
    product_type = db.Column(db.String(30))  # see commerce.PRODUCT_TYPES at time of purchase

    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Integer, nullable=False)
    line_total = db.Column(db.Integer, nullable=False)  # quantity * unit_price, fixed at creation
    currency = db.Column(db.String(3), nullable=False, default="USD")

    product = db.relationship("Product", foreign_keys=[product_id])


class OrderNote(db.Model):
    """An internal, staff-only note on an Order — never returned by any
    public/customer-facing response. Its own small append-only table
    (rather than one growing text field) so each entry carries its own
    author and timestamp naturally, the same association-object pattern
    used for ProductImage/EventSpeaker elsewhere in this app.
    """

    __tablename__ = "order_notes"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
