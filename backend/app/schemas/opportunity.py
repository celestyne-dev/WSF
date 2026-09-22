from datetime import date

from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.geography import REGIONS
from app.models.opportunity import (
    CAREER_LEVELS,
    EMPLOYMENT_TYPES,
    FUNDING_TYPES,
    JOB_STATUSES,
    OPPORTUNITY_STATUSES,
    OPPORTUNITY_TYPES,
    REMOTE_SCOPES,
    WORK_MODES,
    Event,
    Job,
    Opportunity,
)
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.people import OrganizationSchema, PersonSchema
from app.schemas.taxonomy import TopicSchema


class JobSchema(ma.SQLAlchemyAutoSchema):
    logo = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Organization.
    organization_id = fields.Integer(dump_only=True)
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))
    is_closed = fields.Method("get_is_closed")

    class Meta:
        model = Job
        load_instance = False
        # posted_by_id is an internal workflow field (which staff/employer
        # account created this listing) — never part of any Job payload,
        # public or CMS; scoping for jobs.create_own happens server-side.
        exclude = ("posted_by_id",)

    def get_is_closed(self, obj):
        """True when the job should present as no longer accepting
        applications — computed at read time rather than via a scheduler.
        """
        if obj.status in ("closed", "expired"):
            return True
        today = date.today()
        if obj.expiry_date and obj.expiry_date < today:
            return True
        if obj.deadline and obj.deadline < today:
            return True
        return False


