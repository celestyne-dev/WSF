from marshmallow import EXCLUDE, fields, validate

from app.extensions import ma
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.taxonomy import TopicSchema
from app.services.newsletter import count_audience


class NewsletterSubscriberSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump — the Subscribers CMS list/detail. Never exposed
    through a public endpoint. unsubscribe_token is excluded even here:
    no legitimate CMS screen needs to display it, since it's effectively a
    bearer credential for that subscriber's public unsubscribe link.
    """

    country = fields.Nested(CountrySchema, dump_only=True)
    interests = fields.Nested(TopicSchema, many=True, dump_only=True, exclude=("article_count",))

    class Meta:
        model = NewsletterSubscriber
        load_instance = False
        exclude = ("unsubscribe_token",)


class NewsletterSubscriberConfirmationSchema(ma.Schema):
    """What the public subscribe/unsubscribe endpoints echo back — just
    enough for the frontend to confirm the action, nothing else about the
    subscriber's record.
    """

    email = fields.Email(dump_only=True)
    status = fields.String(dump_only=True)
    subscribed_at = fields.DateTime(dump_only=True, data_key="subscribedAt")


class NewsletterIssueSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Article.
    featured_article_id = fields.Integer(dump_only=True)
    featured_article = fields.Method("get_featured_article", dump_only=True)
    estimated_recipients = fields.Method("get_estimated_recipients", dump_only=True)

    class Meta:
        model = NewsletterIssue
        load_instance = False

    def get_featured_article(self, obj):
        if obj.featured_article is None:
            return None
        return {
            "id": obj.featured_article.id,
            "slug": obj.featured_article.slug,
            "title": obj.featured_article.title,
        }

    def get_estimated_recipients(self, obj):
        return count_audience(obj.audience_filter)


class NewsletterIssuePublicSchema(ma.SQLAlchemyAutoSchema):
    """The public newsletter archive's dump — only ever built from a
    status == "sent" issue's own fields. Internal-only fields (the
    editor's `title`, `status`, `audience_filter`, scheduling/provider
    metadata) are deliberately excluded.
    """

    cover_media = fields.Nested(MediaSchema, dump_only=True)
    featured_article = fields.Method("get_featured_article", dump_only=True)

    class Meta:
        model = NewsletterIssue
        load_instance = False
        fields = (
            "id",
            "slug",
            "issue_number",
            "subject",
            "preheader",
            "summary",
            "content",
            "cover_media",
            "featured_article",
            "sent_at",
            "created_at",
        )

    def get_featured_article(self, obj):
        if obj.featured_article is None:
            return None
        return {
            "id": obj.featured_article.id,
            "slug": obj.featured_article.slug,
            "title": obj.featured_article.title,
        }


class SubscribeInputSchema(ma.Schema):
    # NewsletterForm.jsx also sends a consentTimestamp field (client-side
    # consent record, not persisted server-side) — EXCLUDE lets the frontend
    # attach that kind of provenance metadata without a 422 for fields this
    # schema doesn't declare.
    class Meta:
        unknown = EXCLUDE

    email = fields.Email(required=True)
    first_name = fields.String(required=False, allow_none=True, data_key="firstName")
    last_name = fields.String(required=False, allow_none=True, data_key="lastName")
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    placement = fields.String(required=False, allow_none=True)
    acquisition = fields.Dict(required=False, allow_none=True)
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")


class UnsubscribeInputSchema(ma.Schema):
    email = fields.Email(required=True)


class NewsletterAdminSubscriberUpdateSchema(ma.Schema):
    """Admin edits to a subscriber — voluntarily-supplied contact info and
    preferences only. Status/consent timestamps change only through the
    dedicated suppress/reactivate actions, never through a casual field
    edit here.
    """

    first_name = fields.String(required=False, allow_none=True, data_key="firstName")
    last_name = fields.String(required=False, allow_none=True, data_key="lastName")
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")


class NewsletterIssueInputSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    subject = fields.String(required=True, validate=validate.Length(min=1, max=300))
    preheader = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    slug = fields.String(required=False, allow_none=True)
    issue_number = fields.Integer(required=False, allow_none=True, data_key="issueNumber")
    content = fields.List(fields.Dict(), required=False, load_default=list)
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    summary = fields.String(required=False, allow_none=True)
    featured_article_slug = fields.String(required=False, allow_none=True, data_key="featuredArticleSlug")
    # "sent" is deliberately not settable through this general save — an
    # issue is only ever marked sent through the dedicated mark-sent
    # action, so a plain save can never accidentally claim delivery.
    status = fields.String(
        required=False, load_default="draft", validate=validate.OneOf(("draft", "scheduled", "archived"))
    )
    audience_filter = fields.Dict(required=False, allow_none=True, data_key="audienceFilter")
    scheduled_at = fields.DateTime(required=False, allow_none=True, data_key="scheduledAt")
    send_timezone = fields.String(required=False, load_default="UTC", data_key="sendTimezone")


class AudienceEstimateInputSchema(ma.Schema):
    audience_filter = fields.Dict(required=False, allow_none=True, data_key="audienceFilter")
