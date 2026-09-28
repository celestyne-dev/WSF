from marshmallow import fields, validate

from app.extensions import ma
from app.models.learning import (
    ACCESS_TYPES,
    AUDIENCE_TYPES,
    DELIVERY_MODES,
    DIFFICULTY_LEVELS,
    DURATION_UNITS,
    LEARNING_PROGRAM_TYPES,
    LEARNING_STATUSES,
    LESSON_TYPES,
    LearningLesson,
    LearningModule,
    LearningProgram,
)
from app.schemas.commerce import ProductSchema
from app.schemas.media import MediaSchema
from app.schemas.people import AuthorSchema, OrganizationSchema

# A lesson's Article/Resource reference is only ever shown to a public
# reader when that Article/Resource is itself currently eligible for
# public view — a lesson pointing at a draft/unpublished Article must
# never leak its existence (title, slug) to an anonymous reader (spec
# section 68/46: "do not index unpublished lessons ... private data").
_LESSON_ARTICLE_ONLY = ("id", "slug", "title")
_LESSON_RESOURCE_ONLY = ("id", "slug", "name")


class LearningLessonSchema(ma.SQLAlchemyAutoSchema):
    article = fields.Method("get_article")
    resource = fields.Method("get_resource")

    class Meta:
        model = LearningLesson
        load_instance = False
        exclude = ("module_id",)

    def get_article(self, obj):
        if obj.article is None or obj.article.status != "published":
            return None
        return {k: getattr(obj.article, k) for k in _LESSON_ARTICLE_ONLY}

    def get_resource(self, obj):
        if obj.resource is None or obj.resource.status != "published":
            return None
        return {k: getattr(obj.resource, k) for k in _LESSON_RESOURCE_ONLY}


class LearningModuleSchema(ma.SQLAlchemyAutoSchema):
    lessons = fields.Nested(LearningLessonSchema, many=True, dump_only=True)

    class Meta:
        model = LearningModule
        load_instance = False
        exclude = ("learning_program_id",)


_INSTRUCTOR_ONLY = ("id", "slug", "name", "role", "photo")


class LearningProgramSchema(ma.SQLAlchemyAutoSchema):
    """Full program shape — used for the admin detail view and (via
    public_learning_program_schema below, which excludes nothing extra
    since this model carries no internal-only fields) the public detail
    page. Modules/lessons are never independently filtered by status —
    visibility is entirely the parent Program's (see LearningModule's own
    docstring) — so once a Program is eligible for public view, its whole
    curriculum comes along with it, only with any draft-Article/Resource
    lesson references nulled out by LearningLessonSchema above.
    """

    hero_media = fields.Nested(MediaSchema, dump_only=True)
    primary_instructor_id = fields.Integer(dump_only=True)
    primary_instructor = fields.Nested(AuthorSchema, dump_only=True, only=_INSTRUCTOR_ONLY)
    co_instructors = fields.Nested(AuthorSchema, many=True, dump_only=True, only=_INSTRUCTOR_ONLY)
    provider_organization_id = fields.Integer(dump_only=True)
    provider_organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))
    product_id = fields.Integer(dump_only=True)
    # Product stays the sole source of truth for price/currency — only a
    # minimal shape is surfaced here (spec: "do not duplicate pricing").
    product = fields.Nested(ProductSchema, dump_only=True, only=("id", "slug", "name", "price", "sale_price", "currency", "status", "is_available"))
    topics = fields.Method("get_topics")
    modules = fields.Nested(LearningModuleSchema, many=True, dump_only=True)
    related_articles = fields.Method("get_related_articles")
    related_resources = fields.Method("get_related_resources")
    events = fields.Method("get_events")

    class Meta:
        model = LearningProgram
        load_instance = False

    def get_topics(self, obj):
        return [{"slug": t.slug, "name": t.name} for t in obj.topics]

    def get_related_articles(self, obj):
        # Ordered, and only ever an Article an editor explicitly linked —
        # never auto-related — filtered to published (spec: no draft leak).
        return [
            {"id": link.article.id, "slug": link.article.slug, "title": link.article.title}
            for link in obj.related_article_links
            if link.article is not None and link.article.status == "published"
        ]

    def get_related_resources(self, obj):
        return [
            {"id": r.id, "slug": r.slug, "name": r.name}
            for r in obj.related_resources
            if r.status == "published"
        ]

    def get_events(self, obj):
        from app.schemas.opportunity import EventSchema

        # Only Events that are themselves publicly eligible are ever
        # surfaced (spec section 41/88) — mirrors api/v1/events.py's own
        # public-visibility rule exactly.
        eligible = EventSchema(only=("id", "slug", "title", "date", "end_date", "location", "format", "status", "registration_url", "ticket_price", "currency"))
        return [
            eligible.dump(link.event)
            for link in obj.event_links
            if link.event is not None and link.event.status in ("published", "cancelled", "postponed")
        ]


