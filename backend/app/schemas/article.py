from marshmallow import fields, validate

from app.extensions import db, ma
from app.models.article import AI_INVOLVEMENT_VALUES, ARTICLE_STATUSES, Article
from app.models.media import Media
from app.schemas.commerce import SponsorSchema
from app.schemas.media import MediaSchema
from app.schemas.people import AuthorSchema, OrganizationSchema, PersonSchema
from app.schemas.taxonomy import CategorySchema, SeriesSchema, TagSchema, TopicSchema
from app.schemas.user import UserSchema

_STAFF_ONLY = UserSchema(only=("id", "full_name", "email"))

# Workflow/approval metadata is internal-only — never part of any public
# Article payload (list, detail, or related-article nesting). See
# app/services/articles_workflow.py for the transition rules that produce
# these fields. approved_by_user_id itself isn't listed here — like other
# FK columns backing a declared relationship (see PersonSchema's own note
# on organization_id), marshmallow-sqlalchemy's auto schema never
# generates it as a separate field once approved_by is declared below.
_WORKFLOW_FIELDS = ("scheduled_at", "approved_at", "approved_by")


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
    # Editorial workflow metadata — staff-only (excluded from
    # public_article_schema()/article_summary_schema() below), but useful
    # on the authenticated editor-detail view and the admin list/calendar.
    approved_by = fields.Nested(_STAFF_ONLY, dump_only=True)
    # `seo` is a free-form JSON column (see Article.seo's own comment:
    # {title, description, ogImageMediaId, canonical, robots}) — unlike
    # hero_media_id above, ogImageMediaId has no FK/relationship for
    # marshmallow-sqlalchemy to auto-resolve, so the auto-generated field
    # would just dump the bare stored dict (ogImageMediaId as an integer,
    # never a usable image URL). Declared explicitly to override that
    # auto field and inject the resolved image alongside it.
    seo = fields.Method("get_seo", dump_only=True)

    class Meta:
        model = Article
        load_instance = False

    def get_seo(self, obj):
        seo = dict(obj.seo or {})
        media_id = seo.get("ogImageMediaId")
        if media_id:
            media = db.session.get(Media, media_id)
            if media:
                seo["ogImage"] = media.public_url
                if media.alt_text:
                    seo["ogImageAlt"] = media.alt_text
        return seo


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
    return ArticleSchema(many=many, exclude=("ai_editorial_notes",) + _WORKFLOW_FIELDS)


def article_summary_schema(many=False):
    """A lighter shape for PUBLIC list endpoints — no content blocks, no
    full nested relations, just enough for an ArticleCard, and no
    workflow/approval metadata (see admin_article_summary_schema() below
    for the staff-only equivalent used by the admin list and calendar).
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
        )
        + _WORKFLOW_FIELDS,
    )


def admin_article_summary_schema(many=False):
    """Same lightweight row shape as article_summary_schema(), but for the
    admin article list / editorial calendar — includes scheduled_at/
    approved_at/approved_by so those views can show real workflow state
    without an extra per-row fetch. Never used for a public response.
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


# ---------------------------------------------------------------------------
# Editorial workflow actions — see app/services/articles_workflow.py and
# app/api/v1/articles.py's dedicated action resources. Kept separate from
# ArticleInputSchema since these are narrow, single-purpose payloads, not
# a general article edit.
# ---------------------------------------------------------------------------


class ArticleScheduleInputSchema(ma.Schema):
    scheduled_at = fields.DateTime(required=True, data_key="scheduledAt")


class ArticleRejectInputSchema(ma.Schema):
    """Optional short note for a "request changes" action — recorded only
    in the Audit Log entry for this transition (see app/api/v1/articles.py),
    which is this project's existing history mechanism; no new Article
    column or threaded-comments system is added for it."""

    note = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000))
