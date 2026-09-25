from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.nominations import (
    NOMINATION_STATUSES,
    NOMINEE_AWARENESS_VALUES,
    Nomination,
    NominationNote,
    VERIFICATION_STATES,
)
from app.schemas.geography import CountrySchema
from app.schemas.people import OrganizationSchema, PersonSchema
from app.schemas.taxonomy import SeriesSchema, TopicSchema
from app.schemas.user import UserSchema

_URL_VALIDATOR = validate.URL(schemes={"http", "https"}, error="Must be a valid http(s) URL.")


class ArticleRefSchema(ma.Schema):
    """The minimal, admin-only pointer used for Nomination<->Article
    provenance navigation — never the full ArticleSchema, and never sent
    on any public response.
    """

    id = fields.Integer(dump_only=True)
    slug = fields.String(dump_only=True)
    title = fields.String(dump_only=True)
    status = fields.String(dump_only=True)


class NominationNoteSchema(ma.SQLAlchemyAutoSchema):
    """Internal, staff-only — never used on any public response."""

    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = NominationNote
        load_instance = False
        exclude = ("nomination_id", "user_id")


class NominationRelatedSchema(ma.Schema):
    """A lightweight cross-reference to another nomination sharing the same
    nominee — surfaces provenance without merging or overwriting either
    record. See MULTIPLE NOMINATIONS FOR ONE PERSON.
    """

    id = fields.Integer(dump_only=True)
    reference = fields.String(dump_only=True)
    status = fields.String(dump_only=True)
    submitted_at = fields.DateTime(dump_only=True)


# ---------------------------------------------------------------------------
# Admin — the full internal shape. Never returned to an unauthenticated
# request; see nominations.manage-gated routes in api/v1/nominations.py.
# ---------------------------------------------------------------------------


class NominationSchema(ma.SQLAlchemyAutoSchema):
    country = fields.Nested(CountrySchema, dump_only=True)
    series = fields.Nested(SeriesSchema, dump_only=True, only=("id", "slug", "name"))
    topics = fields.Nested(TopicSchema, many=True, dump_only=True, only=("id", "slug", "name"))
    assigned_reviewer = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))
    person = fields.Nested(PersonSchema, dump_only=True, only=("id", "slug", "name"))
    organization = fields.Nested(OrganizationSchema, dump_only=True, only=("id", "slug", "name"))
    resulting_article = fields.Nested(ArticleRefSchema, dump_only=True)
    notes = fields.Nested(NominationNoteSchema, many=True, dump_only=True)
    related_nominations = fields.Nested(NominationRelatedSchema, many=True, dump_only=True)

    class Meta:
        model = Nomination
        load_instance = False


class NominationListItemSchema(ma.SQLAlchemyAutoSchema):
    """A lighter shape for the admin list view — no evidence/consent/notes."""

    country = fields.Nested(CountrySchema, dump_only=True)
    series = fields.Nested(SeriesSchema, dump_only=True, only=("id", "slug", "name"))
    assigned_reviewer = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = Nomination
        load_instance = False
        exclude = (
            "achievements",
            "why_significant",
            "who_impacted",
            "supporting_links",
            "short_bio",
            "nominee_email",
            "nominator_email",
            "nominator_organization",
            "relationship_to_nominee",
            "consent_accuracy_confirmed",
            "consent_review_given",
            "consent_contact_given",
            "consent_recorded_at",
            "editorial_assessment",
            "verification_notes",
        )


# ---------------------------------------------------------------------------
# Public nomination input — the ABOUT THE NOMINEE / WHY YOU ARE NOMINATING
# HER / ABOUT THE NOMINATOR / CONSENT form. Never dumped back — write-only
# besides the confirmation the route builds by hand.
# ---------------------------------------------------------------------------


class SupportingLinkInputSchema(ma.Schema):
    url = fields.String(required=True, validate=[validate.Length(max=500), _URL_VALIDATOR])
    label = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))


