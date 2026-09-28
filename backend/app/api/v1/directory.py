"""Business & Professional Directory — public browse/submit + authorized
CMS review/publish/feature workflow. See app/models/directory.py for the
full architecture rationale (DirectoryListing as a publication/
verification/commercial layer on top of Organization; DirectorySubmission
as the separate, never-auto-publishing public intake model).

Deliberately narrow, matching this task's explicit scope: no payments, no
business-owner login/claim workflow, no reviews/ratings, no maps. See the
module docstrings in app/models/directory.py and app/services/directory.py
for the reasoning behind each boundary.
"""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import cast
from sqlalchemy.dialects.postgresql import JSONB

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.directory import (
    DirectoryCategory,
    DirectoryListing,
    DirectorySubmission,
    DirectorySubmissionNote,
    directory_listing_categories,
)
from app.models.people import ORGANIZATION_TYPES, Organization
from app.schemas.directory import (
    DirectoryCategoryInputSchema,
    DirectoryCategorySchema,
    DirectoryCategoryStatusInputSchema,
    DirectoryListingAdminSchema,
    DirectoryListingCreateSchema,
    DirectoryListingFeaturedInputSchema,
    DirectoryListingListItemSchema,
    DirectoryListingPublicSchema,
    DirectoryListingStatusInputSchema,
    DirectoryListingUpdateSchema,
    DirectoryListingVerificationInputSchema,
    DirectorySubmissionConvertInputSchema,
    DirectorySubmissionInputSchema,
    DirectorySubmissionListItemSchema,
    DirectorySubmissionNoteInputSchema,
    DirectorySubmissionSchema,
    DirectorySubmissionStatusInputSchema,
)
from app.services.audit import log_action
from app.services.directory import (
    find_duplicate_organization,
    find_duplicate_submission,
    generate_submission_reference,
    is_valid_listing_status_transition,
    normalize_business_name,
    normalize_website_domain,
)
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

directory_bp = Blueprint("directory", __name__)
api = Api(directory_bp)

listing_public_schema = DirectoryListingPublicSchema()
listing_admin_schema = DirectoryListingAdminSchema()
listing_list_schema = DirectoryListingListItemSchema()
category_schema = DirectoryCategorySchema()
submission_schema = DirectorySubmissionSchema()
submission_list_schema = DirectorySubmissionListItemSchema()

# A submitted listing_type maps onto the closest existing Organization
# org_type when staff convert a submission into a brand-new Organization —
# never onto an invented new org_type value (see ORGANIZATION_TYPES).
_LISTING_TYPE_TO_ORG_TYPE = {
    "business": "company",
    "nonprofit": "nonprofit",
    "professional_service": "professional_association",
    "social_enterprise": "social_enterprise",
    "association": "professional_association",
}

