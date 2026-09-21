from marshmallow import fields, validate

from app.extensions import ma
from app.models.article import ARTICLE_STATUSES, Article
from app.schemas.media import MediaSchema
from app.schemas.people import AuthorSchema, OrganizationSchema, PersonSchema
from app.schemas.taxonomy import CategorySchema, SeriesSchema, TagSchema, TopicSchema


class ArticleRelatedSchema(ma.Schema):
    """A minimal shape for articles nested inside another article's payload
    (related reading, "up next") — avoids re-dumping full content blocks.
    """

    id = fields.Integer()
    slug = fields.String()
    title = fields.String()
    excerpt = fields.String()
    hero_media = fields.Nested(MediaSchema, dump_only=True)
    publish_date = fields.DateTime()
    reading_time = fields.Integer()


class ArticleSchema(ma.SQLAlchemyAutoSchema):
    hero_media = fields.Nested(MediaSchema, dump_only=True)
    author = fields.Nested(AuthorSchema, dump_only=True)
    co_authors = fields.Nested(AuthorSchema, many=True, dump_only=True)
    category = fields.Nested(CategorySchema, dump_only=True)
    series = fields.Nested(SeriesSchema, dump_only=True, exclude=("article_count",))
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, exclude=("article_count",))
    tags = fields.Nested(TagSchema, many=True, dump_only=True)
    related_people = fields.Nested(PersonSchema, many=True, dump_only=True)
    related_organizations = fields.Nested(OrganizationSchema, many=True, dump_only=True)
    related_articles = fields.Nested(ArticleRelatedSchema, many=True, dump_only=True)

    class Meta:
        model = Article
        load_instance = False


def article_summary_schema(many=False):
    """A lighter shape for list endpoints — no content blocks, no full
    nested relations, just enough for an ArticleCard.
    """
    return ArticleSchema(
        many=many,
        exclude=("content", "related_people", "related_organizations", "related_articles", "co_authors"),
    )


class ArticleInputSchema(ma.Schema):
    """Validates the create/update payload. Relations are addressed by
    slug (matching the shape the frontend mock layer already uses in
    frontend/src/mock/articles.js) and resolved to FK ids in the view —
    keeping "does this slug exist" validation out of the schema layer.
    """

    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    title = fields.String(required=True, validate=validate.Length(min=1, max=300))
    subtitle = fields.String(required=False, allow_none=True)
    excerpt = fields.String(required=False, allow_none=True)

    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    hero_image_caption = fields.String(required=False, allow_none=True, data_key="heroImageCaption")
    hero_image_credit = fields.String(required=False, allow_none=True, data_key="heroImageCredit")

    author_slug = fields.String(required=True, data_key="authorSlug")
    co_author_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="coAuthorSlugs")

    publish_date = fields.DateTime(required=False, allow_none=True, data_key="publishDate")
    reading_time = fields.Integer(required=False, allow_none=True, data_key="readingTime")

    category_slug = fields.String(required=False, allow_none=True, data_key="categorySlug")
    series_slug = fields.String(required=False, allow_none=True, data_key="seriesSlug")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    tag_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="tagSlugs")

    related_person_slugs = fields.List(
        fields.String(), required=False, load_default=list, data_key="relatedPersonSlugs"
    )
    related_organization_slugs = fields.List(
        fields.String(), required=False, load_default=list, data_key="relatedOrganizationSlugs"
    )
    related_article_slugs = fields.List(
        fields.String(), required=False, load_default=list, data_key="relatedArticleSlugs"
    )

    featured = fields.Boolean(required=False, load_default=False)
    promoted = fields.Boolean(required=False, load_default=False)
    is_sponsored = fields.Boolean(required=False, load_default=False, data_key="isSponsored")
    sponsor = fields.Dict(required=False, allow_none=True)

    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(ARTICLE_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)
    content = fields.List(fields.Dict(), required=False, load_default=list)
