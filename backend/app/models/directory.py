"""Business & Professional Directory — a directory-specific publication,
verification, and promotion layer sitting on top of Organization
(app/models/people.py). Organization stays the single source of truth for
canonical identity (name, logo, website, geography, description);
DirectoryListing never duplicates those fields, only links to them via a
1:1 organization_id FK (the public route reuses Organization.slug — no
separate slug needed).

Deliberately a dedicated model rather than new columns on Organization:
Directory has a genuinely distinct review lifecycle (pending ->
under_review -> approved -> published -> rejected -> archived, vs.
Organization's simple draft/published/archived), a genuinely distinct
internal-verification concept, and a genuinely distinct commercial/
featured-placement concept — none of which every Organization should
carry (most Organizations in this CMS are People/Jobs/Article affiliations
with no interest in appearing in a public business directory at all).

DirectorySubmission is the separate public-intake model: a visitor's claim
about a business, held for staff triage before any Organization or
DirectoryListing is created or linked — see app/services/directory.py and
app/api/v1/directory.py for the matching/duplicate-detection workflow.
"""
from app.extensions import db
from app.models.taxonomy import TAXONOMY_STATUSES, _TAXONOMY_STATUS_CHECK_SQL  # noqa: F401 (shared taxonomy status vocabulary)

DIRECTORY_LISTING_TYPES = ("business", "nonprofit", "professional_service", "social_enterprise", "association")
_DIRECTORY_LISTING_TYPE_CHECK_SQL = "listing_type IN (" + ", ".join(f"'{t}'" for t in DIRECTORY_LISTING_TYPES) + ")"

# An explicit, controlled ownership/leadership claim — NEVER inferred from
# name, description, industry, or any other field. "unspecified" is the
# honest default when no claim has been made.
DIRECTORY_OWNERSHIP_CLASSIFICATIONS = ("women_owned", "women_led", "women_founded", "women_focused", "unspecified")
_DIRECTORY_OWNERSHIP_CHECK_SQL = (
    "ownership_classification IN (" + ", ".join(f"'{c}'" for c in DIRECTORY_OWNERSHIP_CLASSIFICATIONS) + ")"
)

# Provenance of the ownership claim above — tracked so a submitter's own
# unverified claim is never silently presented as an independent WSF
# finding. self_attested: the business/submitter said so. staff_reviewed:
# a WSF staff member looked at supporting information and judged the claim
# consistent (still not a legal/government certification).
DIRECTORY_CLASSIFICATION_PROVENANCES = ("self_attested", "staff_reviewed")
_DIRECTORY_CLASSIFICATION_PROVENANCE_CHECK_SQL = (
    "classification_provenance IN (" + ", ".join(f"'{p}'" for p in DIRECTORY_CLASSIFICATION_PROVENANCES) + ")"
)

# Internal WSF review status of the LISTING itself — never a government,
# legal, or financial audit, and never implied by mere publication.
# unverified: no review performed. self_attested: submitter made claims,
# not reviewed by staff. reviewed: a staff member looked it over for
# plausibility. verified: staff checked the listing against real
# supporting information (e.g. a matching public website/registration) —
# still only an internal WSF check, labeled as such everywhere it's shown.
DIRECTORY_VERIFICATION_STATUSES = ("unverified", "self_attested", "reviewed", "verified")
_DIRECTORY_VERIFICATION_STATUS_CHECK_SQL = (
    "verification_status IN (" + ", ".join(f"'{s}'" for s in DIRECTORY_VERIFICATION_STATUSES) + ")"
)

# Publication lifecycle — distinct from Organization.status. Only
# "published" is ever publicly visible (see the public query in
# app/api/v1/directory.py).
DIRECTORY_LISTING_STATUSES = ("pending", "under_review", "approved", "published", "rejected", "archived")
_DIRECTORY_LISTING_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in DIRECTORY_LISTING_STATUSES) + ")"

# How the business actually serves customers — a factual delivery-mode
# claim, never an inferred "availability" or coverage promise.
DIRECTORY_SERVICE_MODES = ("local", "national", "international", "remote", "online", "in_person")

DIRECTORY_SUBMISSION_STATUSES = ("new", "matched", "duplicate", "converted", "rejected")
_DIRECTORY_SUBMISSION_STATUS_CHECK_SQL = (
    "status IN (" + ", ".join(f"'{s}'" for s in DIRECTORY_SUBMISSION_STATUSES) + ")"
)


