from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.people import Organization
from app.schemas.people import OrganizationInputSchema, OrganizationSchema
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_country_or_region_filter, apply_search
from app.utils.responses import ApiError, success_response

organizations_bp = Blueprint("organizations", __name__)
api = Api(organizations_bp)

organization_schema = OrganizationSchema()


class OrganizationListResource(Resource):
    def get(self):
        query = Organization.query.order_by(Organization.featured.desc(), Organization.name)
        query = apply_country_or_region_filter(query, Organization, request.args)
        query = apply_search(query, Organization, request.args, ["name", "industry"])
        return success_response(organization_schema.dump(query.all(), many=True))

    @permission_required("people.manage")
    def post(self):
        data = OrganizationInputSchema().load(request.get_json(silent=True) or {})
        organization = Organization(**{k: v for k, v in data.items() if k != "slug"})
        organization.slug = data.get("slug") or generate_unique_slug(Organization, data["name"])
        db.session.add(organization)
        db.session.commit()
        return success_response(organization_schema.dump(organization), status=201)


class OrganizationDetailResource(Resource):
    def get(self, slug):
        organization = Organization.query.filter_by(slug=slug).first()
        if organization is None:
            raise ApiError("Organization not found.", 404, code="not_found")
        return success_response(organization_schema.dump(organization))


api.add_resource(OrganizationListResource, "")
api.add_resource(OrganizationDetailResource, "/<string:slug>")
