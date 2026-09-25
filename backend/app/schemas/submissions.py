from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.article import AI_INVOLVEMENT_VALUES
from app.models.submissions import (
    CONTENT_ORIGINS,
    STORY_TYPES,
    SUBJECT_PERMISSION_STATUSES,
    SubmissionMedia,
    SubmissionNote,
    StorySubmission,
    SUBMISSION_STATUSES,
    VERIFICATION_STATUSES,
)
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.people import OrganizationSchema, PersonSchema
from app.schemas.taxonomy import SeriesSchema, TopicSchema
from app.schemas.user import UserSchema

_URL_VALIDATOR = validate.URL(schemes={"http", "https"}, error="Must be a valid http(s) URL.")


class ArticleRefSchema(ma.Schema):
    """The minimal, admin-only pointer used for Submission<->Article
    provenance navigation — never the full ArticleSchema, and never sent
    on any public response.
    """

    id = fields.Integer(dump_only=True)
    slug = fields.String(dump_only=True)
    title = fields.String(dump_only=True)
    status = fields.String(dump_only=True)


class SubmissionNoteSchema(ma.SQLAlchemyAutoSchema):
    """Internal, staff-only — never used on any public response."""

    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = SubmissionNote
        load_instance = False
        exclude = ("submission_id", "user_id")


class SubmissionMediaSchema(ma.SQLAlchemyAutoSchema):
    media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = SubmissionMedia
        load_instance = False
        exclude = ("submission_id",)


# ---------------------------------------------------------------------------
# Admin — the full internal shape. Never returned to an unauthenticated
# request; see submissions.manage-gated routes in api/v1/submissions.py.
# ---------------------------------------------------------------------------


class StorySubmissionSchema(ma.SQLAlchemyAutoSchema):
    country = fields.Nested(CountrySchema, dump_only=True)
    series = fields.Nested(SeriesSchema, dump_only=True, only=("id", "slug", "name"))
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, only=("id", "slug", "name"))
    assigned_editor = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))
    person = fields.Nested(PersonSchema, dump_only=True, only=("id", "slug", "name"))
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name"))
    resulting_article = fields.Nested(ArticleRefSchema, dump_only=True)
    notes = fields.Nested(SubmissionNoteSchema, many=True, dump_only=True)
    media_items = fields.Nested(SubmissionMediaSchema, many=True, dump_only=True)
    full_name = fields.String(dump_only=True)

    class Meta:
        model = StorySubmission
        load_instance = False


class SubmissionListItemSchema(ma.SQLAlchemyAutoSchema):
    """A lighter shape for the admin list view — no body/consent/notes."""

    country = fields.Nested(CountrySchema, dump_only=True)
    assigned_editor = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))
    full_name = fields.String(dump_only=True)

    class Meta:
        model = StorySubmission
        load_instance = False
        exclude = (
            "body",
            "why_it_matters",
            "key_lessons",
            "consent_review_given",
            "consent_contact_given",
            "consent_accuracy_confirmed",
            "consent_media_rights_confirmed",
            "consent_recorded_at",
            "editorial_assessment",
            "ai_provenance_note",
            "information_requested_note",
        )


# ---------------------------------------------------------------------------
# Public submission input — the ABOUT YOU / ABOUT THE STORY / SUBJECT /
# MEDIA / PERMISSIONS form. Never dumped back — write-only besides the
# confirmation the route builds by hand.
# ---------------------------------------------------------------------------


class SubmissionMediaInputSchema(ma.Schema):
    media_id = fields.Integer(required=True, data_key="mediaId")
    caption = fields.String(required=False, allow_none=True, validate=validate.Length(max=500))
    credit = fields.String(required=False, allow_none=True, validate=validate.Length(max=255))
    rights_confirmed = fields.Boolean(required=True, data_key="rightsConfirmed")


