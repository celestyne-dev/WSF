"""WSF Career Hub public API (anonymous, read-only). See
app/services/career_hub.py — this module only parses the request and
returns the service's normalized cards. No entitlement is ever decided
here; every card links to the original Resource/Learning page, whose own
endpoints enforce access."""
from flask import Blueprint, request
from flask_restful import Api, Resource

from app.services.career_hub import career_hub_meta, parse_filters, search_career_hub
from app.utils.responses import success_response

career_hub_bp = Blueprint("career_hub", __name__)
api = Api(career_hub_bp)


class CareerHubListResource(Resource):
    """GET /api/v1/career-hub?q=&goal=&format=&access=&sort=&page=&pageSize="""

    def get(self):
        result = search_career_hub(parse_filters(request.args))
        return success_response(result["items"], meta=result["meta"])


class CareerHubMetaResource(Resource):
    """GET /api/v1/career-hub/meta — filter vocabulary + New This Month."""

    def get(self):
        return success_response(career_hub_meta())


api.add_resource(CareerHubListResource, "")
api.add_resource(CareerHubMetaResource, "/meta")
