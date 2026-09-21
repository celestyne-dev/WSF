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


class Product(db.Model):
    """WSF Shop catalog entry. Today this mostly wraps a premium
    downloadable Resource (see frontend's ShopPage, which lists premium
    resources directly); `resource_id` is optional so future product
    types (event tickets, memberships) don't need one.
    """

    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=True)
    type = db.Column(db.String(30), nullable=False, default="digital_download")
    price = db.Column(db.Integer, nullable=False)  # whole currency units, paired with `currency`
    currency = db.Column(db.String(3), nullable=False, default="USD")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    resource = db.relationship("Resource", foreign_keys=[resource_id])


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
