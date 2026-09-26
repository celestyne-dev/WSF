from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.cms import (
    ADVERTISE_OFFERING_STATUSES,
    ADVERTISE_PAGE_STATUSES,
    ADVERTISE_PRICING_MODES,
    HOMEPAGE_MODULE_TYPES,
    HOMEPAGE_SPONSOR_PLACEMENT_KEYS,
    MENU_ITEM_STYLES,
    MENU_ITEM_TYPES,
    SOCIAL_PLATFORMS,
    AdvertiseMetric,
    AdvertiseOffering,
    AdvertisePage,
    HomepageModule,
    SiteSetting,
    SocialLink,
)
from app.schemas.media import MediaSchema
from app.services.footer import reject_html, validate_group_label
from app.services.homepage import validate_cta_url, validate_item_count
from app.services.navigation import (
    compute_item_warnings,
    validate_depth,
    validate_external_url,
    validate_item_type_requirements,
)


class HomepageModuleSchema(ma.SQLAlchemyAutoSchema):
    """Admin dump — every column, including `id`/timestamps, so the
    builder can key React state and show "last updated". The public
    endpoint dumps with this same schema too (see api/v1/public.py):
    nothing here is sensitive (no author identity, no internal notes),
    unlike Page/Article which need a separate PublicSchema.
    """

    media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = HomepageModule
        load_instance = False


class MenuItemSchema(ma.Schema):
    """Admin dump — every raw editable field, plus `effective_url` (a
    read-only preview of where the item actually points right now — for
    entity types this is derived, not stored) and `warnings` (this item's
    own destination-eligibility issues; see services/navigation.py). The
    public shape is a separate, deliberately smaller function
    (services/navigation.py:serialize_public_menu) rather than a
    marshmallow schema, since it needs to drop invisible/non-public
    children entirely and suppress an emptied-out "group" heading —
    conditional exclusion marshmallow doesn't make clean.
    """

    id = fields.Integer(dump_only=True)
    label = fields.String()
    item_type = fields.String(data_key="itemType")
    url = fields.String(allow_none=True)
    topic_id = fields.Integer(allow_none=True, data_key="topicId")
    series_id = fields.Integer(allow_none=True, data_key="seriesId")
    page_id = fields.Integer(allow_none=True, data_key="pageId")
    open_new_tab = fields.Boolean(data_key="openNewTab")
    style = fields.String()
    sort_order = fields.Integer()
    visible = fields.Boolean()
    effective_url = fields.Method("get_effective_url", data_key="effectiveUrl")
    warnings = fields.Method("get_warnings")
    children = fields.Method("get_children")

    def get_effective_url(self, obj):
        return obj.effective_url()

    def get_warnings(self, obj):
        return compute_item_warnings(obj)

    def get_children(self, obj):
        return MenuItemSchema(many=True).dump(obj.children)


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
    """Every homepage module goes through this schema, whatever its
    `type` — the controlled fields (media/CTA) are shared columns rather
    than per-type schemas, since which fields a type actually *uses* is a
    frontend/rendering concern (see HOMEPAGE_MODULE_TYPES's docstring),
    not something the write path needs to branch on.
    """

    type = fields.String(required=True, validate=validate.OneOf(HOMEPAGE_MODULE_TYPES))
    enabled = fields.Boolean(required=False, load_default=True)
    heading = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))
    subheading = fields.String(required=False, allow_none=True)
    selection_mode = fields.String(required=False, allow_none=True, data_key="selectionMode")
    config = fields.Dict(required=False, load_default=dict)

    media_id = fields.Integer(required=False, allow_none=True, data_key="mediaId")
    cta_label = fields.String(required=False, allow_none=True, data_key="ctaLabel", validate=validate.Length(max=50))
    cta_url = fields.String(required=False, allow_none=True, data_key="ctaUrl", validate=validate.Length(max=500))
    secondary_cta_label = fields.String(
        required=False, allow_none=True, data_key="secondaryCtaLabel", validate=validate.Length(max=50)
    )
    secondary_cta_url = fields.String(
        required=False, allow_none=True, data_key="secondaryCtaUrl", validate=validate.Length(max=500)
    )

    @validates_schema
    def validate_module(self, data, **kwargs):
        validate_cta_url(data.get("cta_url"), field_name="cta_url")
        validate_cta_url(data.get("secondary_cta_url"), field_name="secondary_cta_url")
        validate_item_count(data.get("type"), (data.get("config") or {}).get("itemCount"))
        if data.get("type") == "sponsor_placement":
            key = (data.get("config") or {}).get("placementKey")
            if key and key not in HOMEPAGE_SPONSOR_PLACEMENT_KEYS:
                raise ValidationError("Unknown sponsor placement key.", field_name="config")


class HomepageInputSchema(ma.Schema):
    modules = fields.List(fields.Nested(HomepageModuleInputSchema), required=True)

    @validates_schema
    def validate_singletons(self, data, **kwargs):
        from app.services.homepage import validate_no_duplicate_singletons

        validate_no_duplicate_singletons(data.get("modules") or [])


class MenuItemInputSchema(ma.Schema):
    label = fields.String(required=True, validate=validate.Length(min=1, max=100))
    item_type = fields.String(
        required=False, load_default="route", data_key="itemType", validate=validate.OneOf(MENU_ITEM_TYPES)
    )
    url = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    topic_id = fields.Integer(required=False, allow_none=True, data_key="topicId")
    series_id = fields.Integer(required=False, allow_none=True, data_key="seriesId")
    page_id = fields.Integer(required=False, allow_none=True, data_key="pageId")
    open_new_tab = fields.Boolean(required=False, load_default=False, data_key="openNewTab")
    style = fields.String(required=False, load_default="standard", validate=validate.OneOf(MENU_ITEM_STYLES))
    visible = fields.Boolean(required=False, load_default=True)
    children = fields.List(fields.Nested(lambda: MenuItemInputSchema()), required=False, load_default=list)

    @validates_schema
    def validate_item(self, data, **kwargs):
        validate_item_type_requirements(data)


