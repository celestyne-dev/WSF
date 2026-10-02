"""Private "save for later" bookmarks — see app/models/saved_item.py and
app/services/saved_items.py. Every endpoint here is implicitly scoped to
current_user: there is no user_id query parameter anywhere, by design — a
user must never be able to read or affect another user's saved items.
This is a WSF-account feature available to any active authenticated User;
it carries no CMS permission and is not gated by Community membership.
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource
from sqlalchemy.exc import IntegrityError

from app.auth.decorators import active_user_required
from app.extensions import db
from app.models.saved_item import SAVED_CONTENT_TYPES, SavedItem
from app.services.saved_items import fetch_public_content, is_publicly_visible
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

saved_bp = Blueprint("saved", __name__)
api = Api(saved_bp)


def _parse_content_type_and_id(data):
    content_type = data.get("content_type")
    content_id = data.get("content_id")
    if content_type not in SAVED_CONTENT_TYPES:
        raise ApiError("Unsupported content_type.", 422, code="validation_error")
    if not isinstance(content_id, int) or isinstance(content_id, bool) or content_id <= 0:
        raise ApiError("content_id must be a positive integer.", 422, code="validation_error")
    return content_type, content_id


class SavedListResource(Resource):
    @active_user_required
    def get(self):
        content_type_filter = request.args.get("type")
        if content_type_filter and content_type_filter not in SAVED_CONTENT_TYPES:
            raise ApiError("Unsupported type filter.", 422, code="validation_error")

        query = SavedItem.query.filter_by(user_id=current_user.id)
        if content_type_filter:
            query = query.filter_by(content_type=content_type_filter)
        query = query.order_by(SavedItem.created_at.desc())

        result = paginate(query, schema=None)

        items = []
        for saved in result["items"]:
            content = fetch_public_content(saved.content_type, saved.content_id)
            if content is None:
                # Stale pointer (the target was deleted) or content that
                # was public when saved but no longer is — silently
                # excluded, never serialized, never a crash.
                continue
            items.append(
                {
                    "id": saved.id,
                    "content_type": saved.content_type,
                    "content_id": saved.content_id,
                    "saved_at": saved.created_at.isoformat() if saved.created_at else None,
                    "content": content,
                }
            )

        counts_query = (
            db.session.query(SavedItem.content_type, db.func.count(SavedItem.id))
            .filter(SavedItem.user_id == current_user.id)
            .group_by(SavedItem.content_type)
        )
        counts = {content_type: 0 for content_type in SAVED_CONTENT_TYPES}
        for content_type, count in counts_query:
            counts[content_type] = count

        # Pagination is nested inside `data` (rather than passed via the
        # `meta=` kwarg) deliberately: the frontend apiClient's response
        # interceptor only promotes a top-level `meta` into {items,
        # pagination} when `data` itself is a bare array (see
        # frontend/src/api/client.js) — here `data` is {items, counts},
        # so nesting pagination inside it is what the frontend can
        # actually read back out.
        return success_response({"items": items, "counts": counts, "pagination": result["meta"]})

    @active_user_required
    def post(self):
        data = request.get_json(silent=True) or {}
        content_type, content_id = _parse_content_type_and_id(data)

        if not is_publicly_visible(content_type, content_id):
            raise ApiError("Content not found.", 404, code="not_found")

        existing = SavedItem.query.filter_by(
            user_id=current_user.id, content_type=content_type, content_id=content_id
        ).first()
        if existing is None:
            saved = SavedItem(user_id=current_user.id, content_type=content_type, content_id=content_id)
            db.session.add(saved)
            try:
                db.session.commit()
            except IntegrityError:
                # A concurrent request for the same (user, content_type,
                # content_id) won the race — the uniqueness constraint
                # caught it, and the row it created already satisfies
                # this request, so there is nothing left to do.
                db.session.rollback()

        return success_response({"saved": True})


class SavedDetailResource(Resource):
    @active_user_required
    def delete(self, content_type, content_id):
        SavedItem.query.filter_by(
            user_id=current_user.id, content_type=content_type, content_id=content_id
        ).delete()
        db.session.commit()
        return success_response({"saved": False})


class SavedCheckResource(Resource):
    @active_user_required
    def get(self):
        content_type = request.args.get("content_type")
        content_id = request.args.get("content_id", type=int)
        if content_type not in SAVED_CONTENT_TYPES or content_id is None or content_id <= 0:
            return success_response({"saved": False})

        exists = (
            SavedItem.query.filter_by(
                user_id=current_user.id, content_type=content_type, content_id=content_id
            ).first()
            is not None
        )
        return success_response({"saved": exists})


api.add_resource(SavedListResource, "")
api.add_resource(SavedCheckResource, "/check")
api.add_resource(SavedDetailResource, "/<string:content_type>/<int:content_id>")
