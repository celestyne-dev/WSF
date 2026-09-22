from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.opportunity import Job, Opportunity
from app.models.people import Organization, Person
from app.models.taxonomy import Series
from app.schemas.people import OrganizationInputSchema, OrganizationSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

organizations_bp = Blueprint("organizations", __name__)
api = Api(organizations_bp)
organization_schema = OrganizationSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _can_edit_or_none():
    """Mirrors PersonListResource/AuthorListResource's pattern: a
    best-effort permission check that never raises, used to decide
    whether a GET should include draft/archived Organizations and, for
    detail, whether an unpublished Organization 404s for the public
    exactly like a nonexistent slug.
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    if current_user.has_permission("people.manage"):
        return current_user
    return None


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("people.manage"):
        raise ApiError("You do not have permission to manage organizations.", 403, code="forbidden")
    return user


def _apply_fields(organization, data):
    organization.name = data["name"]
    organization.logo_media_id = data.get("logo_media_id")
    organization.industry = data.get("industry")
    organization.country_code = data.get("country_code")
    organization.location = data.get("location")
    organization.founded_year = data.get("founded_year")
    organization.org_type = data.get("org_type")
    organization.short_description = data.get("short_description")
    organization.description = sanitize_content_blocks(data.get("description", []))
    organization.website = data.get("website")
    organization.social = data.get("social")
    organization.status = data.get("status", "draft")
    organization.seo = data.get("seo")
    organization.featured = data.get("featured", False)


def _validate_for_publish(organization):
    """A published organization needs enough real public information to be
    worth showing; a draft may stay incomplete indefinitely.
    """
    has_description = bool(organization.short_description) or bool(organization.description)
    if not has_description:
        raise ApiError(
            "Add a short description or full description before publishing this organization.",
            422,
            code="publish_validation_failed",
        )


def _is_referenced(organization):
    checks = (
        Person.query.filter_by(organization_id=organization.id).first(),
        Job.query.filter_by(organization_id=organization.id).first(),
        Opportunity.query.filter_by(organization_id=organization.id).first(),
        Series.query.filter_by(sponsor_organization_id=organization.id).first(),
        Article.query.filter(Article.related_organizations.any(id=organization.id)).first(),
    )
    return any(checks)


class OrganizationListResource(Resource):
    def get(self):
        editor = _can_edit_or_none()
        query = Organization.query.order_by(Organization.featured.desc(), Organization.name)
        if not editor:
            query = query.filter(Organization.status == "published")
        elif request.args.get("status"):
            query = query.filter(Organization.status == request.args["status"])
        query = apply_country_or_region_filter(query, Organization, request.args)
        query = apply_equality_filters(query, Organization, request.args, ["org_type"])
        query = apply_search(query, Organization, request.args, ["name", "industry"], param="query")
        result = paginate(query, organization_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("people.manage")
    def post(self):
        data = OrganizationInputSchema().load(request.get_json(silent=True) or {})

        organization = Organization()
        if data.get("slug"):
            organization.slug = validate_explicit_slug(Organization, data["slug"])
        else:
            organization.slug = generate_unique_slug(Organization, data["name"])

        _apply_fields(organization, data)
        if organization.status == "published":
            _validate_for_publish(organization)
        db.session.add(organization)
        db.session.commit()
        return success_response(organization_schema.dump(organization), status=201)


class OrganizationDetailResource(Resource):
    def get(self, slug):
        organization = Organization.query.filter_by(slug=slug).first()
        if organization is None:
            raise ApiError("Organization not found.", 404, code="not_found")
        if organization.status != "published" and not _can_edit_or_none():
            raise ApiError("Organization not found.", 404, code="not_found")
        return success_response(organization_schema.dump(organization))

    def put(self, slug):
        _require_manage()
        organization = Organization.query.filter_by(slug=slug).first()
        if organization is None:
            raise ApiError("Organization not found.", 404, code="not_found")

        data = OrganizationInputSchema().load(request.get_json(silent=True) or {})

        if data.get("slug") and data["slug"] != organization.slug:
            organization.slug = validate_explicit_slug(Organization, data["slug"], current_id=organization.id)

        _apply_fields(organization, data)
        if organization.status == "published":
            _validate_for_publish(organization)
        db.session.commit()
        return success_response(organization_schema.dump(organization))

    def delete(self, slug):
        _require_manage()
        organization = Organization.query.filter_by(slug=slug).first()
        if organization is None:
            raise ApiError("Organization not found.", 404, code="not_found")

        if _is_referenced(organization):
            raise ApiError(
                "This organization is referenced by people, jobs, opportunities, articles, or series "
                "and can't be deleted. Remove those relationships first, or archive this organization instead.",
                409,
                code="reference_conflict",
            )

        db.session.delete(organization)
        db.session.commit()
        return success_response({"deleted": True})


api.add_resource(OrganizationListResource, "")
api.add_resource(OrganizationDetailResource, "/<string:slug>")
