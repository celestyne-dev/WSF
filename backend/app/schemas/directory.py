from marshmallow import fields, validate

from app.extensions import ma
from app.models.directory import (
    DIRECTORY_LISTING_STATUSES,
    DIRECTORY_LISTING_TYPES,
    DIRECTORY_OWNERSHIP_CLASSIFICATIONS,
    DIRECTORY_SERVICE_MODES,
    DIRECTORY_SUBMISSION_STATUSES,
    DIRECTORY_VERIFICATION_STATUSES,
    DirectoryCategory,
    DirectoryListing,
    DirectorySubmission,
    DirectorySubmissionNote,
)
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.user import UserSchema

_STAFF_ONLY = UserSchema(only=("id", "full_name", "email"))

# A short, length-limited free-text list — see DirectoryListing.key_services'
# own docstring for why this isn't a taxonomy table.
_MAX_KEY_SERVICES = 12
_MAX_KEY_SERVICE_LENGTH = 140


class DirectoryCategorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = DirectoryCategory
        load_instance = False


class DirectoryCategoryInputSchema(ma.Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=140))
    slug = fields.String(required=False, allow_none=True, validate=validate.Length(max=140))
    status = fields.String(required=False, load_default="published", validate=validate.OneOf(("draft", "published", "archived")))
    sort_order = fields.Integer(required=False, load_default=0, data_key="sortOrder")


class DirectoryCategoryStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(("draft", "published", "archived")))


# ---------------------------------------------------------------------------
# A light, safe Organization preview — canonical identity fields only, never
# an unpublished Organization's data leaking through (guarded in the route/
# Method fields, not here — see get_organization() below).
# ---------------------------------------------------------------------------


class _OrganizationPreviewSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    slug = fields.String(dump_only=True)
    name = fields.String(dump_only=True)
    logo = fields.Nested(MediaSchema, dump_only=True)
    industry = fields.String(dump_only=True)
    location = fields.String(dump_only=True)
    founded_year = fields.Integer(dump_only=True)
    org_type = fields.String(dump_only=True)
    short_description = fields.String(dump_only=True)
    website = fields.String(dump_only=True)
    social = fields.Dict(dump_only=True)
    status = fields.String(dump_only=True)
    country = fields.Nested(CountrySchema, dump_only=True)


class DirectoryListingPublicSchema(ma.Schema):
    """Public directory card/profile shape — strictly excludes
    verification_notes, rejection_reason, reviewer/verifier identity, and
    any submitter data. Publication-gating happens in the route (only
    status == "published" listings ever reach this schema)."""

    id = fields.Integer(dump_only=True)
    organization = fields.Nested(_OrganizationPreviewSchema, dump_only=True)
    listing_type = fields.String(dump_only=True)
    ownership_classification = fields.String(dump_only=True)
    classification_provenance = fields.String(dump_only=True)
    # Only the status itself is exposed — never verification_notes/who
    # verified it — so the frontend can show a badge for "verified" only,
    # with an accessible explanation of what that actually means.
    verification_status = fields.String(dump_only=True)
    service_summary = fields.String(dump_only=True)
    key_services = fields.List(fields.String(), dump_only=True)
    service_modes = fields.List(fields.String(), dump_only=True)
    public_contact_email = fields.String(dump_only=True)
    public_contact_phone = fields.String(dump_only=True)
    categories = fields.Nested(DirectoryCategorySchema, many=True, dump_only=True, only=("id", "slug", "name"))
    is_currently_featured = fields.Boolean(dump_only=True)
    published_at = fields.DateTime(dump_only=True)
    seo = fields.Dict(dump_only=True)


class DirectoryListingAdminSchema(ma.SQLAlchemyAutoSchema):
    organization = fields.Nested(_OrganizationPreviewSchema, dump_only=True)
    categories = fields.Nested(DirectoryCategorySchema, many=True, dump_only=True)
    verified_by = fields.Nested(_STAFF_ONLY, dump_only=True)
    reviewed_by = fields.Nested(_STAFF_ONLY, dump_only=True)
    is_currently_featured = fields.Boolean(dump_only=True)

    class Meta:
        model = DirectoryListing
        load_instance = False


