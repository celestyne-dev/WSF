import json

from marshmallow import ValidationError, fields, validate

from app.extensions import ma
from app.models.analytics import AnalyticsEvent
from app.services.analytics_taxonomy import KNOWN_EVENT_NAMES

# Ingestion is public (anonymous visitors post most of these), so the
# payload/acquisition JSON blobs are bounded here rather than trusted —
# see spec section 65/67: never accept an arbitrary-size blob from the
# client. 4KB is generous for the small {field: value} shapes every
# trackEvent() call site actually sends (see analytics_taxonomy.py).
MAX_JSON_FIELD_BYTES = 4096


class AnalyticsEventSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = AnalyticsEvent
        load_instance = False


def _validate_json_size(value):
    if value is None:
        return
    if len(json.dumps(value)) > MAX_JSON_FIELD_BYTES:
        raise ValidationError(f"Must be {MAX_JSON_FIELD_BYTES} bytes or smaller when serialized.")


class AnalyticsEventInputSchema(ma.Schema):
    # Restricted to the controlled event-name registry (see
    # app/services/analytics_taxonomy.py) — an unrecognized name is a real
    # mistake worth a clear 422, not a silently-accepted new metric no
    # report will ever know to look for.
    event_name = fields.String(required=True, data_key="eventName", validate=validate.OneOf(KNOWN_EVENT_NAMES))
    entity_type = fields.String(
        required=False, allow_none=True, data_key="entityType", validate=validate.Length(max=50)
    )
    entity_id = fields.String(required=False, allow_none=True, data_key="entityId", validate=validate.Length(max=100))
    payload = fields.Dict(required=False, allow_none=True, validate=_validate_json_size)
    acquisition = fields.Dict(required=False, allow_none=True, validate=_validate_json_size)
    session_id = fields.String(
        required=False, allow_none=True, data_key="sessionId", validate=validate.Length(max=100)
    )
