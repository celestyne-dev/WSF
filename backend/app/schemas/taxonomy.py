from marshmallow import ValidationError, fields, validate

from app.extensions import ma
from app.models.article import Article
from app.models.taxonomy import TAXONOMY_STATUSES, Category, Series, Tag, Topic
from app.schemas.media import MediaSchema
from app.schemas.sources import sources_field

# AI Search / GEO Phase 4C — long-form `content`/`sources` are DETAIL-only:
# TopicSchema/SeriesSchema (lists, hubs, homepage modules, selectors, every
# nested taxonomy preview) never carry them. The public detail schemas
# below add them back with the published-only featured Article and the
# bounded contributor/people lists; the admin schemas add the raw editor
# fields.
_DETAIL_ONLY = ("content", "sources")
MAX_TOPIC_CONTRIBUTORS = 6
MAX_SERIES_PEOPLE = 8


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
    hero_media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = Topic
        load_instance = False
        exclude = _DETAIL_ONLY

    def get_article_count(self, obj):
        return Article.query.filter(Article.topics.any(id=obj.id), Article.status == "published").count()


class SeriesSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    article_count = fields.Method("get_article_count")

    class Meta:
        model = Series
        load_instance = False
        exclude = _DETAIL_ONLY

    def get_article_count(self, obj):
        return Article.query.filter_by(series_id=obj.id, status="published").count()


def _public_featured_article(obj):
    """The curated "Start here" Article as the standard public summary —
    ONLY while it is published. A draft/archived pick stays stored for the
    CMS but publicly behaves as no featured Article (nothing about it —
    title, slug, excerpt, image, author, id — is serialized)."""
    article = obj.featured_article
    if article is None or article.status != "published":
        return None
    from app.schemas.article import article_summary_schema

    return article_summary_schema().dump(article)


def _admin_featured_article(obj):
    """CMS-only preview of whatever is selected (any status)."""
    article = obj.featured_article
    if article is None:
        return None
    return {"id": article.id, "slug": article.slug, "title": article.title, "status": article.status}


def _list(value):
    return list(value or [])


class TopicDetailSchema(TopicSchema):
    """Public Topic detail (GET /topics/<slug> `topic`, Topic prerender)."""

    content = fields.Function(lambda obj: _list(obj.content), dump_only=True)
    sources = fields.Function(lambda obj: _list(obj.sources), dump_only=True)
    featured_article = fields.Function(_public_featured_article, dump_only=True)
    contributors = fields.Method("get_contributors", dump_only=True)

    class Meta(TopicSchema.Meta):
        exclude = ()

    def get_contributors(self, obj):
        """Active Authors explicitly classified under this Topic (the
        existing author_topics relationship — never inferred from text,
        mentions, sources or credentials). Lightweight public fields only:
        no sources, credentials, user_id or account data."""
        from sqlalchemy.orm import selectinload

        from app.models.people import Author
        from app.schemas.people import AuthorSchema

        authors = (
            Author.query.options(selectinload(Author.photo))
            .filter(Author.status == "active", Author.topics.any(id=obj.id))
            .order_by(Author.name)
            .limit(MAX_TOPIC_CONTRIBUTORS)
            .all()
        )
        return AuthorSchema(many=True, only=("slug", "name", "role", "short_bio", "photo")).dump(authors)


class SeriesDetailSchema(SeriesSchema):
    """Public Series detail (GET /series/<slug> `series`, Series prerender)."""

    content = fields.Function(lambda obj: _list(obj.content), dump_only=True)
    sources = fields.Function(lambda obj: _list(obj.sources), dump_only=True)
    featured_article = fields.Function(_public_featured_article, dump_only=True)
    people = fields.Method("get_people", dump_only=True)
    sponsor_organization = fields.Method("get_sponsor_organization", dump_only=True)

    class Meta(SeriesSchema.Meta):
        exclude = ()

    def get_people(self, obj):
        """Published People explicitly in this Series (the existing
        person_series relationship). Lightweight public fields only."""
        from sqlalchemy.orm import selectinload

        from app.models.people import Person
        from app.schemas.people import PersonSchema

        people = (
            Person.query.options(selectinload(Person.photo))
            .filter(Person.status == "published", Person.series.any(id=obj.id))
            .order_by(Person.featured.desc(), Person.name)
            .limit(MAX_SERIES_PEOPLE)
            .all()
        )
        return PersonSchema(many=True, only=("slug", "name", "title", "short_bio", "photo")).dump(people)

    def get_sponsor_organization(self, obj):
        """Disclosure only: the sponsoring Organization's name/slug/logo,
        and only while that Organization is itself published (the same
        public_organization_preview rule as everywhere else) — never any
        sponsor campaign/tier/internal record."""
        from app.services.public_visibility import public_organization_preview

        def _dump(org):
            return {"slug": org.slug, "name": org.name, "logo": MediaSchema().dump(org.logo) if org.logo else None}

        if obj.sponsor_organization is None:
            return None
        return public_organization_preview(obj.sponsor_organization, _dump)