class DirectoryListingListItemSchema(ma.SQLAlchemyAutoSchema):
    """Lighter admin list-row shape — no verification/rejection notes text,
    matching ContactInquiryListItemSchema's convention."""

    organization = fields.Nested(_OrganizationPreviewSchema, dump_only=True)
    categories = fields.Nested(DirectoryCategorySchema, many=True, dump_only=True, only=("id", "slug", "name"))
    is_currently_featured = fields.Boolean(dump_only=True)

    class Meta:
        model = DirectoryListing
        load_instance = False
        exclude = ("verification_notes", "rejection_reason", "seo")


def _key_services_field():
    return fields.List(
        fields.String(validate=validate.Length(min=1, max=_MAX_KEY_SERVICE_LENGTH)),
        required=False,
        load_default=list,
        validate=validate.Length(max=_MAX_KEY_SERVICES),
        data_key="keyServices",
    )


def _service_modes_field():
    return fields.List(
        fields.String(validate=validate.OneOf(DIRECTORY_SERVICE_MODES)),
        required=False,
        load_default=list,
        data_key="serviceModes",
    )


class DirectoryListingCreateSchema(ma.Schema):
    """Admin-only: attach an existing Organization to the directory
    directly (independent of the public submission flow)."""

    organization_id = fields.Integer(required=True, data_key="organizationId")
    listing_type = fields.String(required=False, load_default="business", validate=validate.OneOf(DIRECTORY_LISTING_TYPES), data_key="listingType")
    ownership_classification = fields.String(
        required=False, load_default="unspecified", validate=validate.OneOf(DIRECTORY_OWNERSHIP_CLASSIFICATIONS), data_key="ownershipClassification"
    )
    service_summary = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="serviceSummary")
    key_services = _key_services_field()
    service_modes = _service_modes_field()
    category_ids = fields.List(fields.Integer(), required=False, load_default=list, data_key="categoryIds")
    public_contact_email = fields.Email(required=False, allow_none=True, data_key="publicContactEmail")
    public_contact_phone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50), data_key="publicContactPhone")
    seo = fields.Dict(required=False, allow_none=True)


class DirectoryListingUpdateSchema(ma.Schema):
    """Editable listing fields — status, verification, and featured all
    move through their own dedicated actions (see the *Input schemas below)
    so each carries its own audit-log action name, per spec."""

    listing_type = fields.String(required=False, validate=validate.OneOf(DIRECTORY_LISTING_TYPES), data_key="listingType")
    ownership_classification = fields.String(
        required=False, validate=validate.OneOf(DIRECTORY_OWNERSHIP_CLASSIFICATIONS), data_key="ownershipClassification"
    )
    classification_provenance = fields.String(
        required=False, validate=validate.OneOf(("self_attested", "staff_reviewed")), data_key="classificationProvenance"
    )
    service_summary = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="serviceSummary")
    key_services = _key_services_field()
    service_modes = _service_modes_field()
    category_ids = fields.List(fields.Integer(), required=False, data_key="categoryIds")
    public_contact_email = fields.Email(required=False, allow_none=True, data_key="publicContactEmail")
    public_contact_phone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50), data_key="publicContactPhone")
    seo = fields.Dict(required=False, allow_none=True)


class DirectoryListingStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(DIRECTORY_LISTING_STATUSES))
    rejection_reason = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="rejectionReason")


class DirectoryListingVerificationInputSchema(ma.Schema):
    verification_status = fields.String(required=True, validate=validate.OneOf(DIRECTORY_VERIFICATION_STATUSES), data_key="verificationStatus")
    verification_notes = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="verificationNotes")


class DirectoryListingFeaturedInputSchema(ma.Schema):
    featured = fields.Boolean(required=True)
    featured_start_at = fields.DateTime(required=False, allow_none=True, data_key="featuredStartAt")
    featured_end_at = fields.DateTime(required=False, allow_none=True, data_key="featuredEndAt")


# ---------------------------------------------------------------------------
# Public submission
# ---------------------------------------------------------------------------