class DirectoryCategory(db.Model):
    """A narrowly-scoped, directory-only taxonomy — deliberately NOT the
    shared editorial Tag pool (Article/Resource) or Category (documented as
    Article-exclusive in app/models/taxonomy.py), to avoid confusing
    editorial topics with business-directory categories. Mirrors Tag's
    minimal shape plus sort_order (curated, not a free-for-all tag cloud).
    """

    __tablename__ = "directory_categories"
    __table_args__ = (db.CheckConstraint(_TAXONOMY_STATUS_CHECK_SQL, name="ck_directory_categories_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="published")
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )


directory_listing_categories = db.Table(
    "directory_listing_categories",
    db.Column("listing_id", db.Integer, db.ForeignKey("directory_listings.id", ondelete="CASCADE"), primary_key=True),
    db.Column(
        "category_id", db.Integer, db.ForeignKey("directory_categories.id", ondelete="CASCADE"), primary_key=True
    ),
)


class DirectoryListing(db.Model):
    """The directory-specific configuration for one Organization: whether
    and how it appears in the public Business & Professional Directory.
    Organization owns canonical identity (name/logo/website/social/
    geography/description); this model owns everything directory-specific
    (status, verification, classification, categories, service summary,
    featured window). One Organization has at most one DirectoryListing.
    """

    __tablename__ = "directory_listings"
    __table_args__ = (
        db.CheckConstraint(_DIRECTORY_LISTING_TYPE_CHECK_SQL, name="ck_directory_listings_listing_type"),
        db.CheckConstraint(_DIRECTORY_OWNERSHIP_CHECK_SQL, name="ck_directory_listings_ownership_classification"),
        db.CheckConstraint(
            _DIRECTORY_CLASSIFICATION_PROVENANCE_CHECK_SQL, name="ck_directory_listings_classification_provenance"
        ),
        db.CheckConstraint(_DIRECTORY_VERIFICATION_STATUS_CHECK_SQL, name="ck_directory_listings_verification_status"),
        db.CheckConstraint(_DIRECTORY_LISTING_STATUS_CHECK_SQL, name="ck_directory_listings_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(
        db.Integer, db.ForeignKey("organizations.id"), unique=True, nullable=False, index=True
    )

    listing_type = db.Column(db.String(30), nullable=False, default="business")

    ownership_classification = db.Column(db.String(20), nullable=False, default="unspecified")
    classification_provenance = db.Column(db.String(20), nullable=False, default="self_attested")

    verification_status = db.Column(db.String(20), nullable=False, default="unverified", index=True)
    # Staff-only — never returned by any public schema.
    verification_notes = db.Column(db.Text)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    # Staff-only — never returned by any public schema (spec: private
    # rejection reason, no public exposure).
    rejection_reason = db.Column(db.Text)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # A short, directory-specific summary of what the business offers —
    # deliberately separate from Organization.short_description/description
    # (see module docstring's ownership boundary).
    service_summary = db.Column(db.Text)
    key_services = db.Column(db.JSON, nullable=False, default=list)  # list[str], length-limited at the schema layer
    service_modes = db.Column(db.JSON, nullable=False, default=list)  # list[str] from DIRECTORY_SERVICE_MODES

    # Deliberate opt-in public business contact — distinct from the private
    # submitter contact captured on DirectorySubmission, never populated
    # automatically from it.
    public_contact_email = db.Column(db.String(255), nullable=True)
    public_contact_phone = db.Column(db.String(50), nullable=True)

    # Commercial placement — deliberately minimal (no Sponsor FK, no tier,
    # no pricing/billing of any kind; see module docstring and the task's
    # explicit "no payment infrastructure" scope). Expiry is computed from
    # these two timestamps (see is_currently_featured), never staff-tracked
    # by hand.
    featured = db.Column(db.Boolean, nullable=False, default=False)
    featured_start_at = db.Column(db.DateTime(timezone=True), nullable=True)
    featured_end_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Only meaningful while this page remains the directory-specific
    # canonical page (see DirectoryProfilePage's own distinct content
    # angle) — optional per-listing SEO override, same {title, description,
    # ogImageMediaId, canonical, robots} shape used elsewhere.
    seo = db.Column(db.JSON)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    organization = db.relationship("Organization", foreign_keys=[organization_id])
    verified_by = db.relationship("User", foreign_keys=[verified_by_user_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_user_id])
    categories = db.relationship("DirectoryCategory", secondary=directory_listing_categories, order_by="DirectoryCategory.name")

    @property
    def is_currently_featured(self):
        """Automatic expiry — never a staff-remembered flag. `featured`
        alone means "eligible"; the window (if set) decides whether it's
        active right now. No window set means always-active while
        `featured` is True.
        """
        if not self.featured:
            return False
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        if self.featured_start_at and now < self.featured_start_at:
            return False
        if self.featured_end_at and now > self.featured_end_at:
            return False
        return True


class DirectorySubmission(db.Model):
    """A public visitor's claim about a business, held for staff triage —
    never auto-published, never auto-creates or edits an Organization or
    DirectoryListing on its own. Staff either link it to an existing
    Organization (possible duplicate) or create a new one, then build the
    DirectoryListing from it (see app/services/directory.py).
    """

    __tablename__ = "directory_submissions"
    __table_args__ = (db.CheckConstraint(_DIRECTORY_SUBMISSION_STATUS_CHECK_SQL, name="ck_directory_submissions_status"),)

    id = db.Column(db.Integer, primary_key=True)
    # Human-friendly, unique, immutable — e.g. "WSF-DIR-2026-000123".
    # Generated once via app/services/directory.py:generate_submission_reference
    # right after the row has an id (never count()+1 — see Order/Contact).
    reference = db.Column(db.String(30), unique=True, nullable=True, index=True)

    status = db.Column(db.String(20), nullable=False, default="new", index=True)

    business_name = db.Column(db.String(200), nullable=False)
    # Normalized (lowercased, punctuation-stripped) — duplicate-detection
    # signal only, never shown publicly or used to auto-merge.
    business_name_normalized = db.Column(db.String(200), nullable=False, index=True)
    website = db.Column(db.String(300), nullable=True)
    # Normalized registrable domain (e.g. "example.com") — duplicate-
    # detection signal only.
    website_domain = db.Column(db.String(255), nullable=True, index=True)

    listing_type = db.Column(db.String(30), nullable=False, default="business")
    ownership_classification = db.Column(db.String(20), nullable=False, default="unspecified")
    # A submission's classification is always self_attested by definition —
    # no classification_provenance column needed here (see
    # DirectoryListing.classification_provenance for the post-review value).

    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    location = db.Column(db.String(200))

    description = db.Column(db.Text)  # short plain-text pitch, not block content — this is an unreviewed claim
    key_services = db.Column(db.JSON, nullable=False, default=list)
    service_modes = db.Column(db.JSON, nullable=False, default=list)
    category_ids = db.Column(db.JSON, nullable=False, default=list)  # requested DirectoryCategory ids, staff-adjustable

    # Deliberate opt-in public business contact, separate from the
    # submitter's own private contact below.
    public_contact_email = db.Column(db.String(255), nullable=True)
    public_contact_phone = db.Column(db.String(50), nullable=True)

    # The submitter's own private contact/role — staff-only, never returned
    # by any public schema, never copied into public_contact_* above.
    submitter_name = db.Column(db.String(200), nullable=False)
    submitter_email = db.Column(db.String(255), nullable=False)
    submitter_role = db.Column(db.String(120), nullable=True)

    # A same-name/same-domain match found at submission time, presented to
    # admins for a decision — never auto-merged (see
    # app/services/directory.py:find_duplicate_organization).
    possible_duplicate_organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)

    matched_organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    resulting_listing_id = db.Column(db.Integer, db.ForeignKey("directory_listings.id"), nullable=True)

    reviewed_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Staff-only — never returned by any public schema.
    rejection_reason = db.Column(db.Text)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False, index=True)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    country = db.relationship("Country", foreign_keys=[country_code])
    possible_duplicate_organization = db.relationship("Organization", foreign_keys=[possible_duplicate_organization_id])
    matched_organization = db.relationship("Organization", foreign_keys=[matched_organization_id])
    resulting_listing = db.relationship("DirectoryListing", foreign_keys=[resulting_listing_id])
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_user_id])
    notes = db.relationship(
        "DirectorySubmissionNote", backref="submission", cascade="all, delete-orphan", order_by="DirectorySubmissionNote.created_at"
    )


class DirectorySubmissionNote(db.Model):
    """An internal, staff-only note on a directory submission — never
    returned by any public response. Same append-only pattern as
    ContactNote/SubmissionNote/PartnershipNote.
    """

    __tablename__ = "directory_submission_notes"

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(
        db.Integer, db.ForeignKey("directory_submissions.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
