from marshmallow import fields, validate

from app.extensions import ma
from app.models.article import AI_INVOLVEMENT_VALUES, ARTICLE_STATUSES, Article
from app.schemas.commerce import SponsorSchema
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
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # pre-select the linked Sponsor. Restricted to non-commercial fields
    # even here, since this same schema (minus ai_editorial_notes) is what
    # public readers see — see public_article_schema() below.
    sponsor_id = fields.Integer(dump_only=True)
    sponsor_record = fields.Nested(
        SponsorSchema, dump_only=True, data_key="sponsorRecord",
        only=("id", "campaign_name", "resolved_public_name", "logo", "disclosure_label", "organization"),
    )

    class Meta:
        model = Article
        load_instance = False


# ai_editorial_notes is an internal CMS-only field (an editor's private notes
# on how AI was used) — it must never reach an anonymous/public reader. The
# other AI fields (ai_involvement, human_reviewed, ai_disclosure_required,
# ai_disclosure_text) are fine either way: ai_disclosure_text is the field
# meant to be shown publicly when ai_disclosure_required is true (see
# ArticlePage's disclosure notice), and the rest are exposed as transparent
# provenance metadata, not a secret. Views pick this schema whenever the
# requester is not an editor with permission to edit the article — see
# ArticleDetailResource.get() in api/v1/articles.py.
def public_article_schema(many=False):
    return ArticleSchema(many=many, exclude=("ai_editorial_notes",))


def article_summary_schema(many=False):
    """A lighter shape for list endpoints — no content blocks, no full
    nested relations, just enough for an ArticleCard.
    """
    return ArticleSchema(
        many=many,
        exclude=(
            "content",
            "related_people",
            "related_organizations",
            "related_articles",
            "co_authors",
            "ai_editorial_notes",
        ),
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
    # Optional link to a real Sponsor campaign record — see Sponsor.sponsor_id
    # comment. Kept separate from `sponsor` (the freeform fallback dict)
    # since an Article may have one without the other.
    sponsor_id = fields.Integer(required=False, allow_none=True, data_key="sponsorId")

    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(ARTICLE_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)
    content = fields.List(fields.Dict(), required=False, load_default=list)

    # Generative-AI editorial transparency (see Article.AI_INVOLVEMENT_VALUES).
    # ai_editorial_notes is internal-only; never rendered on the public site.
    ai_involvement = fields.String(
        required=False, load_default="none", data_key="aiInvolvement", validate=validate.OneOf(AI_INVOLVEMENT_VALUES)
    )
    human_reviewed = fields.Boolean(required=False, load_default=False, data_key="humanReviewed")
    ai_disclosure_required = fields.Boolean(required=False, load_default=False, data_key="aiDisclosureRequired")
    ai_disclosure_text = fields.String(required=False, allow_none=True, data_key="aiDisclosureText")
    ai_editorial_notes = fields.String(required=False, allow_none=True, data_key="aiEditorialNotes")
