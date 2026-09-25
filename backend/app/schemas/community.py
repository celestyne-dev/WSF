from marshmallow import fields, validate, validates_schema, ValidationError

from app.extensions import ma
from app.models.community import (
    CommunityPage,
    COMMUNITY_PAGE_STATUSES,
    Member,
    MemberNote,
    MEMBERSHIP_SOURCES,
    MEMBERSHIP_STATUSES,
    MEMBERSHIP_TYPES,
)
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.people import PersonSchema
from app.schemas.taxonomy import TopicSchema
from app.schemas.user import UserSchema


# ---------------------------------------------------------------------------
# Community / Membership
# ---------------------------------------------------------------------------


class MemberNoteSchema(ma.SQLAlchemyAutoSchema):
    """Internal, staff-only — never used on any public response."""

    user = fields.Nested(UserSchema, dump_only=True, only=("id", "full_name", "email"))

    class Meta:
        model = MemberNote
        load_instance = False


class MemberSchema(ma.SQLAlchemyAutoSchema):
    """Admin-only dump — the full record. See build_public_member_payload()
    in api/v1/community.py for the public-directory-safe subset.
    """

    full_name = fields.String(dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)
    profile_image_media_id = fields.Integer(dump_only=True)
    profile_image = fields.Nested(MediaSchema, dump_only=True)
    interests = fields.Nested(TopicSchema, many=True, dump_only=True, only=("id", "slug", "name"))
    person_id = fields.Integer(dump_only=True)
    # A lightweight preview only — linking never pulls in the Person's
    # full editorial record, and never changes either record's own
    # visibility rules.
    person = fields.Nested(PersonSchema, dump_only=True, only=("id", "slug", "name", "title"))
    notes = fields.Nested(MemberNoteSchema, many=True, dump_only=True)

    class Meta:
        model = Member
        load_instance = False


class MemberJoinInputSchema(ma.Schema):
    """The public Join WSF form. No account, no membership type choice
    (that's staff-assigned), no status (server-decided).
    """

    first_name = fields.String(required=True, data_key="firstName", validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, data_key="lastName", validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)
    country_code = fields.String(required=True, data_key="countryCode")
    interest_slugs = fields.List(fields.String(), required=False, load_default=list, data_key="interestSlugs")
    consent_given = fields.Boolean(required=True, data_key="consentGiven")

    professional_title = fields.String(required=False, allow_none=True, data_key="professionalTitle", validate=validate.Length(max=200))
    organization_name = fields.String(required=False, allow_none=True, data_key="organizationName", validate=validate.Length(max=200))
    short_bio = fields.String(required=False, allow_none=True, data_key="shortBio", validate=validate.Length(max=2000))
    website_url = fields.String(required=False, allow_none=True, data_key="websiteUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    linkedin_url = fields.String(required=False, allow_none=True, data_key="linkedinUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    city = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    referral_note = fields.String(required=False, allow_none=True, data_key="referralNote", validate=validate.Length(max=300))
    # A controlled value the join page itself supplies (e.g. "Community
    # page") — never an arbitrary client-typed identifier.
    source = fields.String(required=False, allow_none=True, validate=validate.OneOf(MEMBERSHIP_SOURCES))

    # Handled by the route (calls the existing newsletter upsert service) —
    # never written onto Member as a live subscription flag.
    subscribe_newsletter = fields.Boolean(required=False, load_default=False, data_key="subscribeNewsletter")

    acquisition = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_consent(self, data, **kwargs):
        if not data.get("consent_given"):
            raise ValidationError("Please confirm we can use this information to process your request.", field_name="consent_given")


class MemberAdminUpdateSchema(ma.Schema):
    """No load_default anywhere — a key absent from a PATCH leaves that
    field untouched (see the house partial-update rule)."""

    first_name = fields.String(required=False, data_key="firstName", validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=False, data_key="lastName", validate=validate.Length(min=1, max=100))
    email = fields.Email(required=False)
    professional_title = fields.String(required=False, allow_none=True, data_key="professionalTitle", validate=validate.Length(max=200))
    organization_name = fields.String(required=False, allow_none=True, data_key="organizationName", validate=validate.Length(max=200))
    short_bio = fields.String(required=False, allow_none=True, data_key="shortBio", validate=validate.Length(max=2000))
    website_url = fields.String(required=False, allow_none=True, data_key="websiteUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    linkedin_url = fields.String(required=False, allow_none=True, data_key="linkedinUrl", validate=validate.URL(require_tld=True, schemes={"http", "https"}))
    city = fields.String(required=False, allow_none=True, validate=validate.Length(max=120))
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    membership_type = fields.String(required=False, data_key="membershipType", validate=validate.OneOf(MEMBERSHIP_TYPES))
    interest_slugs = fields.List(fields.String(), required=False, data_key="interestSlugs")
    referral_note = fields.String(required=False, allow_none=True, data_key="referralNote", validate=validate.Length(max=300))
    source = fields.String(required=False, allow_none=True, validate=validate.OneOf(MEMBERSHIP_SOURCES))
    community_updates_opt_in = fields.Boolean(required=False, data_key="communityUpdatesOptIn")
    directory_opt_in = fields.Boolean(required=False, data_key="directoryOptIn")
    admin_tags = fields.List(fields.String(), required=False, allow_none=True, data_key="adminTags")
    person_id = fields.Integer(required=False, allow_none=True, data_key="personId")
    profile_image_media_id = fields.Integer(required=False, allow_none=True, data_key="profileImageMediaId")


class MemberStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(MEMBERSHIP_STATUSES))


class MemberNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=2000))


