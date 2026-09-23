from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.cms import (
    ADVERTISE_OFFERING_STATUSES,
    ADVERTISE_PAGE_STATUSES,
    ADVERTISE_PRICING_MODES,
    AdvertiseMetric,
    AdvertiseOffering,
    AdvertisePage,
    HomepageModule,
    SiteSetting,
    SocialLink,
)
from app.schemas.media import MediaSchema


class HomepageModuleSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = HomepageModule
        load_instance = False


class MenuItemSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    label = fields.String()
    url = fields.String()
    sort_order = fields.Integer()
    visible = fields.Boolean()
    children = fields.List(fields.Nested(lambda: MenuItemSchema()), dump_only=True)


class MenuSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    key = fields.String()
    heading = fields.String(allow_none=True)
    items = fields.Method("get_items")

    def get_items(self, obj):
        return MenuItemSchema(many=True).dump(obj.top_level_items())


class SiteSettingSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = SiteSetting
        load_instance = False


class SocialLinkSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = SocialLink
        load_instance = False


class HomepageModuleInputSchema(ma.Schema):
    type = fields.String(required=True)
    enabled = fields.Boolean(required=False, load_default=True)
    heading = fields.String(required=False, allow_none=True)
    subheading = fields.String(required=False, allow_none=True)
    selection_mode = fields.String(required=False, allow_none=True, data_key="selectionMode")
    config = fields.Dict(required=False, load_default=dict)


class HomepageInputSchema(ma.Schema):
    modules = fields.List(fields.Nested(HomepageModuleInputSchema), required=True)


class MenuItemInputSchema(ma.Schema):
    label = fields.String(required=True, validate=validate.Length(min=1, max=100))
    url = fields.String(required=True, validate=validate.Length(min=1, max=300))
    visible = fields.Boolean(required=False, load_default=True)
    children = fields.List(fields.Nested(lambda: MenuItemInputSchema()), required=False, load_default=list)


class MenuInputSchema(ma.Schema):
    key = fields.String(required=True)
    heading = fields.String(required=False, allow_none=True)
    items = fields.List(fields.Nested(MenuItemInputSchema), required=False, load_default=list)


class NavigationInputSchema(ma.Schema):
    menus = fields.List(fields.Nested(MenuInputSchema), required=True)
    social_links = fields.List(fields.Dict(), required=False, load_default=list, data_key="socialLinks")


class SiteSettingsInputSchema(ma.Schema):
    settings = fields.Dict(required=True)


# ---------------------------------------------------------------------------
# Advertise / Media Kit
# ---------------------------------------------------------------------------


class AdvertisePageSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump — includes `status`, timestamps, and everything
    else. See build_public_advertise_page() in api/v1/advertise.py for
    what the public route actually returns.
    """

    hero_media_id = fields.Integer(dump_only=True)
    hero_media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = AdvertisePage
        load_instance = False


class AdvertisePageInputSchema(ma.Schema):
    """Shared field set for the general PATCH — `status` is deliberately
    excluded (dedicated /status action only, so publishing is always a
    conscious step, never a side effect of an unrelated content edit).
    """

    hero_heading = fields.String(required=False, allow_none=True, data_key="heroHeading", validate=validate.Length(max=200))
    hero_description = fields.String(required=False, allow_none=True, data_key="heroDescription")
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    intro_content = fields.List(fields.Dict(), required=False, data_key="introContent")
    audience_overview = fields.String(required=False, allow_none=True, data_key="audienceOverview")
    why_content = fields.List(fields.Dict(), required=False, data_key="whyContent")
    cta_heading = fields.String(required=False, allow_none=True, data_key="ctaHeading", validate=validate.Length(max=200))
    cta_description = fields.String(required=False, allow_none=True, data_key="ctaDescription")
    cta_button_label = fields.String(required=False, allow_none=True, data_key="ctaButtonLabel", validate=validate.Length(max=50))
    contact_email = fields.Email(required=False, allow_none=True, data_key="contactEmail")
    contact_note = fields.String(required=False, allow_none=True, data_key="contactNote")
    media_kit_title = fields.String(required=False, allow_none=True, data_key="mediaKitTitle", validate=validate.Length(max=200))
    media_kit_url = fields.String(required=False, allow_none=True, data_key="mediaKitUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    media_kit_updated_at = fields.Date(required=False, allow_none=True, data_key="mediaKitUpdatedAt")
    faq = fields.List(fields.Dict(), required=False)
    seo = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_faq(self, data, **kwargs):
        for entry in data.get("faq") or []:
            if not isinstance(entry, dict) or not entry.get("question") or not entry.get("answer"):
                raise ValidationError("Each FAQ entry needs a question and an answer.", field_name="faq")


class AdvertisePageStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(ADVERTISE_PAGE_STATUSES))


class AdvertiseMetricSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AdvertiseMetric
        load_instance = False


class AdvertiseMetricInputSchema(ma.Schema):
    label = fields.String(required=True, validate=validate.Length(min=1, max=100))
    value = fields.String(required=True, validate=validate.Length(min=1, max=100))
    unit = fields.String(required=False, allow_none=True, validate=validate.Length(max=30))
    source_note = fields.String(required=False, allow_none=True, data_key="sourceNote")
    as_of_date = fields.Date(required=False, allow_none=True, data_key="asOfDate")
    display_order = fields.Integer(required=False, load_default=0, data_key="displayOrder")
    public_visible = fields.Boolean(required=False, load_default=True, data_key="publicVisible")


class AdvertiseMetricUpdateSchema(ma.Schema):
    """No load_default anywhere — a key absent from the request leaves
    that field untouched, so a reorder/visibility-toggle save can never
    silently reset the label/value/etc.
    """

    label = fields.String(required=False, validate=validate.Length(min=1, max=100))
    value = fields.String(required=False, validate=validate.Length(min=1, max=100))
    unit = fields.String(required=False, allow_none=True, validate=validate.Length(max=30))
    source_note = fields.String(required=False, allow_none=True, data_key="sourceNote")
    as_of_date = fields.Date(required=False, allow_none=True, data_key="asOfDate")
    display_order = fields.Integer(required=False, data_key="displayOrder")
    public_visible = fields.Boolean(required=False, data_key="publicVisible")


class AdvertiseOfferingSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AdvertiseOffering
        load_instance = False


def _validate_pricing(data, error_cls=ValidationError):
    mode = data.get("pricing_mode")
    if mode in ("starting_from", "fixed") and not data.get("price_amount"):
        raise error_cls("A price is required for this pricing mode.", field_name="price_amount")


class AdvertiseOfferingInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=150))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    full_description = fields.String(required=False, allow_none=True, data_key="fullDescription")
    features = fields.List(fields.String(), required=False, load_default=list)
    cta_label = fields.String(required=False, allow_none=True, data_key="ctaLabel", validate=validate.Length(max=50))
    display_order = fields.Integer(required=False, load_default=0, data_key="displayOrder")
    featured = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="active", validate=validate.OneOf(ADVERTISE_OFFERING_STATUSES))
    pricing_mode = fields.String(required=False, load_default="contact", data_key="pricingMode", validate=validate.OneOf(ADVERTISE_PRICING_MODES))
    price_amount = fields.Integer(required=False, allow_none=True, data_key="priceAmount", validate=validate.Range(min=0))
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    pricing_note = fields.String(required=False, allow_none=True, data_key="pricingNote")

    @validates_schema
    def validate_pricing(self, data, **kwargs):
        _validate_pricing(data)


class AdvertiseOfferingUpdateSchema(ma.Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=150))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    full_description = fields.String(required=False, allow_none=True, data_key="fullDescription")
    features = fields.List(fields.String(), required=False)
    cta_label = fields.String(required=False, allow_none=True, data_key="ctaLabel", validate=validate.Length(max=50))
    display_order = fields.Integer(required=False, data_key="displayOrder")
    featured = fields.Boolean(required=False)
    status = fields.String(required=False, validate=validate.OneOf(ADVERTISE_OFFERING_STATUSES))
    pricing_mode = fields.String(required=False, data_key="pricingMode", validate=validate.OneOf(ADVERTISE_PRICING_MODES))
    price_amount = fields.Integer(required=False, allow_none=True, data_key="priceAmount", validate=validate.Range(min=0))
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    pricing_note = fields.String(required=False, allow_none=True, data_key="pricingNote")
