from marshmallow import fields

from app.extensions import ma
from app.models.analytics import AnalyticsEvent


class AnalyticsEventSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AnalyticsEvent
        load_instance = False


class AnalyticsEventInputSchema(ma.Schema):
    event_name = fields.String(required=True, data_key="eventName")
    entity_type = fields.String(required=False, allow_none=True, data_key="entityType")
    entity_id = fields.String(required=False, allow_none=True, data_key="entityId")
    payload = fields.Dict(required=False, allow_none=True)
    acquisition = fields.Dict(required=False, allow_none=True)
    session_id = fields.String(required=False, allow_none=True, data_key="sessionId")