class MenuInputSchema(ma.Schema):
    key = fields.String(required=True)
    heading = fields.String(required=False, allow_none=True)
    items = fields.List(fields.Nested(MenuItemInputSchema), required=False, load_default=list)

    @validates_schema
    def validate_menu(self, data, **kwargs):
        validate_depth(data.get("items") or [])


class NavigationInputSchema(ma.Schema):
    menus = fields.List(fields.Nested(MenuInputSchema), required=True)
    social_links = fields.List(fields.Dict(), required=False, load_default=list, data_key="socialLinks")


class SiteSettingsInputSchema(ma.Schema):
    settings = fields.Dict(required=True)


# ---------------------------------------------------------------------------
# Footer CMS
# ---------------------------------------------------------------------------
#
# Footer link groups reuse Menu/MenuItem (any key prefixed "footer_" — see
# app/services/footer.py) and MenuItemSchema/MenuItemInputSchema exactly as
# Navigation CMS built them: a footer link is a MenuItem, with the same
# controlled item types, entity-aware URLs, and safety validation. Only
# what's genuinely Footer-specific (group-level visible/sort_order, the
# social-link list, and the small settings blob for branding/newsletter
# CTA/contact/copyright) gets new schemas here.


class FooterGroupSchema(MenuSchema):
    """Admin dump for one footer group — everything MenuSchema already
    dumps (key/heading/items), plus the two fields only footer groups
    use for now (visible/sort_order; see Menu's docstring).
    """

    visible = fields.Boolean()
    sort_order = fields.Integer(data_key="sortOrder")


class FooterGroupInputSchema(ma.Schema):
    # Blank/omitted `key` means "create a new group" — the PUT handler
    # assigns a fresh footer_* key server-side (see footer_menu_key()) so
    # admins never see or type one, matching how a brand-new Topic/Series
    # never asks an editor to invent its own primary key either.
    key = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    heading = fields.String(required=True, validate=validate.Length(min=1, max=40))
    visible = fields.Boolean(required=False, load_default=True)
    items = fields.List(fields.Nested(MenuItemInputSchema), required=False, load_default=list)

    @validates_schema
    def validate_group(self, data, **kwargs):
        validate_group_label(data.get("heading"))
        validate_depth(data.get("items") or [])


class SocialLinkInputSchema(ma.Schema):
    platform = fields.String(required=True, validate=validate.OneOf(SOCIAL_PLATFORMS))
    url = fields.String(required=True, validate=validate.Length(max=300))
    handle = fields.String(required=False, allow_none=True, validate=validate.Length(max=100))
    label = fields.String(required=False, allow_none=True, validate=validate.Length(max=150))
    visible = fields.Boolean(required=False, load_default=True)

    @validates_schema
    def validate_social_link(self, data, **kwargs):
        validate_external_url(data.get("url"))
        reject_html(data.get("handle"), "handle", 100)
        reject_html(data.get("label"), "label", 150)


class FooterSettingsInputSchema(ma.Schema):
    """The small, plain-text-only settings blob stored under the
    `SiteSetting` key "footer" (see upsert_site_settings) — branding copy,
    the newsletter CTA's presentation, public contact info, and the
    copyright line. Never raw JSON exposed to the admin UI; this schema
    is what actually gets validated before it's saved under that key.
    """

    brand_description = fields.String(
        required=False, allow_none=True, load_default="", data_key="brandDescription"
    )
    newsletter_heading = fields.String(
        required=False, allow_none=True, load_default="", data_key="newsletterHeading"
    )
    newsletter_description = fields.String(
        required=False, allow_none=True, load_default="", data_key="newsletterDescription"
    )
    newsletter_visible = fields.Boolean(required=False, load_default=True, data_key="newsletterVisible")
    contact_email = fields.String(required=False, allow_none=True, load_default="", data_key="contactEmail")
    copyright_text = fields.String(
        required=False,
        allow_none=True,
        load_default="Women Shaping Futures. All rights reserved.",
        data_key="copyrightText",
    )

    @validates_schema
    def validate_settings(self, data, **kwargs):
        reject_html(data.get("brand_description"), "brandDescription", 280)
        reject_html(data.get("newsletter_heading"), "newsletterHeading", 150)
        reject_html(data.get("newsletter_description"), "newsletterDescription", 300)
        reject_html(data.get("copyright_text"), "copyrightText", 200)
        email = data.get("contact_email")
        if email:
            validate.Email()(email)


class FooterInputSchema(ma.Schema):
    """The whole Footer CMS save payload — groups, social links, and
    settings all validate and commit together in one request (spec:
    "avoid leaving Footer partially broken during multi-item updates"),
    unlike Navigation's per-menu-key partial save, since Footer's admin
    UI always edits its own dedicated page/save action as one unit.
    """

    groups = fields.List(fields.Nested(FooterGroupInputSchema), required=False, load_default=list)
    social_links = fields.List(fields.Nested(SocialLinkInputSchema), required=False, load_default=list, data_key="socialLinks")
    settings = fields.Nested(FooterSettingsInputSchema, required=False, load_default=dict)

    @validates_schema
    def validate_footer(self, data, **kwargs):
        from app.services.footer import FOOTER_MAX_GROUPS

        if len(data.get("groups") or []) > FOOTER_MAX_GROUPS:
            raise ValidationError(f"Footer supports at most {FOOTER_MAX_GROUPS} groups.", field_name="groups")


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
