from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.opportunity import Opportunity
from app.models.taxonomy import Topic
from app.schemas.geography import CountrySchema
from app.schemas.media import MediaSchema
from app.schemas.opportunity import OpportunityInputSchema, OpportunitySchema
from app.schemas.people import OrganizationSchema
from app.schemas.taxonomy import TopicSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.opportunity_access import (
    check_opportunity_application_access,
    has_safe_application_target,
    is_application_open,
    viewer_can_access,
)
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

opportunities_bp = Blueprint("opportunities", __name__)
api = Api(opportunities_bp)

opportunity_schema = OpportunitySchema()


def _dump_opportunity_for_staff(opportunity):
    """OpportunitySchema always excludes application_url/
    application_instructions (see that schema's own Meta.exclude) — this
    is the one place they're explicitly re-attached, and only after the
    caller has already passed an opportunities.manage check. Mirrors
    app/api/v1/events.py's _dump_event_for_staff() for virtual_link.
    """
    data = opportunity_schema.dump(opportunity)
    data["application_url"] = opportunity.application_url
    data["application_instructions"] = opportunity.application_instructions
    return data


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


def _viewer_for_access_check():
    """Distinct from _current_user_or_none(): this one does NOT collapse
    an authenticated-but-inactive account into anonymous — it must reach
    check_opportunity_application_access() as itself so that function
    can tell "no account at all" (401 account_required) apart from "a
    real account that's inactive" (403 forbidden), per spec. Same
    unfiltered pattern as app/api/v1/resources.py's own
    _viewer_for_access_check().
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    return current_user if current_user else None


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
    opportunity.access_type = data.get("access_type", "public")
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
    apply; a draft may stay incomplete indefinitely. circle_only does not
    change any of this — the application mechanism itself is always
    external, with or without Circle gating (spec section U).
    """
    errors = []
    if not opportunity.description:
        errors.append("Add a description before publishing.")
    if not opportunity.application_url:
        errors.append("Add an application URL before publishing — WSF never shows a fake Apply button.")
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


def build_public_opportunity_payload(opportunity, viewer, *, detail=False):
    """The one public-safe Opportunity representation — NEVER includes
    application_url/application_instructions by default (spec section C;
    this is a security boundary, not just a publish-time rule). Reused by
    the public list, public detail, and Saved Items, so none of those
    surfaces can leak the protected application target by construction.

    Only on `detail=True`, for an access_type=="public" opportunity whose
    application is still open and whose stored URL is currently safe, are
    the two protected fields explicitly re-attached — list never does
    this regardless of access_type, and circle_only NEVER does this
    regardless of viewer entitlement (the POST /access endpoint is the
    only path to a circle_only opportunity's application target).
    """
    payload = {
        "id": opportunity.id,
        "slug": opportunity.slug,
        "title": opportunity.title,
        "organization_id": opportunity.organization_id,
        "organization": (
            OrganizationSchema(only=("id", "slug", "name", "logo")).dump(opportunity.organization)
            if opportunity.organization
            else None
        ),
        "organization_name": opportunity.organization_name,
        "logo": MediaSchema().dump(opportunity.logo) if opportunity.logo else None,
        "type": opportunity.type,
        "short_description": opportunity.short_description,
        "description": opportunity.description or [],
        "eligibility": opportunity.eligibility,
        "eligibility_notes": opportunity.eligibility_notes,
        "career_stage": opportunity.career_stage,
        "countries_eligible": CountrySchema(many=True).dump(opportunity.countries_eligible),
        "location": opportunity.location,
        "funding_type": opportunity.funding_type,
        "funding_min": opportunity.funding_min,
        "funding_max": opportunity.funding_max,
        "currency": opportunity.currency,
        "funding_value": opportunity.funding_value,
        "opening_date": opportunity.opening_date.isoformat() if opportunity.opening_date else None,
        "deadline": opportunity.deadline.isoformat() if opportunity.deadline else None,
        "published_date": opportunity.published_date.isoformat() if opportunity.published_date else None,
        "expiry_date": opportunity.expiry_date.isoformat() if opportunity.expiry_date else None,
        "featured": opportunity.featured,
        "sponsored": opportunity.sponsored,
        "status": opportunity.status,
        "is_closed": not is_application_open(opportunity),
        "seo": opportunity.seo or {},
        "topics": TopicSchema(many=True, exclude=("article_count",)).dump(opportunity.topics),
        "access_type": opportunity.access_type,
        "requiresCircle": opportunity.access_type == "circle_only",
    }
    if detail:
        payload["viewerCanAccess"] = viewer_can_access(opportunity, viewer)
        if (
            opportunity.access_type == "public"
            and is_application_open(opportunity)
            and has_safe_application_target(opportunity)
        ):
            payload["application_url"] = opportunity.application_url
            payload["application_instructions"] = opportunity.application_instructions
    return payload


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

        if can_manage:
            result = paginate(query, schema=None)
            items = [_dump_opportunity_for_staff(o) for o in result["items"]]
            return success_response(items, meta=result["meta"])

        # Public list never re-attaches the protected application fields
        # (spec section C) and deliberately skips viewerCanAccess here too
        # (spec section H) — no per-item Circle entitlement query on a
        # paginated list, unlike the single-item detail response below.
        result = paginate(query, schema=None)
        items = [build_public_opportunity_payload(o, None, detail=False) for o in result["items"]]
        return success_response(items, meta=result["meta"])

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
        return success_response(_dump_opportunity_for_staff(opportunity), status=201)


class OpportunityDetailResource(Resource):
    def get(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        if opportunity is None:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        editor = _can_edit_or_none()
        if opportunity.status != "published" and not editor:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        if editor:
            return success_response(_dump_opportunity_for_staff(opportunity))
        return success_response(build_public_opportunity_payload(opportunity, _current_user_or_none(), detail=True))

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
        return success_response(_dump_opportunity_for_staff(opportunity))

    def delete(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        if opportunity is None:
            raise ApiError("Opportunity not found.", 404, code="not_found")
        _require_manage()

        db.session.delete(opportunity)
        db.session.commit()
        return success_response({"deleted": True})


class OpportunityAccessResource(Resource):
    """The ONE access-grant endpoint for a circle_only Opportunity's
    application target — public opportunities are allowed through too
    (spec section G, case 4), so a frontend can use this endpoint
    uniformly for either access_type rather than branching client-side.
    Never a GET — releasing the protected external destination is a
    deliberate action, not a passive read (spec section G).
    """

    def post(self, slug):
        opportunity = Opportunity.query.filter_by(slug=slug).first()
        # Draft is never publicly known (matches the detail endpoint).
        # closed/archived ARE known — they just answer "application
        # closed" (409) rather than 404, so the distinct code reaches the
        # caller (spec section G, cases 1-2).
        if opportunity is None or (opportunity.status == "draft" and not _can_edit_or_none()):
            raise ApiError("Opportunity not found.", 404, code="not_found")

        viewer = _viewer_for_access_check()
        check_opportunity_application_access(opportunity, viewer)

        return success_response(
            {
                "application_url": opportunity.application_url,
                "application_instructions": opportunity.application_instructions,
            }
        )


api.add_resource(OpportunityListResource, "")
api.add_resource(OpportunityDetailResource, "/<string:slug>")
api.add_resource(OpportunityAccessResource, "/<string:slug>/access")
