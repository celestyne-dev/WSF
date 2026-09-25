from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.mentorship import (
    APPLICATION_STATUSES,
    CAREER_STAGES,
    MATCH_STATUSES,
    MEETING_FREQUENCIES,
    MENTORSHIP_FORMATS,
    MentorshipApplication,
    MentorshipApplicationNote,
    MentorshipMatch,
    MentorshipMatchNote,
    MentorshipProgram,
    MentorshipSession,
    PROGRAM_STATUSES,
    SESSION_STATUSES,
)
from app.schemas.community import MemberSchema
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.people import PersonSchema
from app.schemas.taxonomy import TopicSchema
from app.schemas.user import UserSchema

# ---------------------------------------------------------------------------
# Programs
# ---------------------------------------------------------------------------


class MentorshipProgramSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump. See build_public_program_payload() in
    api/v1/mentorship.py for the public-safe subset.
    """

    hero_media_id = fields.Integer(dump_only=True)
    hero_media = fields.Nested(MediaSchema, dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, only=("id", "slug", "name"))
    application_open_now = fields.Method("get_application_open_now", dump_only=True)

    class Meta:
        model = MentorshipProgram
        load_instance = False

    def get_application_open_now(self, obj):
        return obj.applications_open_now()


class MentorshipProgramInputSchema(ma.Schema):
    """Create — `status` is deliberately excluded (dedicated /status
    action, so opening/closing applications is always a conscious step).
    """

    slug = fields.String(required=True, validate=validate.Length(min=1, max=160))
    name = fields.String(required=True, validate=validate.Length(min=1, max=200))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    full_description = fields.List(fields.Dict(), required=False, load_default=list, data_key="fullDescription")
    public_visible = fields.Boolean(required=False, load_default=False, data_key="publicVisible")
    application_opens_at = fields.DateTime(required=False, allow_none=True, data_key="applicationOpensAt")
    application_closes_at = fields.DateTime(required=False, allow_none=True, data_key="applicationClosesAt")
    program_starts_at = fields.Date(required=False, allow_none=True, data_key="programStartsAt")
    program_ends_at = fields.Date(required=False, allow_none=True, data_key="programEndsAt")
    mentor_capacity = fields.Integer(required=False, allow_none=True, data_key="mentorCapacity", validate=validate.Range(min=0))
    mentee_capacity = fields.Integer(required=False, allow_none=True, data_key="menteeCapacity", validate=validate.Range(min=0))
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    eligibility_summary = fields.String(required=False, allow_none=True, data_key="eligibilitySummary")
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    seo = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        opens, closes = data.get("application_opens_at"), data.get("application_closes_at")
        if opens and closes and closes < opens:
            raise ValidationError("Application close date can't be before the open date.", field_name="application_closes_at")
        starts, ends = data.get("program_starts_at"), data.get("program_ends_at")
        if starts and ends and ends < starts:
            raise ValidationError("Program end date can't be before the start date.", field_name="program_ends_at")


class MentorshipProgramUpdateSchema(ma.Schema):
    """No load_default anywhere — a key absent from a PATCH leaves that
    field untouched (house partial-update rule)."""

    name = fields.String(required=False, validate=validate.Length(min=1, max=200))
    short_description = fields.String(required=False, allow_none=True, data_key="shortDescription")
    full_description = fields.List(fields.Dict(), required=False, data_key="fullDescription")
    public_visible = fields.Boolean(required=False, data_key="publicVisible")
    application_opens_at = fields.DateTime(required=False, allow_none=True, data_key="applicationOpensAt")
    application_closes_at = fields.DateTime(required=False, allow_none=True, data_key="applicationClosesAt")
    program_starts_at = fields.Date(required=False, allow_none=True, data_key="programStartsAt")
    program_ends_at = fields.Date(required=False, allow_none=True, data_key="programEndsAt")
    mentor_capacity = fields.Integer(required=False, allow_none=True, data_key="mentorCapacity", validate=validate.Range(min=0))
    mentee_capacity = fields.Integer(required=False, allow_none=True, data_key="menteeCapacity", validate=validate.Range(min=0))
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    eligibility_summary = fields.String(required=False, allow_none=True, data_key="eligibilitySummary")
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    topic_slugs = fields.List(fields.String(), required=False, data_key="topicSlugs")
    seo = fields.Dict(required=False, allow_none=True)


class MentorshipProgramStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(PROGRAM_STATUSES))


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


class MentorshipApplicationNoteSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = MentorshipApplicationNote
        load_instance = False


class MentorshipApplicationPreviewSchema(ma.SQLAlchemyAutoSchema):
    """A lightweight preview used when an application is nested inside a
    Match — avoids duplicating the full record (topics/notes/etc.) twice
    per match.
    """

    full_name = fields.String(dump_only=True)

    class Meta:
        model = MentorshipApplication
        fields = (
            "id", "role", "first_name", "last_name", "full_name", "email", "professional_title",
            "organization_name", "status", "mentor_capacity", "mentor_active",
        )


class MentorshipApplicationSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump — the full record. See build_public_* helpers in
    api/v1/mentorship.py for what (if anything) is ever public — mentorship
    applications are private by default and have no public serializer.
    """

    full_name = fields.String(dump_only=True)
    program = fields.Nested(MentorshipProgramSchema, dump_only=True, only=("id", "slug", "name", "status"))
    country = fields.Nested(CountrySchema, dump_only=True)
    member_id = fields.Integer(dump_only=True)
    member = fields.Nested(MemberSchema, dump_only=True, only=("id", "first_name", "last_name", "email"))
    person_id = fields.Integer(dump_only=True)
    person = fields.Nested(PersonSchema, dump_only=True, only=("id", "slug", "name", "title"))
    reviewed_by = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name"))
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, only=("id", "slug", "name"))
    notes = fields.Nested(MentorshipApplicationNoteSchema, many=True, dump_only=True)
    active_mentee_count = fields.Method("get_active_mentee_count", dump_only=True)

    class Meta:
        model = MentorshipApplication
        load_instance = False

    def get_active_mentee_count(self, obj):
        return obj.active_mentee_count()