class DirectorySubmissionInputSchema(ma.Schema):
    business_name = fields.String(required=True, validate=validate.Length(min=1, max=200), data_key="businessName")
    website = fields.String(required=False, allow_none=True, validate=validate.URL(require_tld=True))
    listing_type = fields.String(required=False, load_default="business", validate=validate.OneOf(DIRECTORY_LISTING_TYPES), data_key="listingType")
    ownership_classification = fields.String(
        required=False, load_default="unspecified", validate=validate.OneOf(DIRECTORY_OWNERSHIP_CLASSIFICATIONS), data_key="ownershipClassification"
    )
    country_code = fields.String(required=False, allow_none=True, data_key="countryCode")
    location = fields.String(required=False, allow_none=True, validate=validate.Length(max=200))
    description = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000))
    key_services = _key_services_field()
    service_modes = _service_modes_field()
    category_ids = fields.List(fields.Integer(), required=False, load_default=list, data_key="categoryIds")
    public_contact_email = fields.Email(required=False, allow_none=True, data_key="publicContactEmail")
    public_contact_phone = fields.String(required=False, allow_none=True, validate=validate.Length(max=50), data_key="publicContactPhone")

    submitter_name = fields.String(required=True, validate=validate.Length(min=1, max=200), data_key="submitterName")
    submitter_email = fields.Email(required=True, data_key="submitterEmail")
    submitter_role = fields.String(required=False, allow_none=True, validate=validate.Length(max=120), data_key="submitterRole")

    # Anti-spam signals — never persisted, never returned (same pattern as
    # ContactInquiryInputSchema).
    hp_website = fields.String(required=False, allow_none=True, load_default="", data_key="hpWebsite")
    elapsed_ms = fields.Integer(required=False, allow_none=True, load_default=None, data_key="elapsedMs")


class DirectorySubmissionNoteSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(_STAFF_ONLY, dump_only=True)

    class Meta:
        model = DirectorySubmissionNote
        load_instance = False
        exclude = ("submission_id", "user_id")


class DirectorySubmissionSchema(ma.SQLAlchemyAutoSchema):
    """Full admin detail dump — submitter identity, rejection reason, and
    duplicate/match links included. Staff-only; never used for the public
    create response (the route builds its own small {reference, status}
    confirmation by hand)."""

    country = fields.Nested(CountrySchema, dump_only=True)
    possible_duplicate_organization = fields.Nested(_OrganizationPreviewSchema, dump_only=True)
    matched_organization = fields.Nested(_OrganizationPreviewSchema, dump_only=True)
    reviewed_by = fields.Nested(_STAFF_ONLY, dump_only=True)
    notes = fields.Nested(DirectorySubmissionNoteSchema, many=True, dump_only=True)
    # Resolved on demand from category_ids (a plain JSON list, not a join
    # table — submissions are pre-review claims, not yet a real taxonomy
    # relationship) so the admin UI can show readable category names.
    categories = fields.Method("get_categories", dump_only=True)

    class Meta:
        model = DirectorySubmission
        load_instance = False

    def get_categories(self, obj):
        ids = obj.category_ids or []
        if not ids:
            return []
        rows = DirectoryCategory.query.filter(DirectoryCategory.id.in_(ids)).all()
        return DirectoryCategorySchema(many=True, only=("id", "slug", "name")).dump(rows)


class DirectorySubmissionListItemSchema(ma.SQLAlchemyAutoSchema):
    """Lighter list-row shape — no description/notes for every row on a
    page, matching ContactInquiryListItemSchema's convention."""

    country = fields.Nested(CountrySchema, dump_only=True)

    class Meta:
        model = DirectorySubmission
        load_instance = False
        exclude = ("description", "key_services", "service_modes", "category_ids")


class DirectorySubmissionStatusInputSchema(ma.Schema):
    status = fields.String(required=True, validate=validate.OneOf(DIRECTORY_SUBMISSION_STATUSES))
    rejection_reason = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000), data_key="rejectionReason")


class DirectorySubmissionConvertInputSchema(ma.Schema):
    """Staff decision on how to turn a submission into a live listing:
    link to an existing Organization (organization_id — typically the
    flagged possible duplicate, but any Organization may be chosen) or
    leave it unset to create a brand-new Organization from the
    submission's own fields."""

    organization_id = fields.Integer(required=False, allow_none=True, data_key="organizationId")


class DirectorySubmissionNoteInputSchema(ma.Schema):
    body = fields.String(required=True, validate=validate.Length(min=1, max=4000))
