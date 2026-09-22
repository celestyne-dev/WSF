from marshmallow import fields, validate

from app.extensions import ma
from app.models.article import Article
from app.models.people import PERSON_STATUSES, Author, Organization, Person
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.taxonomy import SeriesSchema


class OrganizationSchema(ma.SQLAlchemyAutoSchema):
    logo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)

    class Meta:
        model = Organization
        load_instance = False


class PersonSchema(ma.SQLAlchemyAutoSchema):
    photo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))
    series = fields.Nested(SeriesSchema, many=True, dump_only=True, exclude=("article_count",))

    class Meta:
        model = Person
        load_instance = False


class AuthorSchema(ma.SQLAlchemyAutoSchema):
    photo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    article_count = fields.Method("get_article_count")

    class Meta:
        model = Author
        load_instance = False

    def get_article_count(self, obj):
        return Article.query.filter_by(author_id=obj.id, status="published").count()


class OrganizationInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=160))
    logo_media_id = fields.Integer(required=False, allow_none=True, data_key="logoMediaId")
    industry = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    org_type = fields.String(required=False, allow_none=True, data_key="type")
    description = fields.String(required=False, allow_none=True)
    website = fields.String(required=False, allow_none=True)
    social = fields.Dict(required=False, allow_none=True)
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
    bio = fields.String(required=False, allow_none=True)
    short_bio = fields.String(required=False, allow_none=True, data_key="shortBio")
    expertise = fields.List(fields.String(), required=False, load_default=list)
    location = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    social = fields.Dict(required=False, allow_none=True)
    website = fields.String(required=False, allow_none=True)
    user_id = fields.Integer(required=False, allow_none=True, data_key="userId")