class MentorshipApplicationSubmitInputSchema(ma.Schema):
    """The public mentor/mentee application form — no account, no status,
    no capacity/mentor_active fields (staff-only operational fields).
    """

    program_id = fields.Integer(required=True, data_key="programId")
    role = fields.String(required=True, validate=validate.OneOf(("mentor", "mentee")))

    first_name = fields.String(required=True, data_key="firstName", validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, data_key="lastName", validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)

    professional_title = fields.String(required=False, allow_none=True, data_key="professionalTitle", validate=validate.Length(max=200))
    organization_name = fields.String(required=False, allow_none=True, data_key="organizationName", validate=validate.Length(max=200))
    industry = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    years_experience = fields.Integer(required=False, allow_none=True, data_key="yearsExperience", validate=validate.Range(min=0, max=80))
    linkedin_url = fields.String(required=False, allow_none=True, data_key="linkedinUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    website_url = fields.String(required=False, allow_none=True, data_key="websiteUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))

    background_text = fields.String(required=False, allow_none=True, data_key="backgroundText", validate=validate.Length(max=2000))
    goals_text = fields.String(required=False, allow_none=True, data_key="goalsText", validate=validate.Length(max=2000))
    support_offered_text = fields.String(required=False, allow_none=True, data_key="supportOfferedText", validate=validate.Length(max=2000))

    career_stage = fields.String(required=False, allow_none=True, data_key="careerStage", validate=validate.OneOf(CAREER_STAGES))
    career_stages_supported = fields.List(
        fields.String(validate=validate.OneOf(CAREER_STAGES)), required=False, load_default=list, data_key="careerStagesSupported"
    )

    country_code = fields.String(required=True, data_key="countryCode")
    timezone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    meeting_frequency = fields.String(required=False, allow_none=True, data_key="meetingFrequency", validate=validate.OneOf(MEETING_FREQUENCIES))
    mentorship_format = fields.String(required=False, allow_none=True, data_key="mentorshipFormat", validate=validate.OneOf(MENTORSHIP_FORMATS))
    availability_note = fields.String(required=False, allow_none=True, data_key="availabilityNote", validate=validate.Length(max=500))

    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")

    consent_given = fields.Boolean(required=True, data_key="consentGiven")
    subscribe_newsletter = fields.Boolean(required=False, load_default=False, data_key="subscribeNewsletter")
    acquisition = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_consent(self, data, **kwargs):
        if not data.get("consent_given"):
            raise ValidationError("Please confirm we can use this information to process your application.", field_name="consent_given")


