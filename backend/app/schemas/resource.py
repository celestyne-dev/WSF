from marshmallow import fields, validate

from app.extensions import ma
from app.models.resource import Resource
from app.schemas.media import MediaSchema
from app.schemas.people import AuthorSchema
from app.schemas.taxonomy import TopicSchema


class ResourceSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    topic = fields.Nested(TopicSchema, dump_only=True, exclude=("article_count",))
    author = fields.Nested(AuthorSchema, dump_only=True, exclude=("article_count",))

    class Meta:
        model = Resource
        load_instance = False


class ResourceInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    description = fields.String(required=False, allow_none=True)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    type = fields.String(required=False, allow_none=True)
    topic_slug = fields.String(required=False, allow_none=True, data_key="topicSlug")
    author_slug = fields.String(required=False, allow_none=True, data_key="authorSlug")
    price = fields.Integer(required=False, load_default=0)
    currency = fields.String(required=False, load_default="USD", validate=validate.Length(equal=3))
    is_premium = fields.Boolean(required=False, load_default=False, data_key="isPremium")
    is_downloadable = fields.Boolean(required=False, load_default=True, data_key="isDownloadable")
    is_external = fields.Boolean(required=False, load_default=False, data_key="isExternal")
    file_url = fields.String(required=False, allow_none=True, data_key="fileUrl")
    external_url = fields.String(required=False, allow_none=True, data_key="externalUrl")
    featured = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="published", validate=validate.OneOf(["draft", "published"]))
