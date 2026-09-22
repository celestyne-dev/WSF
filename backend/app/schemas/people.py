from marshmallow import fields, validate

from app.extensions import ma
from app.models.article import Article
from app.models.people import (
    AUTHOR_STATUSES,
    ORGANIZATION_STATUSES,
    ORGANIZATION_TYPES,
    PERSON_STATUSES,
    Author,
    Organization,
    Person,
)
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.taxonomy import SeriesSchema, TopicSchema


class OrganizationSchema(ma.SQLAlchemyAutoSchema):
    logo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    people_count = fields.Method("get_people_count")

    class Meta:
        model = Organization
        load_instance = False

    def get_people_count(self, obj):
        return Person.query.filter_by(organization_id=obj.id, status="published").count()


class PersonSchema(ma.SQLAlchemyAutoSchema):
    photo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Organization even when that
    # Organization is still a draft.
    organization_id = fields.Integer(dump_only=True)
    # A lightweight, published-only preview — never leaks an unpublished
    # Organization through a Person response.
    organization = fields.Method("get_organization", dump_only=True)
    series = fields.Nested(SeriesSchema, many=True, dump_only=True, exclude=("article_count",))

    class Meta:
        model = Person
        load_instance = False

    def get_organization(self, obj):
        if not obj.organization or obj.organization.status != "published":
            return None
        return {
            "id": obj.organization.id,
            "slug": obj.organization.slug,
            "name": obj.organization.name,
            "logo": MediaSchema().dump(obj.organization.logo) if obj.organization.logo else None,
        }


class AuthorSchema(ma.SQLAlchemyAutoSchema):
    photo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, exclude=("article_count",))
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship (same reason Person's organization_id/
    # country_code/photo_media_id aren't auto-dumped) — declared explicitly
    # so the CMS editor can always resolve/pre-select the linked Person
    # (from its own permission-gated People list) even when that Person is
    # still a draft.
    person_id = fields.Integer(dump_only=True)
    # A lightweight, published-only preview of the linked Person — never
    # leaks an unpublished Person profile through an Author response.
    person = fields.Method("get_person", dump_only=True)
    article_count = fields.Method("get_article_count")

    class Meta:
        model = Author
        load_instance = False
        # user_id is the internal staff-login link — never part of any
        # Author payload, public or CMS (this task doesn't manage it).
        exclude = ("user_id",)

    def get_article_count(self, obj):
        return Article.query.filter_by(author_id=obj.id, status="published").count()

    def get_person(self, obj):
        if not obj.person or obj.person.status != "published":
            return None
        return {
            "slug": obj.person.slug,
            "name": obj.person.name,
            "title": obj.person.title,
            "photo": MediaSchema().dump(obj.person.photo) if obj.person.photo else None,
        }


class OrganizationInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=160))
    logo_media_id = fields.Integer(required=False, allow_none=True, data_key="logoMediaId")
    industry = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    location = fields.String(required=False, allow_none=True)
    founded_year = fields.Integer(required=False, allow_none=True, data_key="foundedYear")
    org_type = fields.String(required=False, allow_none=True, data_key="type", validate=validate.OneOf(ORGANIZATION_TYPES))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    # Ordered content-block list — same shape as Article.content, sanitized
    # through the same sanitize_content_blocks() service before persisting.
    description = fields.List(fields.Dict(), required=False, load_default=list)
    website = fields.String(required=False, allow_none=True, validate=validate.URL(require_tld=True))
    social = fields.Dict(required=False, allow_none=True)
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(ORGANIZATION_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)
    featured = fields.Boolean(required=False, load_default=False)


class PersonInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=160))
    pronouns = fields.String(required=False, allow_none=True, validate=validate.Length(max=40))
    photo_media_id = fields.Integer(required=False, allow_none=True, data_key="photoMediaId")
    title = fields.String(required=False, allow_none=True)
    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")
    location = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    industry = fields.String(required=False, allow_none=True)
    profession = fields.String(required=False, allow_none=True)
    expertise = fields.List(fields.String(), required=False, load_default=list)
    featured_quote = fields.String(required=False, allow_none=True, data_key="featuredQuote")
    short_bio = fields.String(required=False, allow_none=True, data_key="shortBio")
    # Ordered content-block list — same shape as Article.content, sanitized
    # through the same sanitize_content_blocks() service before persisting.
    bio = fields.List(fields.Dict(), required=False, load_default=list)
    achievements = fields.List(fields.String(), required=False, load_default=list)
    career_timeline = fields.List(fields.Dict(), required=False, load_default=list, data_key="careerTimeline")
    awards = fields.List(fields.String(), required=False, load_default=list)
    website = fields.String(required=False, allow_none=True)
    social = fields.Dict(required=False, allow_none=True)
    series_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="seriesSlugs")
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(PERSON_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)
    featured = fields.Boolean(required=False, load_default=False)


class AuthorInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=160))
    role = fields.String(required=False, allow_none=True)
    photo_media_id = fields.Integer(required=False, allow_none=True, data_key="photoMediaId")
    # Ordered content-block list — same shape as Article.content/Person.bio,
    # sanitized through the same sanitize_content_blocks() service.
    bio = fields.List(fields.Dict(), required=False, load_default=list)
    short_bio = fields.String(required=False, allow_none=True, data_key="shortBio")
    expertise = fields.List(fields.String(), required=False, load_default=list)
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    location = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    social = fields.Dict(required=False, allow_none=True)
    website = fields.String(required=False, allow_none=True, validate=validate.URL(require_tld=True))
    person_id = fields.Integer(required=False, allow_none=True, data_key="personId")
    status = fields.String(required=False, load_default="draft", validate=validate.OneOf(AUTHOR_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)