def public_learning_program_schema(many=False):
    """Public detail — see LearningProgramSchema's own docstring for why
    nothing further needs excluding here.
    """
    return LearningProgramSchema(many=many)


def learning_program_summary_schema(many=False):
    """Lightweight shape for the public Learning index — a card, never
    full curriculum (spec section 76).
    """
    return LearningProgramSchema(
        many=many,
        exclude=("overview", "learning_outcomes", "prerequisites", "modules", "related_articles", "related_resources", "seo"),
    )


def admin_learning_program_summary_schema(many=False):
    """Row shape for the admin Learning list (spec section 50) — no full
    curriculum/overview, but includes status (never shown publicly).
    """
    return LearningProgramSchema(
        many=many,
        exclude=("overview", "learning_outcomes", "prerequisites", "modules", "related_articles", "related_resources", "events"),
    )


# ---------------------------------------------------------------------------
# Input schemas
# ---------------------------------------------------------------------------


class LearningProgramInputSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    subtitle = fields.String(required=False, allow_none=True, validate=validate.Length(max=300))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")

    program_type = fields.String(required=False, load_default="course", data_key="programType", validate=validate.OneOf(LEARNING_PROGRAM_TYPES))
    difficulty_level = fields.String(required=False, allow_none=True, data_key="difficultyLevel", validate=validate.OneOf(DIFFICULTY_LEVELS))
    audience = fields.List(fields.String(validate=validate.OneOf(AUDIENCE_TYPES)), required=False, load_default=list)
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")

    overview = fields.List(fields.Dict(), required=False, load_default=list)
    learning_outcomes = fields.List(fields.String(), required=False, load_default=list, data_key="learningOutcomes")
    prerequisites = fields.List(fields.String(), required=False, load_default=list)
    duration_value = fields.Integer(required=False, allow_none=True, data_key="durationValue", validate=validate.Range(min=1))
    duration_unit = fields.String(required=False, allow_none=True, data_key="durationUnit", validate=validate.OneOf(DURATION_UNITS))

    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")

    primary_instructor_slug = fields.String(required=False, allow_none=True, data_key="primaryInstructorSlug")
    co_instructor_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="coInstructorSlugs")
    provider_organization_slug = fields.String(required=False, allow_none=True, data_key="providerOrganizationSlug")

    delivery_mode = fields.String(required=False, load_default="self_paced", data_key="deliveryMode", validate=validate.OneOf(DELIVERY_MODES))
    event_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="eventSlugs")

    access_type = fields.String(required=False, load_default="free", data_key="accessType", validate=validate.OneOf(ACCESS_TYPES))
    product_slug = fields.String(required=False, allow_none=True, data_key="productSlug")
    external_url = fields.String(required=False, allow_none=True, data_key="externalUrl")

    related_article_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="relatedArticleSlugs")
    related_resource_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="relatedResourceSlugs")

    featured = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(LEARNING_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)

    # Publish-time requirements (title/slug/instructor/at least one module)
    # are enforced in the route layer, same pattern as every other content
    # type's `_validate_for_publish` — a draft may stay incomplete.


class LearningLessonInputSchema(ma.Schema):
    id = fields.Integer(required=False, allow_none=True)  # present when updating an existing lesson
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    lesson_type = fields.String(required=False, load_default="text", data_key="lessonType", validate=validate.OneOf(LESSON_TYPES))
    summary = fields.String(required=False, allow_none=True)
    content = fields.List(fields.Dict(), required=False, load_default=list)
    article_slug = fields.String(required=False, allow_none=True, data_key="articleSlug")
    resource_slug = fields.String(required=False, allow_none=True, data_key="resourceSlug")
    external_url = fields.String(required=False, allow_none=True, data_key="externalUrl")
    duration_minutes = fields.Integer(required=False, allow_none=True, data_key="durationMinutes", validate=validate.Range(min=0))


class LearningModuleInputSchema(ma.Schema):
    id = fields.Integer(required=False, allow_none=True)  # present when updating an existing module
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    description = fields.String(required=False, allow_none=True)
    lessons = fields.List(fields.Nested(LearningLessonInputSchema), required=False, load_default=list)


class LearningCurriculumInputSchema(ma.Schema):
    """The whole modules+lessons tree, replaced atomically in one request
    (spec section 70: "a validation failure should not leave half the
    curriculum saved"). Ordering is implicit in list order.
    """

    modules = fields.List(fields.Nested(LearningModuleInputSchema), required=True)
