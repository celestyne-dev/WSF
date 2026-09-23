from marshmallow import fields, validate

from app.extensions import ma
from app.models.resource import (
    ACCESS_TYPES,
    FILE_FORMATS,
    Resource,
    ResourceImage,
    ResourceLead,
    RESOURCE_STATUSES,
    RESOURCE_TYPES,
)
from app.schemas.media import MediaSchema
from app.schemas.people import AuthorSchema, OrganizationSchema
from app.schemas.taxonomy import TagSchema, TopicSchema


class ResourceImageSchema(ma.SQLAlchemyAutoSchema):
    media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = ResourceImage
        load_instance = False
        exclude = ("resource_id",)


class ResourceSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    images = fields.Nested(ResourceImageSchema, many=True, dump_only=True)
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, exclude=("article_count",))
    tags = fields.Nested(TagSchema, many=True, dump_only=True)
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Author/Sponsor.
    author_id = fields.Integer(dump_only=True)
    author = fields.Nested(AuthorSchema, dump_only=True, exclude=("article_count",))
    sponsor_id = fields.Integer(dump_only=True)
    sponsor = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))
    is_free = fields.Method("get_is_free")
    requires_email = fields.Method("get_requires_email")
    requires_account = fields.Method("get_requires_account")
    # The existing Product.resource_id hook — surfaced read-only so an
    # editor can see (not create) a Shop listing that already wraps this
    # Resource, without duplicating any product/payment logic here.
    linked_product = fields.Method("get_linked_product")

    class Meta:
        model = Resource
        load_instance = False

    def get_is_free(self, obj):
        return obj.access_type != "premium" and not obj.is_premium

    def get_requires_email(self, obj):
        return obj.access_type == "email_gate"

    def get_requires_account(self, obj):
        return obj.access_type == "member_only"

    def get_linked_product(self, obj):
        from app.models.commerce import Product

        product = Product.query.filter_by(resource_id=obj.id).first()
        if product is None:
            return None
        return {"id": product.id, "slug": product.slug, "name": product.name, "status": product.status}


class ResourceInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    subtitle = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    # Ordered content-block list — same shape/sanitizer as Job/Product
    # description. The editor structures "What's included"/"Who it's
    # for"/"Key benefits" themselves rather than the app hard-coding them.
    description = fields.List(fields.Dict(), required=False, load_default=list)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    gallery_media_ids = fields.List(fields.Integer(), required=False, load_default=list, data_key="galleryMediaIds")
    type = fields.String(required=False, allow_none=True, validate=validate.OneOf(RESOURCE_TYPES))
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    tag_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="tagSlugs")
    author_slug = fields.String(required=False, allow_none=True, data_key="authorSlug")
    author_name = fields.String(required=False, allow_none=True, data_key="authorName")

    price = fields.Integer(required=False, load_default=0, validate=validate.Range(min=0))
    currency = fields.String(required=False, load_default="USD", validate=validate.Length(equal=3))

    access_type = fields.String(required=False, load_default="direct_download", data_key="accessType", validate=validate.OneOf(ACCESS_TYPES))
    file_url = fields.String(required=False, allow_none=True, data_key="fileUrl")
    external_url = fields.String(required=False, allow_none=True, data_key="externalUrl")
    file_format = fields.String(required=False, allow_none=True, data_key="fileFormat", validate=validate.OneOf(FILE_FORMATS))
    file_size = fields.Integer(required=False, allow_none=True, data_key="fileSize", validate=validate.Range(min=0))
    page_count = fields.Integer(required=False, allow_none=True, data_key="pageCount", validate=validate.Range(min=0))

    sponsor_slug = fields.String(required=False, allow_none=True, data_key="sponsorSlug")
    sponsored = fields.Boolean(required=False, load_default=False)

    featured = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(RESOURCE_STATUSES))
    published_date = fields.Date(required=False, allow_none=True, data_key="publishedDate")
    seo = fields.Dict(required=False, allow_none=True)

    # File/external-URL requirements are enforced only at publish time (see
    # _validate_publish in app/api/v1/resources.py) — a draft is allowed to
    # be saved incomplete, same as every other content type's draft state.


class ResourceLeadSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = ResourceLead
        load_instance = False
        exclude = ("resource_id",)


class ResourceLeadInputSchema(ma.Schema):
    email = fields.Email(required=True)
    first_name = fields.String(required=False, allow_none=True, data_key="firstName")
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    newsletter_consent = fields.Boolean(required=False, load_default=False, data_key="newsletterConsent")
    acquisition = fields.Dict(required=False, allow_none=True)
