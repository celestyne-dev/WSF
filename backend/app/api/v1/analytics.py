from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.analytics import AnalyticsEvent
from app.schemas.analytics import AnalyticsEventInputSchema, AnalyticsEventSchema
from app.utils.pagination import paginate
from app.utils.responses import success_response

analytics_bp = Blueprint("analytics", __name__)
api = Api(analytics_bp)

event_schema = AnalyticsEventSchema()


def _optional_current_user_id():
    """Analytics ingestion is public (anonymous visitors trigger most of
    these events), but attribute the event to a logged-in user when a
    valid token happens to be present.
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    return current_user.id if current_user else None


class AnalyticsEventListResource(Resource):
    def post(self):
        data = AnalyticsEventInputSchema().load(request.get_json(silent=True) or {})
        event = AnalyticsEvent(
            event_name=data["event_name"],
            entity_type=data.get("entity_type"),
            entity_id=data.get("entity_id"),
            payload=data.get("payload"),
            acquisition=data.get("acquisition"),
            session_id=data.get("session_id"),
            user_id=_optional_current_user_id(),
        )
        db.session.add(event)
        db.session.commit()
        return success_response(None, status=201)

    @permission_required("analytics.view")
    def get(self):
        query = AnalyticsEvent.query.order_by(AnalyticsEvent.created_at.desc())
        event_name = request.args.get("event_name")
        if event_name:
            query = query.filter_by(event_name=event_name)
        result = paginate(query, event_schema)
        return success_response(result["items"], meta=result["meta"])


class AnalyticsSummaryResource(Resource):
    @permission_required("analytics.view")
    def get(self):
        rows = (
            db.session.query(AnalyticsEvent.event_name, db.func.count(AnalyticsEvent.id))
            .group_by(AnalyticsEvent.event_name)
            .order_by(db.func.count(AnalyticsEvent.id).desc())
            .all()
        )
        return success_response([{"eventName": name, "count": count} for name, count in rows])


api.add_resource(AnalyticsEventListResource, "/events")
api.add_resource(AnalyticsSummaryResource, "/summary")