class TopicAdminSchema(TopicSchema):
    """CMS Topic (admin detail/create/update): the raw editorial fields,
    including a draft/archived featured Article selection."""

    content = fields.Function(lambda obj: _list(obj.content), dump_only=True)
    sources = fields.Function(lambda obj: _list(obj.sources), dump_only=True)
    featured_article_id = fields.Integer(dump_only=True)
    featured_article = fields.Function(_admin_featured_article, dump_only=True)

    class Meta(TopicSchema.Meta):
        exclude = ()


class SeriesAdminSchema(SeriesSchema):
    content = fields.Function(lambda obj: _list(obj.content), dump_only=True)
    sources = fields.Function(lambda obj: _list(obj.sources), dump_only=True)
    featured_article_id = fields.Integer(dump_only=True)
    featured_article = fields.Function(_admin_featured_article, dump_only=True)
    # So the editor can pre-select the stored sponsor (any status) instead
    # of sending null — and silently clearing it — on every save.
    sponsor_organization_id = fields.Integer(dump_only=True)

    class Meta(SeriesSchema.Meta):
        exclude = ()


# Exactly the blocks the Topic/Series editors can create (ArticleBlockEditor's
# DEFAULT_BLOCK_TYPES). Checked here, before the shared
# sanitize_content_blocks() runs in admin_taxonomy._apply_editorial — that
# sanitizer deliberately passes unknown types through for its other callers
# (Articles, Newsletter, ...), so Topic/Series content opts into this
# stricter allowlist instead of changing it globally.
TOPIC_SERIES_CONTENT_BLOCK_TYPES = frozenset(
    {"paragraph", "heading", "list", "blockquote", "pullquote", "image", "highlight", "divider"}
)


def validate_topic_series_content(blocks):
    """Reject (never silently drop) any block that isn't a dict with one of
    the allowed string types — raw_html, button, articleCard, footerNote,
    newsletterCta, sponsorBlock, ad, table, faq or anything unknown."""
    for index, block in enumerate(blocks):
        if not isinstance(block, dict) or not isinstance(block.get("type"), str):
            raise ValidationError(f"Content block {index + 1} needs a block type.")
        if block["type"] not in TOPIC_SERIES_CONTENT_BLOCK_TYPES:
            raise ValidationError(f"Unsupported content block type: {block['type']}.")


def _editorial_input_fields():
    """Shared Topic/Series editorial input fields. None of them has a
    load_default: omitted on update -> stored value untouched; content []
    / sources [] / featuredArticleId null -> cleared."""
    return {
        "content": fields.List(fields.Raw(), required=False, validate=validate_topic_series_content),
        "sources": sources_field("A topic or series"),
        "featured_article_id": fields.Integer(required=False, allow_none=True, data_key="featuredArticleId"),
    }


class CategoryInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(TAXONOMY_STATUSES))
    sort_order = fields.Integer(required=False, load_default=0, data_key="sortOrder")


class CategoryUpdateSchema(ma.Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)
    status = fields.String(required=False, validate=validate.OneOf(TAXONOMY_STATUSES))
    sort_order = fields.Integer(required=False, data_key="sortOrder")


class TopicInputSchema(ma.Schema.from_dict(_editorial_input_fields())):
    name = fields.String(required=True, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    seo = fields.Dict(required=False, allow_none=True)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(TAXONOMY_STATUSES))
    sort_order = fields.Integer(required=False, load_default=0, data_key="sortOrder")


class TopicUpdateSchema(ma.Schema.from_dict(_editorial_input_fields())):
    name = fields.String(required=False, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    description = fields.String(required=False, allow_none=True)
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    seo = fields.Dict(required=False, allow_none=True)
    status = fields.String(required=False, validate=validate.OneOf(TAXONOMY_STATUSES))
    sort_order = fields.Integer(required=False, data_key="sortOrder")


class SeriesInputSchema(ma.Schema.from_dict(_editorial_input_fields())):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    subtitle = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    description = fields.String(required=False, allow_none=True)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    sponsor_organization_id = fields.Integer(required=False, allow_none=True, data_key="sponsorOrganizationId")
    seo = fields.Dict(required=False, allow_none=True)
    featured = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(TAXONOMY_STATUSES))
    sort_order = fields.Integer(required=False, load_default=0, data_key="sortOrder")


class SeriesUpdateSchema(ma.Schema.from_dict(_editorial_input_fields())):
    name = fields.String(required=False, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    subtitle = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    description = fields.String(required=False, allow_none=True)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    sponsor_organization_id = fields.Integer(required=False, allow_none=True, data_key="sponsorOrganizationId")
    seo = fields.Dict(required=False, allow_none=True)
    featured = fields.Boolean(required=False)
    status = fields.String(required=False, validate=validate.OneOf(TAXONOMY_STATUSES))
    sort_order = fields.Integer(required=False, data_key="sortOrder")


class TagInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    status = fields.String(required=False, load_default="published", validate=validate.OneOf(TAXONOMY_STATUSES))


class TagUpdateSchema(ma.Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    status = fields.String(required=False, validate=validate.OneOf(TAXONOMY_STATUSES))


class TaxonomyStatusUpdateSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(TAXONOMY_STATUSES))


class TagMergeSchema(ma.Schema):
    from_tag_id = fields.Integer(required=True, data_key="fromTagId")
    to_tag_id = fields.Integer(required=True, data_key="toTagId")
