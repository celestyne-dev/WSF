from marshmallow import fields, validate

from app.extensions import ma
from app.models.commerce import PartnershipInquiry, Sponsor
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
