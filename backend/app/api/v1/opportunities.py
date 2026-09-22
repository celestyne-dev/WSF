from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.opportunity import Opportunity
from app.models.taxonomy import Topic
from app.schemas.opportunity import OpportunityInputSchema, OpportunitySchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

opportunities_bp = Blueprint("opportunities", __name__)
api = Api(opportunities_bp)

opportunity_schema = OpportunitySchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _current_user_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("opportunities.manage"):
        raise ApiError("You do not have permission to manage opportunities.", 403, code="forbidden")
    return user


def _can_edit_or_none():
    try:
        return _require_manage()
    except Exception:
        return None


def _resolve_organization(organization_id):
    if not organization_id:
        return None
    from app.models.people import Organization

    org = db.session.get(Organization, organization_id)
    if org is None:
        raise ApiError("Organization not found.", 404, code="not_found")
    return org


def _resolve_countries(codes):
    from app.models.geography import Country

    countries = Country.query.filter(Country.code.in_([c.upper() for c in codes])).all()
    if len(countries) != len(set(codes)):
        found = {c.code for c in countries}
        missing = [c for c in codes if c.upper() not in found]
        raise ApiError(f'Country "{missing[0]}" not found.', 404, code="not_found")
    return countries


def _resolve_topics(slugs):
    topics = Topic.query.filter(Topic.slug.in_(slugs)).all()
    if len(topics) != len(set(slugs)):
        found = {t.slug for t in topics}
        missing = [s for s in slugs if s not in found]
        raise ApiError(f'Topic "{missing[0]}" not found.', 404, code="not_found")
    return topics


def _apply_fields(opportunity, data, organization):
    opportunity.title = data["title"]
    opportunity.organization = organization
    opportunity.organization_name = data.get("organization_name") or (
        organization.name if organization else opportunity.organization_name
    )
    opportunity.logo_media_id = data.get("logo_media_id")
    opportunity.type = data.get("type")
    opportunity.short_description = data.get("short_description")
    opportunity.description = sanitize_content_blocks(data.get("description", []))
    opportunity.eligibility = data.get("eligibility")
    opportunity.eligibility_notes = data.get("eligibility_notes")
    opportunity.career_stage = data.get("career_stage")
    opportunity.location = data.get("location")
    opportunity.funding_type = data.get("funding_type")
    opportunity.funding_min = data.get("funding_min")
    opportunity.funding_max = data.get("funding_max")
    opportunity.currency = data.get("currency")
    opportunity.funding_value = data.get("funding_value")
    opportunity.application_url = data.get("application_url")
    opportunity.application_instructions = data.get("application_instructions")
    opportunity.opening_date = data.get("opening_date")
    opportunity.deadline = data.get("deadline")
    opportunity.expiry_date = data.get("expiry_date")
    opportunity.featured = data.get("featured", False)
    opportunity.sponsored = data.get("sponsored", False)
    opportunity.status = data.get("status", "published")
    opportunity.seo = data.get("seo")
    opportunity.countries_eligible = _resolve_countries(data.get("countries_eligible", []))
    opportunity.topics = _resolve_topics(data.get("topic_slugs", []))
    if opportunity.status == "published" and opportunity.published_date is None:
        opportunity.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        opportunity.published_date = data["published_date"]


def _validate_for_publish(opportunity):
    """A published opportunity needs a real description and a real way to
    apply; a draft may stay incomplete indefinitely.
    """
    errors = []
    if not opportunity.description:
        errors.append("Add a description before publishing.")
    if not opportunity.application_url:
        errors.append("Add an application URL before publishing — WSF never shows a fake Apply button.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


class OpportunityListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        can_manage = bool(user and user.has_permission("opportunities.manage"))

        query = Opportunity.query.order_by(Opportunity.featured.desc(), Opportunity.deadline)
        if can_manage:
            if request.args.get("status"):
                query = query.filter(Opportunity.status == request.args["status"])
        else:
            query = query.filter(Opportunity.status == "published")
            query = query.filter(or_(Opportunity.expiry_date.is_(None), Opportunity.expiry_date >= date.today()))

        opp_type = request.args.get("type")
        if opp_type:
            query = query.filter(Opportunity.type == opp_type)
        country = request.args.get("country")
        if country:
            query = query.filter(Opportunity.countries_eligible.any(code=country.upper()))
        region = request.args.get("region")
        if region:
            from app.models.geography import Country

            query = query.filter(Opportunity.countries_eligible.any(Country.region == region))
        topic = request.args.get("topic")
        if topic:
            query = query.filter(Opportunity.topics.any(slug=topic))
        query = apply_search(query, Opportunity, request.args, ["title", "organization_name"], param="query")
        if request.args.get("organization"):
            query = query.filter(Opportunity.organization.has(slug=request.args["organization"]))
        if request.args.get("featured") == "true":
            query = query.filter(Opportunity.featured.is_(True))

        result = paginate(query, opportunity_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        _require_manage()
        data = OpportunityInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_id"))

        opportunity = Opportunity()
        if data.get("slug"):
            opportunity.slug = validate_explicit_slug(Opportunity, data["slug"])
        else:
            opportunity.slug = generate_unique_slug(Opportunity, data["title"])

        _apply_fields(opportunity, data, organization)
        if opportunity.status == "published":
            _validate_for_publish(opportunity)
        db.session.add(opportunity)
        db.session.commit()
        return success_response(opportunity_schema.dump(opportunity), status=201)


class OpportunityDetailResource(Resource):
    def get(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        if opportunity is None:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        if opportunity.status != "published" and not _can_edit_or_none():
            raise ApiError("Opportunity not found.", 404, code="not_found")
        return success_response(opportunity_schema.dump(opportunity))

    def put(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        if opportunity is None:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        _require_manage()

        data = OpportunityInputSchema().load(request.get_json(silent=True) or {})
        organization = _resolve_organization(data.get("organization_id"))

        if data.get("slug") and data["slug"] != opportunity.slug:
            opportunity.slug = validate_explicit_slug(Opportunity, data["slug"], current_id=opportunity.id)

        _apply_fields(opportunity, data, organization)
        if opportunity.status == "published":
            _validate_for_publish(opportunity)
        db.session.commit()
        return success_response(opportunity_schema.dump(opportunity))

    def delete(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        if opportunity is None:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        _require_manage()

        db.session.delete(opportunity)
        db.session.commit()
        return success_response({"deleted": True})


api.add_resource(OpportunityListResource, "")
api.add_resource(OpportunityDetailResource, "/<string:slug>")