_MIN_HUMAN_SUBMIT_MS = 1500


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _can_manage_or_none():
    """Best-effort permission check that never raises — mirrors
    organizations.py's _can_edit_or_none, deciding whether a public-facing
    GET should widen to every status."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    if current_user.has_permission("directory.manage"):
        return current_user
    return None


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("directory.manage"):
        raise ApiError("You do not have permission to manage the directory.", 403, code="forbidden")
    return user


def _require_taxonomy_manage():
    user = _require_active_user()
    if not user.has_permission("taxonomy.manage"):
        raise ApiError("You do not have permission to manage directory categories.", 403, code="forbidden")
    return user


def _looks_like_spam(data):
    if (data.get("hp_website") or "").strip():
        return True
    elapsed = data.get("elapsed_ms")
    if elapsed is not None and elapsed < _MIN_HUMAN_SUBMIT_MS:
        return True
    return False


def _resolve_categories(category_ids):
    if not category_ids:
        return []
    rows = DirectoryCategory.query.filter(DirectoryCategory.id.in_(category_ids)).all()
    return rows


def _apply_listing_editable_fields(listing, data):
    if "listing_type" in data:
        listing.listing_type = data["listing_type"]
    if "ownership_classification" in data:
        listing.ownership_classification = data["ownership_classification"]
    if "classification_provenance" in data:
        listing.classification_provenance = data["classification_provenance"]
    if "service_summary" in data:
        listing.service_summary = data["service_summary"]
    if "key_services" in data:
        listing.key_services = data["key_services"]
    if "service_modes" in data:
        listing.service_modes = data["service_modes"]
    if "public_contact_email" in data:
        listing.public_contact_email = data["public_contact_email"]
    if "public_contact_phone" in data:
        listing.public_contact_phone = data["public_contact_phone"]
    if "seo" in data:
        listing.seo = data["seo"]
    if "category_ids" in data:
        listing.categories = _resolve_categories(data["category_ids"])


def _dump_public_listing(listing):
    return listing_public_schema.dump(listing)


# ---------------------------------------------------------------------------
# Public directory
# ---------------------------------------------------------------------------


class DirectoryListingPublicListResource(Resource):
    def get(self):
        query = (
            DirectoryListing.query.join(Organization, DirectoryListing.organization_id == Organization.id)
            .filter(DirectoryListing.status == "published", Organization.status == "published")
        )

        args = request.args
        if args.get("category"):
            query = query.filter(
                DirectoryListing.categories.any(DirectoryCategory.slug == args["category"])
            )
        if args.get("classification"):
            query = query.filter(DirectoryListing.ownership_classification == args["classification"])
        if args.get("listing_type"):
            query = query.filter(DirectoryListing.listing_type == args["listing_type"])
        if args.get("remote") in ("true", "1"):
            query = query.filter(cast(DirectoryListing.service_modes, JSONB).contains(["remote"]))
        query = apply_country_or_region_filter(query, Organization, args)
        query = apply_search(query, Organization, args, ["name"], param="q")

        sort = args.get("sort", "featured")
        if sort == "alphabetical":
            query = query.order_by(Organization.name.asc())
        elif sort == "newest":
            query = query.order_by(DirectoryListing.published_at.desc().nullslast())
        else:
            # Default: featured-first (transparent, no fake popularity
            # score), then newest — matches the featured-window semantics
            # of is_currently_featured rather than the raw `featured` flag.
            query = query.order_by(DirectoryListing.featured.desc(), DirectoryListing.published_at.desc().nullslast())

        result = paginate(query, listing_public_schema)
        return success_response(result["items"], meta=result["meta"])


class DirectoryCategoryPublicListResource(Resource):
    def get(self):
        rows = DirectoryCategory.query.filter_by(status="published").order_by(
            DirectoryCategory.sort_order, DirectoryCategory.name
        ).all()
        return success_response(category_schema.dump(rows, many=True))


class DirectoryListingPublicDetailResource(Resource):
    def get(self, org_slug):
        organization = Organization.query.filter_by(slug=org_slug).first()
        if organization is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")
        listing = DirectoryListing.query.filter_by(organization_id=organization.id).first()
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")
        if (listing.status != "published" or organization.status != "published") and not _can_manage_or_none():
            raise ApiError("Directory listing not found.", 404, code="not_found")
        return success_response(_dump_public_listing(listing))


class DirectorySubmissionCreateResource(Resource):
    def post(self):
        payload = request.get_json(silent=True) or {}
        data = DirectorySubmissionInputSchema().load(payload)

        if _looks_like_spam(data):
            # A believable-looking confirmation, but nothing is persisted —
            # a bot never learns it was caught (see contact.py's identical
            # pattern).
            return success_response({"reference": "WSF-DIR-0000-000000", "status": "received"}, status=201)

        data.pop("hp_website", None)
        data.pop("elapsed_ms", None)

        duplicate_submission = find_duplicate_submission(data["business_name"], data.get("website"))
        if duplicate_submission is not None:
            return success_response({"reference": duplicate_submission.reference, "status": "received"}, status=201)

        possible_duplicate = find_duplicate_organization(data["business_name"], data.get("website"))

        submission = DirectorySubmission(
            business_name=data["business_name"],
            business_name_normalized=normalize_business_name(data["business_name"]),
            website=data.get("website"),
            website_domain=normalize_website_domain(data.get("website")),
            listing_type=data["listing_type"],
            ownership_classification=data["ownership_classification"],
            country_code=data.get("country_code"),
            location=data.get("location"),
            description=data.get("description"),
            key_services=data["key_services"],
            service_modes=data["service_modes"],
            category_ids=data["category_ids"],
            public_contact_email=data.get("public_contact_email"),
            public_contact_phone=data.get("public_contact_phone"),
            submitter_name=data["submitter_name"],
            submitter_email=data["submitter_email"].strip().lower(),
            submitter_role=data.get("submitter_role"),
            possible_duplicate_organization_id=possible_duplicate.id if possible_duplicate else None,
            status="new",
        )
        db.session.add(submission)
        db.session.flush()
        submission.reference = generate_submission_reference(submission)
        db.session.commit()

        log_action(None, "directory.submission_received", "DirectorySubmission", submission.id, {"reference": submission.reference})
        return success_response({"reference": submission.reference, "status": "received"}, status=201)


# ---------------------------------------------------------------------------
# Admin: listings
# ---------------------------------------------------------------------------


class AdminDirectoryListingListResource(Resource):
    @permission_required("directory.manage")
    def get(self):
        query = DirectoryListing.query.join(Organization, DirectoryListing.organization_id == Organization.id)
        args = request.args
        query = apply_equality_filters(query, DirectoryListing, args, ["status", "verification_status", "listing_type", "ownership_classification"])
        if args.get("featured") in ("true", "1"):
            query = query.filter(DirectoryListing.featured.is_(True))
        query = apply_country_or_region_filter(query, Organization, args)
        query = apply_search(query, Organization, args, ["name"], param="q")
        query = query.order_by(DirectoryListing.created_at.desc())
        result = paginate(query, listing_list_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("directory.manage")
    def post(self):
        data = DirectoryListingCreateSchema().load(request.get_json(silent=True) or {})
        organization = db.session.get(Organization, data["organization_id"])
        if organization is None:
            raise ApiError("That organization could not be found.", 422, code="invalid_organization")
        if DirectoryListing.query.filter_by(organization_id=organization.id).first() is not None:
            raise ApiError("This organization already has a directory listing.", 409, code="already_listed")

        listing = DirectoryListing(organization_id=organization.id, status="pending")
        _apply_listing_editable_fields(listing, data)
        db.session.add(listing)
        db.session.commit()

        log_action(
            current_user, "directory.organization_linked", "DirectoryListing", listing.id,
            {"organization_id": organization.id, "organization_slug": organization.slug},
        )
        return success_response(listing_admin_schema.dump(listing), status=201)


class AdminDirectoryListingDetailResource(Resource):
    @permission_required("directory.manage")
    def get(self, listing_id):
        listing = db.session.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")
        return success_response(listing_admin_schema.dump(listing))

    @permission_required("directory.manage")
    def put(self, listing_id):
        listing = db.session.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")
        data = DirectoryListingUpdateSchema().load(request.get_json(silent=True) or {})
        _apply_listing_editable_fields(listing, data)
        db.session.commit()
        return success_response(listing_admin_schema.dump(listing))

    @permission_required("directory.manage")
    def delete(self, listing_id):
        listing = db.session.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")

        # Deleting a listing must never delete the Organization it points
        # to — only detach the directory-specific configuration. Archiving
        # (status: "archived") is the safer default; this hard delete
        # exists for genuine mistakes (e.g. linked to the wrong org).
        DirectorySubmission.query.filter_by(resulting_listing_id=listing.id).update({"resulting_listing_id": None})
        organization_id = listing.organization_id
        db.session.delete(listing)
        db.session.commit()

        log_action(current_user, "directory.listing_deleted", "DirectoryListing", listing_id, {"organization_id": organization_id})
        return success_response({"deleted": True})


class AdminDirectoryListingStatusResource(Resource):
    @permission_required("directory.manage")
    def patch(self, listing_id):
        listing = db.session.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")

        data = DirectoryListingStatusInputSchema().load(request.get_json(silent=True) or {})
        new_status = data["status"]

        if not is_valid_listing_status_transition(listing.status, new_status):
            raise ApiError(f"Cannot move a listing from '{listing.status}' to '{new_status}'.", 409, code="invalid_transition")
        if new_status == "rejected" and not data.get("rejection_reason"):
            raise ApiError("A rejection reason is required.", 422, code="rejection_reason_required")

        from_status = listing.status
        listing.status = new_status
        listing.rejection_reason = data.get("rejection_reason") if new_status == "rejected" else listing.rejection_reason
        listing.reviewed_by_user_id = current_user.id
        listing.reviewed_at = datetime.now(timezone.utc)
        if new_status == "published" and listing.published_at is None:
            listing.published_at = datetime.now(timezone.utc)
        db.session.commit()

        action = {
            "published": "directory.listing_published",
            "archived": "directory.listing_archived",
            "approved": "directory.listing_approved",
            "rejected": "directory.listing_rejected",
        }.get(new_status, "directory.listing_status_changed")
        log_action(current_user, action, "DirectoryListing", listing.id, {"from_status": from_status, "to_status": new_status})
        return success_response(listing_admin_schema.dump(listing))


class AdminDirectoryListingVerificationResource(Resource):
    @permission_required("directory.manage")
    def patch(self, listing_id):
        listing = db.session.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")

        data = DirectoryListingVerificationInputSchema().load(request.get_json(silent=True) or {})
        from_status = listing.verification_status
        listing.verification_status = data["verification_status"]
        listing.verification_notes = data.get("verification_notes")
        if data["verification_status"] == "verified":
            listing.verified_at = datetime.now(timezone.utc)
            listing.verified_by_user_id = current_user.id
        else:
            listing.verified_at = None
            listing.verified_by_user_id = None
        db.session.commit()

        log_action(
            current_user, "directory.verification_changed", "DirectoryListing", listing.id,
            {"from_status": from_status, "to_status": listing.verification_status},
        )
        return success_response(listing_admin_schema.dump(listing))


class AdminDirectoryListingFeaturedResource(Resource):
    @permission_required("directory.manage")
    def patch(self, listing_id):
        listing = db.session.get(DirectoryListing, listing_id)
        if listing is None:
            raise ApiError("Directory listing not found.", 404, code="not_found")

        data = DirectoryListingFeaturedInputSchema().load(request.get_json(silent=True) or {})
        listing.featured = data["featured"]
        listing.featured_start_at = data.get("featured_start_at")
        listing.featured_end_at = data.get("featured_end_at")
        db.session.commit()

        log_action(
            current_user, "directory.feature_status_changed", "DirectoryListing", listing.id,
            {
                "featured": listing.featured,
                "featured_start_at": listing.featured_start_at.isoformat() if listing.featured_start_at else None,
                "featured_end_at": listing.featured_end_at.isoformat() if listing.featured_end_at else None,
            },
        )
        return success_response(listing_admin_schema.dump(listing))


# ---------------------------------------------------------------------------
# Admin: submissions
# ---------------------------------------------------------------------------


class AdminDirectorySubmissionListResource(Resource):
    @permission_required("directory.manage")
    def get(self):
        query = DirectorySubmission.query.order_by(DirectorySubmission.created_at.desc())
        query = apply_equality_filters(query, DirectorySubmission, request.args, ["status"])
        query = apply_search(query, DirectorySubmission, request.args, ["reference", "business_name", "submitter_name", "submitter_email"], param="q")
        result = paginate(query, submission_list_schema)
        return success_response(result["items"], meta=result["meta"])


class AdminDirectorySubmissionDetailResource(Resource):
    @permission_required("directory.manage")
    def get(self, submission_id):
        submission = db.session.get(DirectorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")
        return success_response(submission_schema.dump(submission))


class AdminDirectorySubmissionStatusResource(Resource):
    @permission_required("directory.manage")
    def patch(self, submission_id):
        submission = db.session.get(DirectorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = DirectorySubmissionStatusInputSchema().load(request.get_json(silent=True) or {})
        submission.status = data["status"]
        submission.rejection_reason = data.get("rejection_reason")
        submission.reviewed_by_user_id = current_user.id
        submission.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action(
            current_user, "directory.submission_status_changed", "DirectorySubmission", submission.id,
            {"reference": submission.reference, "to_status": submission.status},
        )
        return success_response(submission_schema.dump(submission))


class AdminDirectorySubmissionConvertResource(Resource):
    @permission_required("directory.manage")
    def post(self, submission_id):
        """Turn a submission into a live (pending-review) directory
        listing — either linking to an existing Organization or creating a
        new one from the submission's own fields. Never auto-publishes:
        the resulting DirectoryListing still starts at status="pending"
        and must go through the normal review/publish workflow."""
        submission = db.session.get(DirectorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")
        if submission.status == "converted":
            raise ApiError("This submission has already been converted.", 409, code="already_converted")

        data = DirectorySubmissionConvertInputSchema().load(request.get_json(silent=True) or {})

        if data.get("organization_id"):
            organization = db.session.get(Organization, data["organization_id"])
            if organization is None:
                raise ApiError("That organization could not be found.", 422, code="invalid_organization")
        else:
            organization = Organization(
                name=submission.business_name,
                slug=generate_unique_slug(Organization, submission.business_name),
                website=submission.website,
                country_code=submission.country_code,
                location=submission.location,
                org_type=_LISTING_TYPE_TO_ORG_TYPE.get(submission.listing_type, "other"),
                short_description=submission.description,
                status="draft",
            )
            db.session.add(organization)
            db.session.flush()

        existing_listing = DirectoryListing.query.filter_by(organization_id=organization.id).first()
        if existing_listing is not None:
            listing = existing_listing
        else:
            listing = DirectoryListing(
                organization_id=organization.id,
                listing_type=submission.listing_type,
                ownership_classification=submission.ownership_classification,
                classification_provenance="self_attested",
                service_summary=submission.description,
                key_services=submission.key_services or [],
                service_modes=submission.service_modes or [],
                public_contact_email=submission.public_contact_email,
                public_contact_phone=submission.public_contact_phone,
                status="pending",
            )
            listing.categories = _resolve_categories(submission.category_ids)
            db.session.add(listing)
            db.session.flush()

        submission.status = "converted"
        submission.matched_organization_id = organization.id
        submission.resulting_listing_id = listing.id
        submission.reviewed_by_user_id = current_user.id
        submission.reviewed_at = datetime.now(timezone.utc)
        db.session.commit()

        log_action(
            current_user, "directory.organization_linked", "DirectoryListing", listing.id,
            {"organization_id": organization.id, "from_submission_reference": submission.reference},
        )
        return success_response(
            {"submission": submission_schema.dump(submission), "listing": listing_admin_schema.dump(listing)}
        )


class AdminDirectorySubmissionNoteListResource(Resource):
    @permission_required("directory.manage")
    def post(self, submission_id):
        submission = db.session.get(DirectorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = DirectorySubmissionNoteInputSchema().load(request.get_json(silent=True) or {})
        note = DirectorySubmissionNote(submission_id=submission.id, user_id=current_user.id, body=data["body"])
        db.session.add(note)
        db.session.commit()
        return success_response(submission_schema.dump(submission), status=201)


# ---------------------------------------------------------------------------
# Admin: categories (taxonomy.manage — same gate as Category/Tag/Topic/Series)
# ---------------------------------------------------------------------------


class AdminDirectoryCategoryListResource(Resource):
    @permission_required("taxonomy.manage")
    def get(self):
        query = DirectoryCategory.query.order_by(DirectoryCategory.sort_order, DirectoryCategory.name)
        if request.args.get("status"):
            query = query.filter(DirectoryCategory.status == request.args["status"])
        query = apply_search(query, DirectoryCategory, request.args, ["name"], param="q")
        result = paginate(query, category_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("taxonomy.manage")
    def post(self):
        data = DirectoryCategoryInputSchema().load(request.get_json(silent=True) or {})
        category = DirectoryCategory(name=data["name"], status=data["status"], sort_order=data["sort_order"])
        category.slug = data.get("slug") and validate_explicit_slug(DirectoryCategory, data["slug"]) or generate_unique_slug(DirectoryCategory, data["name"])
        db.session.add(category)
        db.session.commit()
        log_action(current_user, "directory.category_created", "DirectoryCategory", category.id, {"name": category.name})
        return success_response(category_schema.dump(category), status=201)


class AdminDirectoryCategoryDetailResource(Resource):
    @permission_required("taxonomy.manage")
    def put(self, category_id):
        category = db.session.get(DirectoryCategory, category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        data = DirectoryCategoryInputSchema().load(request.get_json(silent=True) or {})
        category.name = data["name"]
        category.sort_order = data["sort_order"]
        if data.get("slug") and data["slug"] != category.slug:
            category.slug = validate_explicit_slug(DirectoryCategory, data["slug"], current_id=category.id)
        db.session.commit()
        return success_response(category_schema.dump(category))

    @permission_required("taxonomy.manage")
    def delete(self, category_id):
        category = db.session.get(DirectoryCategory, category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        in_use = db.session.query(directory_listing_categories).filter(
            directory_listing_categories.c.category_id == category.id
        ).first()
        if in_use is not None:
            raise ApiError(
                "This category is assigned to one or more directory listings and can't be deleted. "
                "Remove it from those listings first, or archive it instead.",
                409,
                code="reference_conflict",
            )
        db.session.delete(category)
        db.session.commit()
        return success_response({"deleted": True})


class AdminDirectoryCategoryStatusResource(Resource):
    @permission_required("taxonomy.manage")
    def put(self, category_id):
        category = db.session.get(DirectoryCategory, category_id)
        if category is None:
            raise ApiError("Category not found.", 404, code="not_found")
        data = DirectoryCategoryStatusInputSchema().load(request.get_json(silent=True) or {})
        category.status = data["status"]
        db.session.commit()
        return success_response(category_schema.dump(category))


api.add_resource(DirectoryListingPublicListResource, "")
api.add_resource(DirectoryCategoryPublicListResource, "/categories")
api.add_resource(DirectorySubmissionCreateResource, "/submit")
api.add_resource(DirectoryListingPublicDetailResource, "/<string:org_slug>")

api.add_resource(AdminDirectoryListingListResource, "/admin/listings")
api.add_resource(AdminDirectoryListingDetailResource, "/admin/listings/<int:listing_id>")
api.add_resource(AdminDirectoryListingStatusResource, "/admin/listings/<int:listing_id>/status")
api.add_resource(AdminDirectoryListingVerificationResource, "/admin/listings/<int:listing_id>/verification")
api.add_resource(AdminDirectoryListingFeaturedResource, "/admin/listings/<int:listing_id>/featured")

api.add_resource(AdminDirectorySubmissionListResource, "/admin/submissions")
api.add_resource(AdminDirectorySubmissionDetailResource, "/admin/submissions/<int:submission_id>")
api.add_resource(AdminDirectorySubmissionStatusResource, "/admin/submissions/<int:submission_id>/status")
api.add_resource(AdminDirectorySubmissionConvertResource, "/admin/submissions/<int:submission_id>/convert")
api.add_resource(AdminDirectorySubmissionNoteListResource, "/admin/submissions/<int:submission_id>/notes")

api.add_resource(AdminDirectoryCategoryListResource, "/admin/categories")
api.add_resource(AdminDirectoryCategoryDetailResource, "/admin/categories/<int:category_id>")
api.add_resource(AdminDirectoryCategoryStatusResource, "/admin/categories/<int:category_id>/status")
