from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.commerce import (
    FULFILLMENT_STATUSES,
    Order,
    OrderItem,
    OrderNote,
    ORDER_STATUSES,
    PARTNERSHIP_STATUSES,
    PARTNERSHIP_TYPES,
    PartnershipInquiry,
    PartnershipNote,
    PAYMENT_STATUSES,
    Product,
    ProductCategory,
    ProductImage,
    PRODUCT_STATUSES,
    PRODUCT_TYPES,
    Sponsor,
)
from app.models.audit import AuditLog
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.people import OrganizationSchema
from app.schemas.resource import ResourceSchema
from app.schemas.user import UserSchema


class PartnershipNoteSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = PartnershipNote
        load_instance = False
        exclude = ("partnership_id",)


class PartnershipInquirySchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump — the full record, including commercial/contact
    fields and internal notes. Never used for a public response.
    """

    country = fields.Nested(CountrySchema, dump_only=True)
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Organization/assignee.
    organization_id = fields.Integer(dump_only=True)
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))
    assigned_to_id = fields.Integer(dump_only=True)
    assigned_to = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))
    notes = fields.Nested(PartnershipNoteSchema, many=True, dump_only=True)

    class Meta:
        model = PartnershipInquiry
        load_instance = False


class PartnershipInquiryConfirmationSchema(ma.Schema):
    """What the public submit endpoint echoes back — a bare confirmation,
    never the record itself (no id, no internal fields).
    """

    company = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    submitted_at = fields.DateTime(dump_only=True, data_key="submittedAt")


class SponsorSchema(ma.SQLAlchemyAutoSchema):
    organization = fields.Nested(OrganizationSchema, dump_only=True)

    class Meta:
        model = Sponsor
        load_instance = False


class PartnershipInquiryInputSchema(ma.Schema):
    # Contact
    contact_name = fields.String(required=True, data_key="contactName", validate=validate.Length(min=1, max=200))
    email = fields.Email(required=True)
    phone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    job_title = fields.String(required=False, allow_none=True, data_key="jobTitle", validate=validate.Length(max=150))

    # Organization — freeform; no existing Organization record required.
    company = fields.String(required=True, validate=validate.Length(min=1, max=200))
    website = fields.String(required=False, allow_none=True, validate=validate.URL(require_tld=True))
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")

    # Inquiry
    partnership_type = fields.String(
        required=False, allow_none=True, data_key="partnershipType", validate=validate.OneOf(PARTNERSHIP_TYPES)
    )
    subject = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))
    message = fields.String(required=False, allow_none=True, validate=validate.Length(max=5000))
    goals = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000))
    proposed_timing = fields.String(required=False, allow_none=True, data_key="proposedTiming", validate=validate.Length(max=100))
    budget_range = fields.String(required=False, allow_none=True, data_key="budgetRange", validate=validate.Length(max=100))

    consent_given = fields.Boolean(required=True, data_key="consentGiven")
    acquisition = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_consent(self, data, **kwargs):
        if not data.get("consent_given"):
            raise ValidationError(
                "Please confirm we can use this information to respond to your inquiry.", field_name="consent_given"
            )


class PartnershipAdminUpdateSchema(ma.Schema):
    """Admin edits to the inquiry's own fields — contact/organization/
    inquiry/commercial content. Status, assignment, and the Organization
    link each go through their own dedicated action so those changes stay
    intentional and auditable rather than a side effect of a general save.
    """

    contact_name = fields.String(required=False, allow_none=True, data_key="contactName", validate=validate.Length(min=1, max=200))
    email = fields.Email(required=False, allow_none=True)
    phone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    job_title = fields.String(required=False, allow_none=True, data_key="jobTitle", validate=validate.Length(max=150))
    company = fields.String(required=False, allow_none=True, validate=validate.Length(min=1, max=200))
    website = fields.String(required=False, allow_none=True, validate=validate.URL(require_tld=True))
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    partnership_type = fields.String(
        required=False, allow_none=True, data_key="partnershipType", validate=validate.OneOf(PARTNERSHIP_TYPES)
    )
    subject = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))
    message = fields.String(required=False, allow_none=True, validate=validate.Length(max=5000))
    goals = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000))
    proposed_timing = fields.String(required=False, allow_none=True, data_key="proposedTiming", validate=validate.Length(max=100))
    budget_range = fields.String(required=False, allow_none=True, data_key="budgetRange", validate=validate.Length(max=100))
    estimated_value = fields.Integer(required=False, allow_none=True, data_key="estimatedValue", validate=validate.Range(min=0))
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    commercial_notes = fields.String(required=False, allow_none=True, data_key="commercialNotes", validate=validate.Length(max=5000))
    proposed_start_date = fields.Date(required=False, allow_none=True, data_key="proposedStartDate")
    proposed_end_date = fields.Date(required=False, allow_none=True, data_key="proposedEndDate")
    actual_start_date = fields.Date(required=False, allow_none=True, data_key="actualStartDate")
    actual_end_date = fields.Date(required=False, allow_none=True, data_key="actualEndDate")


class PartnershipStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(PARTNERSHIP_STATUSES))


class PartnershipAssignInputSchema(ma.Schema):
    assigned_to_id = fields.Integer(required=False, allow_none=True, data_key="assignedToId")


class PartnershipOrganizationLinkInputSchema(ma.Schema):
    organization_slug = fields.String(required=False, allow_none=True, data_key="organizationSlug")


class PartnershipNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=5000))


class SponsorInputSchema(ma.Schema):
    organization_slug = fields.String(required=True, data_key="organizationSlug")
    tier = fields.String(required=False, allow_none=True)
    active = fields.Boolean(required=False, load_default=True)
    starts_at = fields.Date(required=False, allow_none=True, data_key="startsAt")
    ends_at = fields.Date(required=False, allow_none=True, data_key="endsAt")


class ProductCategorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ProductCategory
        load_instance = False


class ProductImageSchema(ma.SQLAlchemyAutoSchema):
    media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = ProductImage
        load_instance = False
        exclude = ("product_id",)


class ProductSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    images = fields.Nested(ProductImageSchema, many=True, dump_only=True)
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Resource/Category.
    resource_id = fields.Integer(dump_only=True)
    resource = fields.Nested(ResourceSchema, dump_only=True, only=("id", "slug", "name"))
    category_id = fields.Integer(dump_only=True)
    category = fields.Nested(ProductCategorySchema, dump_only=True)
    is_available = fields.Method("get_is_available")

    class Meta:
        model = Product
        load_instance = False

    def get_is_available(self, obj):
        """Whether the product can actually be bought right now — combines
        the editorial status with live inventory, computed at read time
        rather than requiring an editor to flip a second switch by hand.
        """
        if obj.status != "active":
            return False
        if obj.track_inventory and (obj.stock_quantity or 0) <= 0:
            return False
        return True


class ProductInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    # Ordered content-block list — same shape as Job.description, sanitized
    # through the same sanitize_content_blocks() service. The editor
    # structures "About"/"What's included"/"Specifications" etc.
    # themselves rather than the app hard-coding those headings.
    description = fields.List(fields.Dict(), required=False, load_default=list)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    gallery_media_ids = fields.List(fields.Integer(), required=False, load_default=list, data_key="galleryMediaIds")
    resource_slug = fields.String(required=False, allow_none=True, data_key="resourceSlug")
    category_id = fields.Integer(required=False, allow_none=True, data_key="categoryId")
    type = fields.String(required=False, load_default="digital", validate=validate.OneOf(PRODUCT_TYPES))
    sku = fields.String(required=False, allow_none=True, validate=validate.Length(max=64))
    price = fields.Integer(required=True, validate=validate.Range(min=0))
    sale_price = fields.Integer(required=False, allow_none=True, data_key="salePrice", validate=validate.Range(min=0))
    currency = fields.String(required=False, load_default="USD", validate=validate.Length(equal=3))
    price_visible = fields.Boolean(required=False, load_default=True, data_key="priceVisible")
    track_inventory = fields.Boolean(required=False, load_default=False, data_key="trackInventory")
    stock_quantity = fields.Integer(required=False, allow_none=True, data_key="stockQuantity", validate=validate.Range(min=0))
    shipping_notes = fields.String(required=False, allow_none=True, data_key="shippingNotes")
    purchase_url = fields.String(required=False, allow_none=True, data_key="purchaseUrl", validate=validate.URL(require_tld=True))
    featured = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="active", validate=validate.OneOf(PRODUCT_STATUSES))
    published_date = fields.Date(required=False, allow_none=True, data_key="publishedDate")
    seo = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_sale_price(self, data, **kwargs):
        price = data.get("price")
        sale_price = data.get("sale_price")
        if sale_price is not None and price is not None and sale_price > price:
            raise ValidationError("Sale price cannot exceed the regular price.", field_name="sale_price")


class OrderItemSchema(ma.SQLAlchemyAutoSchema):
    # A lightweight preview of the CURRENT Product record, so the admin UI
    # can link through to it — never the source of truth for what was
    # actually purchased. product_name/product_sku/product_type/unit_price/
    # line_total below are the immutable snapshot taken at purchase time
    # and are what the CMS actually displays.
    product = fields.Nested(ProductSchema, dump_only=True, only=("id", "slug", "name", "status"))

    class Meta:
        model = OrderItem
        load_instance = False


class OrderNoteSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = OrderNote
        load_instance = False
        exclude = ("order_id",)


class OrderSchema(ma.SQLAlchemyAutoSchema):
    items = fields.Nested(OrderItemSchema, many=True, dump_only=True)
    notes = fields.Nested(OrderNoteSchema, many=True, dump_only=True)
    requires_shipping = fields.Method("get_requires_shipping")

    class Meta:
        model = Order
        load_instance = False

    def get_requires_shipping(self, obj):
        """Whether any item in this order is a physical product — computed
        from each OrderItem's own snapshotted product_type, not the
        current Product record, so this stays accurate even if a Product
        is later reclassified.
        """
        return any(item.product_type == "physical" for item in obj.items)


class OrderItemInputSchema(ma.Schema):
    product_slug = fields.String(required=True, data_key="productSlug")
    quantity = fields.Integer(required=False, load_default=1, validate=validate.Range(min=1))


class OrderAddressInputSchema(ma.Schema):
    line1 = fields.String(required=False, allow_none=True)
    line2 = fields.String(required=False, allow_none=True)
    city = fields.String(required=False, allow_none=True)
    region = fields.String(required=False, allow_none=True)
    postal_code = fields.String(required=False, allow_none=True, data_key="postalCode")
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")


class OrderInputSchema(ma.Schema):
    email = fields.Email(required=True)
    customer_name = fields.String(required=False, allow_none=True, data_key="customerName")
    phone = fields.String(required=False, allow_none=True)
    billing_address = fields.Nested(OrderAddressInputSchema, required=False, allow_none=True, data_key="billingAddress")
    shipping_address = fields.Nested(OrderAddressInputSchema, required=False, allow_none=True, data_key="shippingAddress")
    items = fields.List(fields.Nested(OrderItemInputSchema), required=True, validate=validate.Length(min=1))


class OrderAdminUpdateSchema(ma.Schema):
    """Partial-update payload for the fields an admin may actually change
    on an order after creation. Commercial facts (items, prices, totals)
    are never editable here — see sections 8/9/28 of the task this schema
    was built against.
    """

    order_status = fields.String(required=False, allow_none=True, data_key="orderStatus", validate=validate.OneOf(ORDER_STATUSES))
    payment_status = fields.String(required=False, allow_none=True, data_key="paymentStatus", validate=validate.OneOf(PAYMENT_STATUSES))
    fulfillment_status = fields.String(
        required=False, allow_none=True, data_key="fulfillmentStatus", validate=validate.OneOf(FULFILLMENT_STATUSES)
    )
    payment_provider = fields.String(required=False, allow_none=True, data_key="paymentProvider")
    payment_reference = fields.String(required=False, allow_none=True, data_key="paymentReference")
    refund_amount = fields.Integer(required=False, allow_none=True, data_key="refundAmount", validate=validate.Range(min=0))
    refund_reason = fields.String(required=False, allow_none=True, data_key="refundReason")


class OrderCancelInputSchema(ma.Schema):
    reason = fields.String(required=False, allow_none=True)


class OrderNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1))


class OrderHistoryEntrySchema(ma.SQLAlchemyAutoSchema):
    """Reuses the existing app-wide AuditLog (app/services/audit.py) —
    scoped here to just the entries for one Order rather than building a
    separate Order-status-history table or a general audit-log viewer.
    """

    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = AuditLog
        load_instance = False
