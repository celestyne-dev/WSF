"""Account-linked cookie-consent records (see app/models/consent.py).

POST /api/v1/consent       record the signed-in member's current decision
GET  /api/v1/consent/me    that member's own decision history, newest first

Both are scoped to current_user; there is no user_id parameter. The
browser stays the authority for what runs on the page (it must decide
before any request); this is the account-linked audit trail.
"""
from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource
from sqlalchemy.exc import IntegrityError

from app.auth.decorators import active_user_required
from app.extensions import db, limiter
from app.models.consent import ConsentRecord
from app.services.engagement_settings import get_cookie_consent
from app.utils.responses import ApiError, success_response

consent_bp = Blueprint("consent", __name__)
api = Api(consent_bp)

CATEGORIES = ("preferences", "analytics", "marketing")
HISTORY_LIMIT = 50


def serialize(record):
    return {
        "consentVersion": record.consent_version,
        **{c: getattr(record, c) for c in CATEGORIES},
        "decidedAt": record.decided_at.isoformat(),
        "recordedAt": record.recorded_at.isoformat() if record.recorded_at else None,
    }


def _parse_decided_at(value):
    if not isinstance(value, str) or not value:
        raise ApiError("decidedAt is required.", 422, code="validation_error")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ApiError("decidedAt must be an ISO 8601 timestamp.", 422, code="validation_error")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    # A browser clock can drift a little; a decision dated well into the
    # future is not a real decision.
    if (parsed - datetime.now(timezone.utc)).total_seconds() > 300:
        raise ApiError("decidedAt can't be in the future.", 422, code="validation_error")
    return parsed


def record_consent(user, data):
    """Store one decision for `user`. Returns (record, created). The
    version must be the consent version currently configured in Studio."""
    if not isinstance(data, dict):
        raise ApiError("Invalid consent payload.", 422, code="validation_error")
    version = data.get("consentVersion")
    if version != get_cookie_consent()["version"]:
        raise ApiError("This consent version is not current.", 409, code="stale_consent_version")
    choices = {}
    for category in CATEGORIES:
        value = data.get(category)
        if not isinstance(value, bool):
            raise ApiError(f"{category} must be true or false.", 422, code="validation_error")
        choices[category] = value
    decided_at = _parse_decided_at(data.get("decidedAt"))

    existing = ConsentRecord.query.filter_by(user_id=user.id, decided_at=decided_at, consent_version=version).first()
    if existing is not None:
        return existing, False
    record = ConsentRecord(user_id=user.id, consent_version=version, decided_at=decided_at, **choices)
    db.session.add(record)
    try:
        db.session.commit()
    except IntegrityError:  # the same decision raced in from another tab
        db.session.rollback()
        return ConsentRecord.query.filter_by(user_id=user.id, decided_at=decided_at, consent_version=version).first(), False
    return record, True


class ConsentRecordResource(Resource):
    decorators = [limiter.limit("30 per minute")]

    @active_user_required
    def post(self):
        record, created = record_consent(current_user, request.get_json(silent=True))
        return success_response(serialize(record), status=201 if created else 200)


class ConsentHistoryResource(Resource):
    @active_user_required
    def get(self):
        rows = (ConsentRecord.query.filter_by(user_id=current_user.id)
                .order_by(ConsentRecord.recorded_at.desc(), ConsentRecord.id.desc()).limit(HISTORY_LIMIT).all())
        return success_response([serialize(r) for r in rows])


api.add_resource(ConsentRecordResource, "")
api.add_resource(ConsentHistoryResource, "/me")
