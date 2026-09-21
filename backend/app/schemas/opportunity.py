from marshmallow import fields, validate

from app.extensions import ma
from app.models.opportunity import Event, Job, Opportunity
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.people import OrganizationSchema, PersonSchema
from app.schemas.taxonomy import TopicSchema


class JobSchema(ma.SQLAlchemyAutoSchema):
    logo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))

    class Meta:
        model = Job
        load_instance = False


class OpportunitySchema(ma.SQLAlchemyAutoSchema):
    logo = fields.Nested(MediaSchema, dump_only=True)
    countries_eligible = fields.Nested(CountrySchema, many=True, dump_only=True)
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, exclude=("article_count",))
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))

    class Meta:
        model = Opportunity
        load_instance = False


class EventSchema(ma.SQLAlchemyAutoSchema):
    cover_media = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    speakers = fields.Nested(PersonSchema, many=True, dump_only=True)
    sponsors = fields.Nested(OrganizationSchema, many=True, dump_only=True)

    class Meta:
        model = Event
        load_instance = False


class JobInputSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")
    company_name = fields.String(required=True, data_key="companyName")
    logo_media_id = fields.Integer(required=False, allow_none=True, data_key="logoMediaId")
    location = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    work_mode = fields.String(required=False, allow_none=True, data_key="workMode")
    employment_type = fields.String(required=False, allow_none=True, data_key="employmentType")
    career_level = fields.String(required=False, allow_none=True, data_key="careerLevel")
    industry = fields.String(required=False, allow_none=True)
    salary_min = fields.Integer(required=False, allow_none=True, data_key="salaryMin")
    salary_max = fields.Integer(required=False, allow_none=True, data_key="salaryMax")
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    salary_period = fields.String(required=False, allow_none=True, data_key="salaryPeriod")
    description = fields.String(required=False, allow_none=True)
    responsibilities = fields.List(fields.String(), required=False, load_default=list)
    requirements = fields.List(fields.String(), required=False, load_default=list)
    benefits = fields.List(fields.String(), required=False, load_default=list)
    application_url = fields.String(required=False, allow_none=True, data_key="applicationUrl")
    application_instructions = fields.String(required=False, allow_none=True, data_key="applicationInstructions")
    deadline = fields.Date(required=False, allow_none=True)
    published_date = fields.Date(required=False, allow_none=True, data_key="publishedDate")
    expiry_date = fields.Date(required=False, allow_none=True, data_key="expiryDate")
    featured = fields.Boolean(required=False, load_default=False)
    sponsored = fields.Boolean(required=False, load_default=False)
    status = fields.String(
        required=False, load_default="published", validate=validate.OneOf(["draft", "published", "expired", "closed"])
    )


class OpportunityInputSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")
    organization_name = fields.String(required=False, allow_none=True, data_key="organizationName")
    logo_media_id = fields.Integer(required=False, allow_none=True, data_key="logoMediaId")
    type = fields.String(required=False, allow_none=True)
    description = fields.String(required=False, allow_none=True)
    eligibility = fields.String(required=False, allow_none=True)
    countries_eligible = fields.List(fields.String(), required=False, load_default=list, data_key="countriesEligible")
    location = fields.String(required=False, allow_none=True)
    deadline = fields.Date(required=False, allow_none=True)
    funding_value = fields.String(required=False, allow_none=True, data_key="fundingValue")
    application_url = fields.String(required=False, allow_none=True, data_key="applicationUrl")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    featured = fields.Boolean(required=False, load_default=False)
    sponsored = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="published", validate=validate.OneOf(["draft", "published", "closed"]))


class AgendaItemSchema(ma.Schema):
    time = fields.String(required=True)
    title = fields.String(required=True)


class EventInputSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    description = fields.String(required=False, allow_none=True)
    type = fields.String(required=False, allow_none=True)
    format = fields.String(required=False, allow_none=True, validate=validate.OneOf(["in-person", "virtual", "hybrid"]))
    date = fields.Date(required=True)
    start_time = fields.Time(required=False, allow_none=True, data_key="startTime")
    end_time = fields.Time(required=False, allow_none=True, data_key="endTime")
    timezone = fields.String(required=False, allow_none=True)
    location = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    venue = fields.String(required=False, allow_none=True)
    virtual_link = fields.String(required=False, allow_none=True, data_key="virtualLink")
    registration_url = fields.String(required=False, allow_none=True, data_key="registrationUrl")
    ticket_price = fields.Integer(required=False, allow_none=True, data_key="ticketPrice")
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    capacity = fields.Integer(required=False, allow_none=True)
    agenda = fields.List(fields.Nested(AgendaItemSchema), required=False, load_default=list)
    status = fields.String(
        required=False, load_default="upcoming", validate=validate.OneOf(["upcoming", "past", "cancelled"])
    )
    cover_media_id = fields.Integer(required=False, allow_none=True, data_key="coverMediaId")
    featured = fields.Boolean(required=False, load_default=False)
    speaker_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="speakerSlugs")
    sponsor_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="sponsorSlugs")