class StorySubmissionInputSchema(ma.Schema):
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=120), data_key="firstName")
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=120), data_key="lastName")
    email = fields.Email(required=True)
    country_code = fields.String(required=True, data_key="countryCode")
    city = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    professional_title = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="professionalTitle")
    organization_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="organizationName")
    linkedin_url = fields.String(required=False, allow_none=True, validate=[validate.Length(max=500), _URL_VALIDATOR], data_key="linkedinUrl")
    website_url = fields.String(required=False, allow_none=True, validate=[validate.Length(max=500), _URL_VALIDATOR], data_key="websiteUrl")

    title = fields.String(required=True, validate=validate.Length(min=1, max=300))
    summary = fields.String(required=True, validate=validate.Length(min=1, max=2000))
    body = fields.String(required=True, validate=validate.Length(min=1, max=20000))
    why_it_matters = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="whyItMatters")
    key_lessons = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="keyLessons")
    story_type = fields.String(required=False, allow_none=True, validate=validate.OneOf(STORY_TYPES), data_key="storyType")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")

    subject_is_submitter = fields.Boolean(required=False, load_default=True, data_key="subjectIsSubmitter")
    subject_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="subjectName")
    subject_relationship = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="subjectRelationship")

    content_origin = fields.String(required=False, allow_none=True, validate=validate.OneOf(CONTENT_ORIGINS), data_key="contentOrigin")
    previous_publication_url = fields.String(
        required=False, allow_none=True, validate=[validate.Length(max=500), _URL_VALIDATOR], data_key="previousPublicationUrl"
    )
    ai_involvement = fields.String(
        required=False, load_default="none", validate=validate.OneOf(AI_INVOLVEMENT_VALUES), data_key="aiInvolvement"
    )
    ai_provenance_note = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="aiProvenanceNote")

    media = fields.List(fields.Nested(SubmissionMediaInputSchema), required=False, load_default=list)

    consent_review_given = fields.Boolean(required=True, data_key="consentReviewGiven")
    consent_contact_given = fields.Boolean(required=True, data_key="consentContactGiven")
    consent_accuracy_confirmed = fields.Boolean(required=True, data_key="consentAccuracyConfirmed")
    consent_media_rights_confirmed = fields.Boolean(required=False, allow_none=True, data_key="consentMediaRightsConfirmed")
    newsletter_opt_in = fields.Boolean(required=False, load_default=False, data_key="newsletterOptIn")

    acquisition = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_consent(self, data, **kwargs):
        for field in ("consent_review_given", "consent_contact_given", "consent_accuracy_confirmed"):
            if not data.get(field):
                raise ValidationError("Please confirm all required permissions before submitting.", field_name=field)
        if data.get("media") and not data.get("consent_media_rights_confirmed"):
            raise ValidationError(
                "Please confirm you have permission to submit any attached images.",
                field_name="consent_media_rights_confirmed",
            )

    @validates_schema
    def validate_subject(self, data, **kwargs):
        if not data.get("subject_is_submitter", True) and not (data.get("subject_name") or "").strip():
            raise ValidationError("Please tell us who this story is about.", field_name="subject_name")


# ---------------------------------------------------------------------------
# Admin update / action schemas — every field optional, no load_default,
# so a PATCH only ever touches keys actually present (see the Mentorship/
# Community house rule on partial-update defaults).
# ---------------------------------------------------------------------------


class SubmissionUpdateSchema(ma.Schema):
    story_type = fields.String(required=False, allow_none=True, validate=validate.OneOf(STORY_TYPES), data_key="storyType")
    topic_slugs = fields.List(fields.String(), required=False, data_key="topicSlugs")
    series_id = fields.Integer(required=False, allow_none=True, data_key="seriesId")
    recommended_format = fields.String(required=False, allow_none=True, validate=validate.Length(max=120), data_key="recommendedFormat")
    verification_status = fields.String(required=False, validate=validate.OneOf(VERIFICATION_STATUSES), data_key="verificationStatus")
    permission_followup_required = fields.Boolean(required=False, data_key="permissionFollowupRequired")
    media_followup_required = fields.Boolean(required=False, data_key="mediaFollowupRequired")
    information_requested_note = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="informationRequestedNote")
    editorial_assessment = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="editorialAssessment")
    subject_permission_status = fields.String(
        required=False, validate=validate.OneOf(SUBJECT_PERMISSION_STATUSES), data_key="subjectPermissionStatus"
    )
    person_id = fields.Integer(required=False, allow_none=True, data_key="personId")
    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")


class SubmissionStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(SUBMISSION_STATUSES))


class SubmissionAssignInputSchema(ma.Schema):
    editor_id = fields.Integer(required=True, allow_none=True, data_key="editorId")


class SubmissionNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=4000))


class SubmissionConvertToArticleInputSchema(ma.Schema):
    """The deliberate 'Create Article Draft' handoff — see
    SubmissionConvertToArticleResource. Requires an existing Author since
    Article.author_id is not nullable; WSF's Article CMS has no auto-
    created 'editorial team' identity to fall back to, and creating one
    implicitly would risk duplicating author identities.
    """

    author_id = fields.Integer(required=True, data_key="authorId")
    include_media = fields.Boolean(required=False, load_default=True, data_key="includeMedia")
