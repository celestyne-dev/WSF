from marshmallow import fields, validate

from app.extensions import ma
from app.models.commerce import Order, OrderItem, PartnershipInquiry, Product, Sponsor
from app.schemas.media import MediaSchema
from app.schemas.people import OrganizationSchema


class PartnershipInquirySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = PartnershipInquiry
        load_instance = False


class SponsorSchema(ma.SQLAlchemyAutoSchema):
    organization = fields.Nested(OrganizationSchema, dump_only=True)

    class Meta:
        model = Sponsor
        load_instance = False


class PartnershipInquiryInputSchema(ma.Schema):
    company = fields.String(required=True, validate=validate.Length(min=1, max=200))
    contact_name = fields.String(required=True, data_key="contactName")
    email = fields.Email(required=True)
    interest = fields.String(required=False, allow_none=True)
    message = fields.String(required=False, allow_none=True)
    acquisition = fields.Dict(required=False, allow_none=True)


class SponsorInputSchema(ma.Schema):
    organization_slug = fields.String(required=True, data_key="organizationSlug")
    tier = fields.String(required=False, allow_none=True)
    active = fields.Boolean(required=False, load_default=True)
    starts_at = fields.Date(required=False, allow_none=True, data_key="startsAt")
    ends_at = fields.Date(required=False, allow_none=True, data_key="endsAt")


class PartnershipStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(["new", "contacted", "won", "lost"]))


class ProductSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = Product
        load_instance = False


class ProductInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    description = fields.String(required=False, allow_none=True)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    resource_slug = fields.String(required=False, allow_none=True, data_key="resourceSlug")
    type = fields.String(required=False, load_default="digital_download")
    price = fields.Integer(required=True)
    currency = fields.String(required=False, load_default="USD", validate=validate.Length(equal=3))
    is_active = fields.Boolean(required=False, load_default=True, data_key="isActive")


class OrderItemSchema(ma.SQLAlchemyAutoSchema):
    product = fields.Nested(ProductSchema, dump_only=True)

    class Meta:
        model = OrderItem
        load_instance = False


class OrderSchema(ma.SQLAlchemyAutoSchema):
    items = fields.Nested(OrderItemSchema, many=True, dump_only=True)

    class Meta:
        model = Order
        load_instance = False


class OrderItemInputSchema(ma.Schema):
    product_slug = fields.String(required=True, data_key="productSlug")
    quantity = fields.Integer(required=False, load_default=1)


class OrderInputSchema(ma.Schema):
    email = fields.Email(required=True)
    items = fields.List(fields.Nested(OrderItemInputSchema), required=True, validate=validate.Length(min=1))


class OrderStatusInputSchema(ma.Schema):
    status = fields.String(
        required=True, validate=validate.OneOf(["pending_payment", "paid", "failed", "refunded"])
    )
    payment_provider = fields.String(required=False, allow_none=True, data_key="paymentProvider")
    payment_reference = fields.String(required=False, allow_none=True, data_key="paymentReference")