class CommunityPageSchema(ma.SQLAlchemyAutoSchema):
    hero_media_id = fields.Integer(dump_only=True)
    hero_media = fields.Nested(MediaSchema, dump_only=True)

    class Meta:
        model = CommunityPage
        load_instance = False


class CommunityPageInputSchema(ma.Schema):
    """Shared field set for the general PATCH — `status` is deliberately
    excluded (dedicated /status action, so publishing is always a
    conscious step).
    """

    hero_heading = fields.String(required=False, allow_none=True, data_key="heroHeading", validate=validate.Length(max=200))
    hero_description = fields.String(required=False, allow_none=True, data_key="heroDescription")
    hero_media_id = fields.Integer(required=False, allow_none=True, data_key="heroMediaId")
    intro_content = fields.List(fields.Dict(), required=False, data_key="introContent")
    benefits = fields.List(fields.Dict(), required=False)
    who_for_text = fields.String(required=False, allow_none=True, data_key="whoForText")
    how_to_join_text = fields.String(required=False, allow_none=True, data_key="howToJoinText")
    cta_heading = fields.String(required=False, allow_none=True, data_key="ctaHeading", validate=validate.Length(max=200))
    cta_description = fields.String(required=False, allow_none=True, data_key="ctaDescription")
    cta_button_label = fields.String(required=False, allow_none=True, data_key="ctaButtonLabel", validate=validate.Length(max=50))
    faq = fields.List(fields.Dict(), required=False)
    seo = fields.Dict(required=False, allow_none=True)

    @validates_schema
    def validate_benefits(self, data, **kwargs):
        for entry in data.get("benefits") or []:
            if not isinstance(entry, dict) or not entry.get("title"):
                raise ValidationError("Each benefit needs a title.", field_name="benefits")

    @validates_schema
    def validate_faq(self, data, **kwargs):
        for entry in data.get("faq") or []:
            if not isinstance(entry, dict) or not entry.get("question") or not entry.get("answer"):
                raise ValidationError("Each FAQ entry needs a question and an answer.", field_name="faq")


class CommunityPageStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(COMMUNITY_PAGE_STATUSES))