class OpportunitySchema(ma.SQLAlchemyAutoSchema):
    logo = fields.Nested(MediaSchema, dump_only=True)
    countries_eligible = fields.Nested(CountrySchema, many=True, dump_only=True)
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, exclude=("article_count",))
    # marshmallow-sqlalchemy's auto schema omits FK columns that back a
    # declared relationship — declared explicitly so the CMS editor can
    # always resolve/pre-select the linked Organization.
    organization_id = fields.Integer(dump_only=True)
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name", "logo"))
    is_closed = fields.Method("get_is_closed")

    class Meta:
        model = Opportunity
        load_instance = False

    def get_is_closed(self, obj):
        """True when the opportunity should present as no longer accepting
        applications — computed at read time rather than via a scheduler.
        """
        if obj.status in ("closed", "archived"):
            return True
        today = date.today()
        if obj.expiry_date and obj.expiry_date < today:
            return True
        if obj.deadline and obj.deadline < today:
            return True
        return False


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
    # Not required at the schema level — when an Organization is selected
    # the route fills this from its name, so an editor never has to type a
    # duplicate company name. Still a legitimate, DB-required field for
    # jobs posted without a linked Organization (see validate_employer
    # below).
    company_name = fields.String(required=False, allow_none=True, data_key="companyName")
    logo_media_id = fields.Integer(required=False, allow_none=True, data_key="logoMediaId")
    location = fields.String(required=False, allow_none=True)
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    work_mode = fields.String(required=False, allow_none=True, data_key="workMode", validate=validate.OneOf(WORK_MODES))
    remote_scope = fields.String(required=False, allow_none=True, data_key="remoteScope", validate=validate.OneOf(REMOTE_SCOPES))
    remote_region = fields.String(required=False, allow_none=True, data_key="remoteRegion", validate=validate.OneOf(REGIONS))
    employment_type = fields.String(
        required=False, allow_none=True, data_key="employmentType", validate=validate.OneOf(EMPLOYMENT_TYPES)
    )
    career_level = fields.String(
        required=False, allow_none=True, data_key="careerLevel", validate=validate.OneOf(CAREER_LEVELS)
    )
    industry = fields.String(required=False, allow_none=True)
    salary_min = fields.Integer(required=False, allow_none=True, data_key="salaryMin")
    salary_max = fields.Integer(required=False, allow_none=True, data_key="salaryMax")
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    salary_period = fields.String(required=False, allow_none=True, data_key="salaryPeriod")
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    # Ordered content-block list — same shape as Article.content, sanitized
    # through the same sanitize_content_blocks() service. The employer
    # structures "About the role"/"Responsibilities"/"Requirements"/etc.
    # themselves rather than the app hard-coding those headings.
    description = fields.List(fields.Dict(), required=False, load_default=list)
    application_url = fields.String(required=False, allow_none=True, data_key="applicationUrl", validate=validate.URL(require_tld=True))
    application_instructions = fields.String(required=False, allow_none=True, data_key="applicationInstructions")
    deadline = fields.Date(required=False, allow_none=True)
    published_date = fields.Date(required=False, allow_none=True, data_key="publishedDate")
    expiry_date = fields.Date(required=False, allow_none=True, data_key="expiryDate")
    featured = fields.Boolean(required=False, load_default=False)
    sponsored = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="published", validate=validate.OneOf(JOB_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_employer(self, data, **kwargs):
        if not data.get("organization_id") and not data.get("company_name"):
            raise ValidationError(
                "Select an organization or enter a company name.", field_name="company_name"
            )

    @validates_schema
    def validate_salary_range(self, data, **kwargs):
        salary_min = data.get("salary_min")
        salary_max = data.get("salary_max")
        if salary_min is not None and salary_max is not None and salary_min > salary_max:
            raise ValidationError("Minimum salary cannot exceed maximum salary.", field_name="salary_min")

    @validates_schema
    def validate_dates(self, data, **kwargs):
        deadline = data.get("deadline")
        expiry_date = data.get("expiry_date")
        if deadline and expiry_date and deadline > expiry_date:
            raise ValidationError("Application deadline cannot be after the listing's expiry date.", field_name="deadline")


class OpportunityInputSchema(ma.Schema):
    title = fields.String(required=True, validate=validate.Length(min=1, max=200))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=220))
    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")
    # Not required at the schema level — when an Organization is selected
    # the route fills this from its name, so an editor never has to type a
    # duplicate provider name. Still required overall for opportunities
    # posted without a linked Organization (see validate_provider below).
    organization_name = fields.String(required=False, allow_none=True, data_key="organizationName")
    logo_media_id = fields.Integer(required=False, allow_none=True, data_key="logoMediaId")
    type = fields.String(required=False, allow_none=True, validate=validate.OneOf(OPPORTUNITY_TYPES))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    # Ordered content-block list — same shape as Job.description, sanitized
    # through the same sanitize_content_blocks() service. The editor
    # structures "About"/"What's offered"/"Eligibility"/"How to apply" etc.
    # themselves rather than the app hard-coding those headings.
    description = fields.List(fields.Dict(), required=False, load_default=list)
    eligibility = fields.String(required=False, allow_none=True)
    eligibility_notes = fields.String(required=False, allow_none=True, data_key="eligibilityNotes")
    career_stage = fields.String(required=False, allow_none=True, data_key="careerStage")
    countries_eligible = fields.List(fields.String(), required=False, load_default=list, data_key="countriesEligible")
    location = fields.String(required=False, allow_none=True)
    funding_type = fields.String(required=False, allow_none=True, data_key="fundingType", validate=validate.OneOf(FUNDING_TYPES))
    funding_min = fields.Integer(required=False, allow_none=True, data_key="fundingMin")
    funding_max = fields.Integer(required=False, allow_none=True, data_key="fundingMax")
    currency = fields.String(required=False, allow_none=True, validate=validate.Length(equal=3))
    funding_value = fields.String(required=False, allow_none=True, data_key="fundingValue")
    application_url = fields.String(required=False, allow_none=True, data_key="applicationUrl", validate=validate.URL(require_tld=True))
    application_instructions = fields.String(required=False, allow_none=True, data_key="applicationInstructions")
    opening_date = fields.Date(required=False, allow_none=True, data_key="openingDate")
    deadline = fields.Date(required=False, allow_none=True)
    published_date = fields.Date(required=False, allow_none=True, data_key="publishedDate")
    expiry_date = fields.Date(required=False, allow_none=True, data_key="expiryDate")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    featured = fields.Boolean(required=False, load_default=False)
    sponsored = fields.Boolean(required=False, load_default=False)
    status = fields.String(required=False, load_default="published", validate=validate.OneOf(OPPORTUNITY_STATUSES))
    seo = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_provider(self, data, **kwargs):
        if not data.get("organization_id") and not data.get("organization_name"):
            raise ValidationError(
                "Select an organization or enter a provider name.", field_name="organization_name"
            )

    @validates_schema
    def validate_funding_range(self, data, **kwargs):
        funding_min = data.get("funding_min")
        funding_max = data.get("funding_max")
        if funding_min is not None and funding_max is not None and funding_min > funding_max:
            raise ValidationError("Minimum funding cannot exceed maximum funding.", field_name="funding_min")

    @validates_schema
    def validate_dates(self, data, **kwargs):
        opening_date = data.get("opening_date")
        deadline = data.get("deadline")
        expiry_date = data.get("expiry_date")
        if opening_date and deadline and opening_date > deadline:
            raise ValidationError("Opening date must be before the application deadline.", field_name="opening_date")
        if deadline and expiry_date and deadline > expiry_date:
            raise ValidationError("Application deadline cannot be after the listing's expiry date.", field_name="deadline")


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
