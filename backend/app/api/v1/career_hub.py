"""WSF Career Hub public API (anonymous, read-only). See
app/services/career_hub.py — this module only parses the request and
returns the service's normalized cards. No entitlement is ever decided
here; every card links to the original Resource/Learning page, whose own
endpoints enforce access."""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required
from app.extensions import db
from app.services.career_hub import (
    GOAL_LABELS,
    career_hub_meta,
    normalize_user_goals,
    parse_filters,
    recommended_for_goals,
    resolve_viewer,
    search_career_hub,
    url_value,
)
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


def _goals_payload(user):
    goals = [g for g in (user.career_goals or []) if g in GOAL_LABELS]
    return {
        "goals": [{"key": g, "slug": url_value(g), "label": GOAL_LABELS[g]} for g in goals],
        # True once the optional prompt was answered or skipped.
        "prompted": user.career_goals_prompted_at is not None,
    }


class CareerHubMyGoalsResource(Resource):
    """The signed-in user's own private career goals.

    GET -> {goals, prompted}. PUT {goals: [...]} saves (up to 3; [] clears).
    POST /skip records that the optional prompt was dismissed."""

    @active_user_required
    def get(self):
        return success_response(_goals_payload(current_user))

    @active_user_required
    def put(self):
        data = request.get_json(silent=True) or {}
        current_user.career_goals = normalize_user_goals(data.get("goals"))
        current_user.career_goals_prompted_at = current_user.career_goals_prompted_at or datetime.now(timezone.utc)
        db.session.commit()
        return success_response(_goals_payload(current_user))


class CareerHubSkipGoalsResource(Resource):
    @active_user_required
    def post(self):
        current_user.career_goals_prompted_at = current_user.career_goals_prompted_at or datetime.now(timezone.utc)
        db.session.commit()
        return success_response(_goals_payload(current_user))


class CareerHubRecommendedResource(Resource):
    """GET /career-hub/me/recommended — deterministic picks for the
    signed-in user's goals (never AI). Empty list without goals."""

    @active_user_required
    def get(self):
        goals = [g for g in (current_user.career_goals or []) if g in GOAL_LABELS]
        return success_response({"goals": goals, "items": recommended_for_goals(goals, viewer=resolve_viewer(current_user))})


api.add_resource(CareerHubListResource, "")
api.add_resource(CareerHubMyGoalsResource, "/me/goals")
api.add_resource(CareerHubSkipGoalsResource, "/me/goals/skip")
api.add_resource(CareerHubRecommendedResource, "/me/recommended")
api.add_resource(CareerHubMetaResource, "/meta")
