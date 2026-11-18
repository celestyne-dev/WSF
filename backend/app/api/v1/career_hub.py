"""WSF Career Hub public API (anonymous, read-only). See
app/services/career_hub.py — this module only parses the request and
returns the service's normalized cards. No entitlement is ever decided
here; every card links to the original Resource/Learning page, whose own
endpoints enforce access."""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.services.career_hub import career_hub_meta, parse_filters, resolve_viewer, search_career_hub
from app.utils.responses import success_response

career_hub_bp = Blueprint("career_hub", __name__)


def _viewer():
    """Optional auth: a signed-in visitor gets viewer-specific membership
    labels (her tier resolved once per request); anonymous requests get
    exactly the anonymous payload. A bad/expired token is treated as
    anonymous rather than an error on this public page."""
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    user = current_user if current_user else None
    if user is None or not user.is_active:
        return None
    return resolve_viewer(user)
api = Api(career_hub_bp)


class CareerHubListResource(Resource):
    """GET /api/v1/career-hub?q=&goal=&format=&access=&sort=&page=&pageSize="""

    def get(self):
        result = search_career_hub(parse_filters(request.args), viewer=_viewer())
        return success_response(result["items"], meta=result["meta"])


class CareerHubMetaResource(Resource):
    """GET /api/v1/career-hub/meta — filter vocabulary + New This Month."""

    def get(self):
        return success_response(career_hub_meta(viewer=_viewer()))


api.add_resource(CareerHubListResource, "")
api.add_resource(CareerHubMetaResource, "/meta")
