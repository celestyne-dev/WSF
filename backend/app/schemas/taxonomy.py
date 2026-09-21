from marshmallow import fields, validate

from app.extensions import ma
from app.models.article import Article
from app.models.taxonomy import Category, Series, Tag, Topic
from app.schemas.media import MediaSchema


class CategorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Category
        load_instance = False


class TagSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Tag
        load_instance = False


class TopicSchema(ma.SQLAlchemyAutoSchema):
    article_count = fields.Method("get_article_count")

    class Meta:
        model = Topic
        load_instance = False

    def get_article_count(self, obj):
        return Article.query.filter(Article.topics.any(id=obj.id), Article.status == "published").count()


class SeriesSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    article_count = fields.Method("get_article_count")

    class Meta:
        model = Series
        load_instance = False

    def get_article_count(self, obj):
        return Article.query.filter_by(series_id=obj.id, status="published").count()


class CategoryInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)


class TopicInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)
    sort_order = fields.Integer(required=False, load_default=0, data_key="sortOrder")


class SeriesInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    sponsor_organization_id = fields.Integer(required=False, allow_none=True, data_key="sponsorOrganizationId")
    featured = fields.Boolean(required=False, load_default=False)