class MentorshipApplicationAdminUpdateSchema(ma.Schema):
    """No load_default anywhere. Excludes program_id/role (immutable after
    submission) and status (dedicated /status action)."""

    first_name = fields.String(required=False, data_key="firstName", validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=False, data_key="lastName", validate=validate.Length(min=1, max=100))
    email = fields.Email(required=False)
    professional_title = fields.String(required=False, allow_none=True, data_key="professionalTitle", validate=validate.Length(max=200))
    organization_name = fields.String(required=False, allow_none=True, data_key="organizationName", validate=validate.Length(max=200))
    industry = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    years_experience = fields.Integer(required=False, allow_none=True, data_key="yearsExperience", validate=validate.Range(min=0, max=80))
    linkedin_url = fields.String(required=False, allow_none=True, data_key="linkedinUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    website_url = fields.String(required=False, allow_none=True, data_key="websiteUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    background_text = fields.String(required=False, allow_none=True, data_key="backgroundText")
    goals_text = fields.String(required=False, allow_none=True, data_key="goalsText")
    support_offered_text = fields.String(required=False, allow_none=True, data_key="supportOfferedText")
    career_stage = fields.String(required=False, allow_none=True, data_key="careerStage", validate=validate.OneOf(CAREER_STAGES))
    career_stages_supported = fields.List(
        fields.String(validate=validate.OneOf(CAREER_STAGES)), required=False, data_key="careerStagesSupported"
    )
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    timezone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50))
    meeting_frequency = fields.String(required=False, allow_none=True, data_key="meetingFrequency", validate=validate.OneOf(MEETING_FREQUENCIES))
    mentorship_format = fields.String(required=False, allow_none=True, data_key="mentorshipFormat", validate=validate.OneOf(MENTORSHIP_FORMATS))
    availability_note = fields.String(required=False, allow_none=True, data_key="availabilityNote")
    mentor_capacity = fields.Integer(required=False, allow_none=True, data_key="mentorCapacity", validate=validate.Range(min=0))
    mentor_active = fields.Boolean(required=False, data_key="mentorActive")
    topic_slugs = fields.List(fields.String(), required=False, data_key="topicSlugs")
    member_id = fields.Integer(required=False, allow_none=True, data_key="memberId")
    person_id = fields.Integer(required=False, allow_none=True, data_key="personId")


class MentorshipApplicationStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(APPLICATION_STATUSES))


class MentorshipApplicationNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=2000))


# ---------------------------------------------------------------------------
# Matches
# ---------------------------------------------------------------------------


class MentorshipMatchNoteSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = MentorshipMatchNote
        load_instance = False


class MentorshipSessionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = MentorshipSession
        load_instance = False


class MentorshipMatchSchema(ma.SQLAlchemyAutoSchema):
    program = fields.Nested(MentorshipProgramSchema, dump_only=True, only=("id", "slug", "name"))
    mentor_application_id = fields.Integer(dump_only=True)
    mentor_application = fields.Nested(MentorshipApplicationPreviewSchema, dump_only=True)
    mentee_application_id = fields.Integer(dump_only=True)
    mentee_application = fields.Nested(MentorshipApplicationPreviewSchema, dump_only=True)
    notes = fields.Nested(MentorshipMatchNoteSchema, many=True, dump_only=True)
    sessions = fields.Nested(MentorshipSessionSchema, many=True, dump_only=True)

    class Meta:
        model = MentorshipMatch
        load_instance = False


class MentorshipMatchCreateInputSchema(ma.Schema):
    mentor_application_id = fields.Integer(required=True, data_key="mentorApplicationId")
    mentee_application_id = fields.Integer(required=True, data_key="menteeApplicationId")
    planned_start_date = fields.Date(required=False, allow_none=True, data_key="plannedStartDate")
    planned_end_date = fields.Date(required=False, allow_none=True, data_key="plannedEndDate")
    matching_notes = fields.String(required=False, allow_none=True, data_key="matchingNotes")

    @validates_schema
    def validate_dates(self, data, **kwargs):
        starts, ends = data.get("planned_start_date"), data.get("planned_end_date")
        if starts and ends and ends < starts:
            raise ValidationError("Planned end date can't be before the planned start date.", field_name="planned_end_date")


class MentorshipMatchUpdateSchema(ma.Schema):
    planned_start_date = fields.Date(required=False, allow_none=True, data_key="plannedStartDate")
    planned_end_date = fields.Date(required=False, allow_none=True, data_key="plannedEndDate")


class MentorshipMatchStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(MATCH_STATUSES))
    closure_reason = fields.String(required=False, allow_none=True, data_key="closureReason", validate=validate.Length(max=1000))


class MentorshipMatchNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=2000))


class MentorshipSessionInputSchema(ma.Schema):
    session_date = fields.Date(required=True, data_key="sessionDate")
    session_number = fields.Integer(required=False, allow_none=True, data_key="sessionNumber", validate=validate.Range(min=1))
    status = fields.String(required=False, load_default="scheduled", validate=validate.OneOf(SESSION_STATUSES))
    summary = fields.String(required=False, allow_none=True)
    next_step_note = fields.String(required=False, allow_none=True, data_key="nextStepNote")


class MentorshipSessionUpdateSchema(ma.Schema):
    session_date = fields.Date(required=False, data_key="sessionDate")
    session_number = fields.Integer(required=False, allow_none=True, data_key="sessionNumber", validate=validate.Range(min=1))
    status = fields.String(required=False, validate=validate.OneOf(SESSION_STATUSES))
    summary = fields.String(required=False, allow_none=True)
    next_step_note = fields.String(required=False, allow_none=True, data_key="nextStepNote")
