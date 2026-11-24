"""Self-service data export, account deletion and privacy requests (Step 16).
Rules: app/services/account_privacy.py.

Member (/api/v1/account):
  GET  /export                   the member's data as a JSON download
  POST /deletion                 {password, removeComments}  schedule deletion (+14 days);
                                 every session ends, the refresh cookie is cleared
  POST /deletion/cancel          {token}  the sign-in cancel token (login of a scheduled account)
  POST /deletion/cancel-link     {token}  the emailed cancel link (works signed out)
  POST /privacy-requests         {requestType, details}
Studio (/api/v1/admin/privacy-requests, permission users.manage):
  GET  ?status=&type=            list (newest first)
  POST                           {requestType, requesterName, requesterEmail, details}
  PATCH /<id>                    {status, adminNotes}
All mutations are rate-limited (shared Redis/PostgreSQL store) and audited.
"""
import json
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, make_response, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required, permission_required
from app.extensions import db, limiter
from app.models.privacy import PRIVACY_REQUEST_STATUSES, PRIVACY_REQUEST_TYPES, PrivacyRequest
from app.services import account_privacy as svc
from app.services.audit import log_action
from app.services.rate_limits import limit
from app.utils.responses import ApiError, success_response

account_privacy_bp = Blueprint("account_privacy", __name__)
api = Api(account_privacy_bp)
admin_privacy_bp = Blueprint("admin_privacy", __name__)
admin_api = Api(admin_privacy_bp)


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _fail(exc):
    raise ApiError(str(exc), exc.status, code=exc.code)


class AccountExportResource(Resource):
    @active_user_required
    @limiter.limit(limit("account_export"))
    def get(self):
        data = svc.build_export(current_user)
        svc.open_privacy_request(request_type="access", user=current_user, source="self_service",
                                 status="completed", details="Self-service JSON export downloaded.")
        db.session.commit()
        log_action(current_user, "account.export", "User", current_user.id)
        response = Response(json.dumps(data, indent=2, ensure_ascii=False), mimetype="application/json")
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        response.headers["Content-Disposition"] = f"attachment; filename=wsf-account-data-{stamp}.json"
        response.headers["Cache-Control"] = "no-store"
        return response


class AccountDeletionResource(Resource):
    @active_user_required
    @limiter.limit(limit("account_deletion"))
    def post(self):
        from app.services.refresh_sessions import clear_refresh_cookie

        data = _body()
        try:
            user = svc.request_deletion(current_user._get_current_object(), data.get("password"),
                                        remove_comments=data.get("removeComments") is True)
        except svc.AccountPrivacyError as exc:
            _fail(exc)
        body = {"success": True, "data": {"deletion_scheduled_for": user.deletion_scheduled_for.isoformat(),
                                          "session_ended": True},
                "message": "Your account is scheduled for deletion. You've been signed out."}
        return clear_refresh_cookie(make_response(jsonify(body), 200))


class AccountDeletionCancelResource(Resource):
    @limiter.limit(limit("account_deletion"))
    def post(self):
        user = svc.cancel_with_login_token(_body().get("token"))
        if user is None:
            raise ApiError("This cancellation has expired. Please sign in again.", 400, code="cancel_token_invalid")
        return success_response(None, message="Deletion cancelled. Please sign in again.")


class AccountDeletionCancelLinkResource(Resource):
    @limiter.limit(limit("account_deletion"))
    def post(self):
        user = svc.cancel_with_email_token(_body().get("token"))
        if user is None:
            raise ApiError("This link isn't valid any more.", 404, code="cancel_link_invalid")
        return success_response(None, message="Deletion cancelled. You can sign in again.")


class MemberPrivacyRequestResource(Resource):
    @active_user_required
    @limiter.limit(limit("privacy_request"))
    def post(self):
        data = _body()
        request_type = data.get("requestType")
        if request_type not in ("access", "correction", "other"):
            raise ApiError("Choose a request type.", 422, code="validation_error")
        details = (data.get("details") or "").strip()
        if not details or len(details) > 2000:
            raise ApiError("Tell us what you need (up to 2000 characters).", 422, code="validation_error")
        row = svc.open_privacy_request(request_type=request_type, user=current_user, source="member_form",
                                       details=details)
        db.session.commit()
        log_action(current_user, "privacy_request.created", "PrivacyRequest", row.id, {"type": request_type})
        return success_response({"id": row.id, "dueAt": row.due_at.isoformat()}, status=201,
                                message="Thanks. We aim to reply within 30 days.")


