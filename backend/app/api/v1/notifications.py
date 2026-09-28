"""Admin Notifications & Work Queue — every endpoint here is implicitly
scoped to the authenticated caller (`current_user`); there is no
`recipient_user_id` query parameter anywhere, by design — a CMS user must
never be able to enumerate another staff member's notifications (see task
spec's CURRENT USER ONLY section). Any authenticated, active CMS user may
use these endpoints for their own inbox — this is not gated by a specific
feature permission (compare app/api/v1/learning.py's `learning.manage`
gate): everyone with a CMS login has notifications of their own to read.
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.extensions import db
from app.models.notification import NOTIFICATION_TYPES, Notification
from app.schemas.notification import NotificationSchema
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

notifications_bp = Blueprint("notifications", __name__)
api = Api(notifications_bp)

notification_schema = NotificationSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _own_notification_or_404(notification_id, user):
    # Scoped by recipient_user_id in the query itself — a request for
    # another user's notification id 404s exactly like a nonexistent one,
    # never a 403 that would confirm the id belongs to someone else.
    notification = Notification.query.filter_by(id=notification_id, recipient_user_id=user.id).first()
    if notification is None:
        raise ApiError("Notification not found.", 404, code="not_found")
    return notification


class NotificationListResource(Resource):
    def get(self):
        user = _require_active_user()
        query = Notification.query.filter_by(recipient_user_id=user.id)

        status_filter = request.args.get("filter", "all")
        if status_filter == "archived":
            query = query.filter(Notification.is_archived.is_(True))
        else:
            query = query.filter(Notification.is_archived.is_(False))
            if status_filter in ("unread", "needs_attention"):
                # "Needs Attention" is currently the same query as
                # "Unread" — see this module's own docstring above and the
                # task's final report for why (checking whether each
                # notification's source entity has already been resolved
                # would mean an extra per-row query per notification type,
                # which the task spec explicitly allows deferring: "keep
                # first implementation simple: Unread = attention").
                query = query.filter(Notification.is_read.is_(False))

        if request.args.get("type") in NOTIFICATION_TYPES:
            query = query.filter(Notification.notification_type == request.args["type"])
        if request.args.get("priority") in ("normal", "high"):
            query = query.filter(Notification.priority == request.args["priority"])

        query = query.order_by(Notification.created_at.desc())
        result = paginate(query, notification_schema, default_per_page=20)
        return success_response(result["items"], meta=result["meta"])


class UnreadCountResource(Resource):
    def get(self):
        # A single COUNT query — never hydrates or dumps any row (see task
        # spec's PERFORMANCE section: "unread count endpoint must remain
        # lightweight").
        user = _require_active_user()
        count = Notification.query.filter_by(
            recipient_user_id=user.id, is_archived=False, is_read=False
        ).count()
        return success_response({"count": count})


class NotificationReadResource(Resource):
    def patch(self, notification_id):
        user = _require_active_user()
        notification = _own_notification_or_404(notification_id, user)
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = db.func.now()
            db.session.commit()
        return success_response(notification_schema.dump(notification))


class NotificationUnreadResource(Resource):
    def patch(self, notification_id):
        user = _require_active_user()
        notification = _own_notification_or_404(notification_id, user)
        if notification.is_read:
            notification.is_read = False
            notification.read_at = None
            db.session.commit()
        return success_response(notification_schema.dump(notification))


class NotificationArchiveResource(Resource):
    def patch(self, notification_id):
        """Archiving only ever changes this notification row — it never
        touches, deletes, or otherwise affects the source entity it
        references (see task spec's ARCHIVE / DISMISS section).
        """
        user = _require_active_user()
        notification = _own_notification_or_404(notification_id, user)
        if not notification.is_archived:
            notification.is_archived = True
            notification.archived_at = db.func.now()
            db.session.commit()
        return success_response(notification_schema.dump(notification))


class MarkAllReadResource(Resource):
    def post(self):
        """Marks every currently-unread, non-archived notification read
        for the calling user only — never touches archived state (see
        task spec's MARK ALL READ section) and never another user's rows.
        """
        user = _require_active_user()
        updated = (
            Notification.query.filter_by(recipient_user_id=user.id, is_archived=False, is_read=False)
            .update({"is_read": True, "read_at": db.func.now()}, synchronize_session=False)
        )
        db.session.commit()
        return success_response({"updated": updated})


api.add_resource(NotificationListResource, "")
api.add_resource(UnreadCountResource, "/unread-count")
api.add_resource(NotificationReadResource, "/<int:notification_id>/read")
api.add_resource(NotificationUnreadResource, "/<int:notification_id>/unread")
api.add_resource(NotificationArchiveResource, "/<int:notification_id>/archive")
api.add_resource(MarkAllReadResource, "/mark-all-read")
