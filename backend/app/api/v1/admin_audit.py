"""Admin Audit Log — a read-only, append-only history of administrative
CMS actions, built entirely on the existing app/models/audit.py AuditLog
table and app/services/audit.py log_action() writer (the single source
of truth for every action already logged across the backend). This
module adds no new write path and no new audit model — only a
cross-module read/filter/paginate view plus the label/category/redaction
support in app/services/audit_query.py.

Deliberately no PATCH/PUT/DELETE resource: immutability here means the
capability to edit or delete a record doesn't exist in this API at all,
not merely that it's permission-gated.
"""

from datetime import datetime, time, timezone

from flask import Blueprint, request
from flask_restful import Api, Resource
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.auth.decorators import permission_required
from app.models.audit import AuditLog
from app.models.user import User
from app.services.audit_query import ALL_CATEGORIES, KNOWN_ENTITY_TYPES, entity_types_for_category, serialize_audit_page
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

admin_audit_bp = Blueprint("admin_audit", __name__)
api = Api(admin_audit_bp)


def _parse_date(value, end_of_day=False):
    try:
        d = datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        raise ApiError(f"Invalid date: {value!r}. Use YYYY-MM-DD.", 422, code="validation_error")
    t = time.max if end_of_day else time.min
    return datetime.combine(d, t, tzinfo=timezone.utc)


class AdminAuditLogResource(Resource):
    """GET-only. Filters: actor (user id), action (exact), entityType,
    entityId, category, dateFrom/dateTo (YYYY-MM-DD, inclusive, UTC), q
    (matches action, entity type/id, or actor name/email — see module
    docstring for why label search across dozens of entity models isn't
    supported here). Sort: newest first by default; sort=oldest reverses.
    """

    @permission_required("audit.view")
    def get(self):
        query = AuditLog.query.options(selectinload(AuditLog.user))

        actor_id = request.args.get("actor", type=int)
        if actor_id:
            query = query.filter(AuditLog.user_id == actor_id)

        action = request.args.get("action")
        if action:
            query = query.filter(AuditLog.action == action)

        entity_type = request.args.get("entityType")
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)

        entity_id = request.args.get("entityId")
        if entity_id:
            query = query.filter(AuditLog.entity_id == entity_id)

        date_from = request.args.get("dateFrom")
        if date_from:
            query = query.filter(AuditLog.created_at >= _parse_date(date_from))

        date_to = request.args.get("dateTo")
        if date_to:
            query = query.filter(AuditLog.created_at <= _parse_date(date_to, end_of_day=True))

        q = request.args.get("q")
        if q:
            like = f"%{q}%"
            query = query.outerjoin(User, AuditLog.user_id == User.id).filter(
                or_(
                    AuditLog.action.ilike(like),
                    AuditLog.entity_type.ilike(like),
                    AuditLog.entity_id.ilike(like),
                    User.email.ilike(like),
                    User.first_name.ilike(like),
                    User.last_name.ilike(like),
                    User.display_name.ilike(like),
                )
            )

        category = request.args.get("category")
        if category:
            if category not in ALL_CATEGORIES:
                raise ApiError(f"Unknown category: {category!r}.", 422, code="validation_error")
            entity_types = entity_types_for_category(category)
            if entity_types is None:  # "system" — every entity_type not otherwise categorized
                query = query.filter(~AuditLog.entity_type.in_(KNOWN_ENTITY_TYPES))
            else:
                query = query.filter(AuditLog.entity_type.in_(entity_types))

        sort = request.args.get("sort")
        query = query.order_by(AuditLog.created_at.asc() if sort == "oldest" else AuditLog.created_at.desc())

        result = paginate(query, schema=None)
        entries = serialize_audit_page(result["items"])

        return success_response(entries, meta=result["meta"])


api.add_resource(AdminAuditLogResource, "/audit")