api.add_resource(AccountExportResource, "/export")
api.add_resource(AccountDeletionResource, "/deletion")
api.add_resource(AccountDeletionCancelResource, "/deletion/cancel")
api.add_resource(AccountDeletionCancelLinkResource, "/deletion/cancel-link")
api.add_resource(MemberPrivacyRequestResource, "/privacy-requests")


# --- Studio ------------------------------------------------------------------------------------


def _dump(row):
    now = datetime.now(timezone.utc)
    due = row.due_at if row.due_at.tzinfo else row.due_at.replace(tzinfo=timezone.utc)
    return {"id": row.id, "requestType": row.request_type, "status": row.status, "source": row.source,
            "requesterName": row.requester_name, "requesterEmail": row.requester_email,
            "accountLinked": row.user_id is not None, "details": row.details, "adminNotes": row.admin_notes,
            "openedAt": row.opened_at.isoformat() if row.opened_at else None, "dueAt": due.isoformat(),
            "overdue": row.status in ("open", "in_progress") and due < now,
            "completedAt": row.completed_at.isoformat() if row.completed_at else None}


class AdminPrivacyRequestListResource(Resource):
    @permission_required("users.manage")
    def get(self):
        query = PrivacyRequest.query
        if request.args.get("status") in PRIVACY_REQUEST_STATUSES:
            query = query.filter_by(status=request.args["status"])
        if request.args.get("type") in PRIVACY_REQUEST_TYPES:
            query = query.filter_by(request_type=request.args["type"])
        rows = query.order_by(PrivacyRequest.opened_at.desc(), PrivacyRequest.id.desc()).limit(500).all()
        return success_response({"items": [_dump(r) for r in rows]})

    @permission_required("users.manage")
    def post(self):
        data = _body()
        if data.get("requestType") not in PRIVACY_REQUEST_TYPES:
            raise ApiError("Choose a request type.", 422, code="validation_error")
        name = (data.get("requesterName") or "").strip()[:200] or None
        email = (data.get("requesterEmail") or "").strip()[:255] or None
        if not name and not email:
            raise ApiError("Record who made the request.", 422, code="validation_error")
        row = svc.open_privacy_request(request_type=data["requestType"], source="studio",
                                       details=(data.get("details") or "").strip()[:5000] or None,
                                       requester_name=name, requester_email=email, created_by=current_user)
        db.session.commit()
        log_action(current_user, "privacy_request.created", "PrivacyRequest", row.id, {"type": row.request_type})
        return success_response(_dump(row), status=201)


class AdminPrivacyRequestDetailResource(Resource):
    @permission_required("users.manage")
    def patch(self, request_id):
        row = db.session.get(PrivacyRequest, request_id)
        if row is None:
            raise ApiError("Request not found.", 404, code="not_found")
        data = _body()
        changes = {}
        if "status" in data:
            if data["status"] not in PRIVACY_REQUEST_STATUSES:
                raise ApiError("Unknown status.", 422, code="validation_error")
            changes["status"] = {"from": row.status, "to": data["status"]}
            row.status = data["status"]
            row.completed_at = datetime.now(timezone.utc) if row.status in ("completed", "declined") else None
        if "adminNotes" in data:
            notes = data["adminNotes"]
            if notes is not None and (not isinstance(notes, str) or len(notes) > 5000):
                raise ApiError("Notes are limited to 5000 characters.", 422, code="validation_error")
            row.admin_notes = notes or None
            changes["notes_updated"] = True
        db.session.commit()
        log_action(current_user, "privacy_request.updated", "PrivacyRequest", row.id, changes)
        return success_response(_dump(row))


admin_api.add_resource(AdminPrivacyRequestListResource, "/privacy-requests")
admin_api.add_resource(AdminPrivacyRequestDetailResource, "/privacy-requests/<int:request_id>")