class NominationInputSchema(ma.Schema):
    nominee_name = fields.String(required=True, validate=validate.Length(min=1, max=200), data_key="nomineeName")
    country_code = fields.String(required=True, data_key="countryCode")
    city = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    professional_title = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="professionalTitle")
    organization_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="organizationName")
    website_url = fields.String(required=False, allow_none=True, validate=[validate.Length(max=500), _URL_VALIDATOR], data_key="websiteUrl")
    linkedin_url = fields.String(required=False, allow_none=True, validate=[validate.Length(max=500), _URL_VALIDATOR], data_key="linkedinUrl")
    short_bio = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="shortBio")

    nomination_summary = fields.String(required=False, allow_none=True, validate=validate.Length(max=300), data_key="nominationSummary")
    achievements = fields.String(required=True, validate=validate.Length(min=1, max=8000))
    why_significant = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="whySignificant")
    who_impacted = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="whoImpacted")
    supporting_links = fields.List(fields.Nested(SupportingLinkInputSchema), required=False, load_default=list, data_key="supportingLinks")
    topic_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="topicSlugs")
    series_id = fields.Integer(required=False, allow_none=True, data_key="seriesId")

    is_self_nomination = fields.Boolean(required=False, load_default=False, data_key="isSelfNomination")

    nominator_name = fields.String(required=True, validate=validate.Length(min=1, max=200), data_key="nominatorName")
    nominator_email = fields.Email(required=True, data_key="nominatorEmail")
    nominator_organization = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="nominatorOrganization")
    relationship_to_nominee = fields.String(required=False, allow_none=True, validate=validate.Length(max=200), data_key="relationshipToNominee")
    nominee_awareness = fields.String(
        required=False, load_default="unknown", validate=validate.OneOf(NOMINEE_AWARENESS_VALUES), data_key="nomineeAwareness"
    )

    consent_accuracy_confirmed = fields.Boolean(required=True, data_key="consentAccuracyConfirmed")
    consent_review_given = fields.Boolean(required=True, data_key="consentReviewGiven")
    consent_contact_given = fields.Boolean(required=True, data_key="consentContactGiven")
    newsletter_opt_in = fields.Boolean(required=False, load_default=False, data_key="newsletterOptIn")

    acquisition = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_consent(self, data, **kwargs):
        for field in ("consent_accuracy_confirmed", "consent_review_given", "consent_contact_given"):
            if not data.get(field):
                raise ValidationError("Please confirm all required permissions before submitting.", field_name=field)


# ---------------------------------------------------------------------------
# Admin update / action schemas — every field optional, no load_default,
# so a PATCH only ever touches keys actually present (see the Mentorship/
# Community/Submissions house rule on partial-update defaults).
# ---------------------------------------------------------------------------


class NominationUpdateSchema(ma.Schema):
    topic_slugs = fields.List(fields.String(), required=False, data_key="topicSlugs")
    series_id = fields.Integer(required=False, allow_none=True, data_key="seriesId")
    editorial_assessment = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="editorialAssessment")
    verification_state = fields.String(required=False, validate=validate.OneOf(VERIFICATION_STATES), data_key="verificationState")
    verification_notes = fields.String(required=False, allow_none=True, validate=validate.Length(max=4000), data_key="verificationNotes")
    contact_nominee_before_publication = fields.Boolean(required=False, data_key="contactNomineeBeforePublication")
    nominee_awareness = fields.String(required=False, validate=validate.OneOf(NOMINEE_AWARENESS_VALUES), data_key="nomineeAwareness")
    person_profile_needed = fields.Boolean(required=False, data_key="personProfileNeeded")
    person_id = fields.Integer(required=False, allow_none=True, data_key="personId")
    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")


class NominationStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(NOMINATION_STATUSES))


class NominationAssignInputSchema(ma.Schema):
    reviewer_id = fields.Integer(required=True, allow_none=True, data_key="reviewerId")


class NominationNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=4000))


class NominationConvertToArticleInputSchema(ma.Schema):
    """The deliberate 'Create Article Draft' handoff — see
    NominationConvertToArticleResource. Requires an existing Author since
    Article.author_id is not nullable; nominee/nominator are never
    auto-promoted to an Author identity.
    """

    author_id = fields.Integer(required=True, data_key="authorId")
