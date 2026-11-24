"""Two-factor authentication endpoints (app/services/two_factor.py).

Sign-in steps (no session exists yet; the short-lived token from
POST /auth/login identifies the account):
  POST /api/v1/auth/2fa/challenge        {token, code} or {token, recovery_code}
  POST /api/v1/auth/2fa/setup/start      {token}   (required set-up at sign-in)
  POST /api/v1/auth/2fa/setup/confirm    {token, code}
Signed-in account settings (access token):
  GET  /api/v1/auth/2fa                  status
  POST /api/v1/auth/2fa/setup/start      {}        (optional set-up)
  POST /api/v1/auth/2fa/setup/confirm    {code}
  POST /api/v1/auth/2fa/recovery-codes   {code}    new codes (old ones stop working)
  POST /api/v1/auth/2fa/disable          {password, code}  (not for required roles)
Administration:
  POST /api/v1/admin/users/<id>/two-factor/reset   Super Admin only

Every security-relevant step is written to the audit log (never a code or
secret). Challenge and set-up are rate-limited.
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required
from app.extensions import db, limiter
from app.models.user import User
from app.services import two_factor
from app.services.audit import log_action
from app.services.rate_limits import limit
from app.services.refresh_sessions import invalidate_user_sessions
from app.services.two_factor import TwoFactorError
from app.utils.responses import ApiError, error_response, success_response

two_factor_bp = Blueprint("two_factor", __name__)
api = Api(two_factor_bp)
admin_two_factor_bp = Blueprint("admin_two_factor", __name__)
admin_api = Api(admin_two_factor_bp)


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _signed_in_user():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    user = current_user if current_user else None
    return user if user is not None and user.is_active else None


def _target_user(data, purpose):
    """The account this step is for: a sign-in token when given, otherwise
    the signed-in user (optional set-up from account settings)."""
    token = data.get("token")
    if token:
        return two_factor.read_token(token, purpose), True
    user = _signed_in_user()
    if user is None:
        raise ApiError("Please sign in.", 401, code="authorization_required")
    return user, False


def _complete_sign_in(user, extra=None):
    from datetime import datetime, timezone

    from app.api.v1.auth import signed_in_response

    user.last_login_at = datetime.now(timezone.utc)
    log_action(user, "user.login", "User", user.id, changes={"two_factor": True})
    return _with_extra(signed_in_response(user, two_factor_verified=True), extra)


def _with_extra(response, extra):
    if extra:
        import json

        body = json.loads(response.get_data(as_text=True))
        body["data"].update(extra)
        response.set_data(json.dumps(body))
    return response


class ChallengeResource(Resource):
    decorators = [limiter.limit(limit("two_factor_challenge"))]

    def post(self):
        data = _body()
        try:
            user = two_factor.read_token(data.get("token"), "challenge")
        except TwoFactorError as exc:
            return error_response(str(exc), 401, code=exc.code)
        if data.get("recovery_code"):
            if not two_factor.use_recovery_code(user, data["recovery_code"]):
                db.session.commit()
                log_action(user, "2fa.challenge_failed", "User", user.id, changes={"method": "recovery_code"})
                return error_response("That recovery code isn't valid or was already used.", 401,
                                      code="invalid_recovery_code")
            log_action(user, "2fa.recovery_code_used", "User", user.id,
                       changes={"remaining": two_factor.recovery_codes_remaining(user)})
            return _complete_sign_in(user, {"recovery_codes_remaining": two_factor.recovery_codes_remaining(user)})
        if not two_factor.verify_code(user, data.get("code")):
            db.session.commit()
            log_action(user, "2fa.challenge_failed", "User", user.id, changes={"method": "totp"})
            return error_response("That code isn't right. Use the newest code from your authenticator app.", 401,
                                  code="invalid_two_factor_code")
        log_action(user, "2fa.challenge_passed", "User", user.id)
        return _complete_sign_in(user)


class SetupStartResource(Resource):
    decorators = [limiter.limit(limit("two_factor_setup"))]

    def post(self):
        data = _body()
        try:
            user, _via_token = _target_user(data, "setup")
        except TwoFactorError as exc:
            return error_response(str(exc), 401, code=exc.code)
        if two_factor.is_enabled(user):
            return error_response("Two-factor authentication is already on.", 409, code="two_factor_already_enabled")
        result = two_factor.start_setup(user)
        db.session.commit()
        log_action(user, "2fa.setup_started", "User", user.id)
        return success_response({"secret": result["secret"], "otpauth_uri": result["otpauthUri"],
                                 "qr_svg": result["qrSvg"]})


class SetupConfirmResource(Resource):
    decorators = [limiter.limit(limit("two_factor_setup"))]

    def post(self):
        data = _body()
        try:
            user, via_token = _target_user(data, "setup")
            codes = two_factor.confirm_setup(user, data.get("code"))
        except TwoFactorError as exc:
            db.session.rollback()
            return error_response(str(exc), 422 if exc.code == "invalid_two_factor_code" else 400, code=exc.code)
        # Turning 2FA on is a security boundary: every access token and
        # session issued before it (none of which passed 2FA) ends, so an old
        # session can't keep working around the new protection.
        invalidate_user_sessions(user, "two_factor_enabled")
        db.session.commit()
        log_action(user, "2fa.enabled", "User", user.id)
        if via_token:
            # Required set-up at sign-in: finishing it signs the member in.
            return _complete_sign_in(user, {"recovery_codes": codes})
        # Optional set-up from account settings: this browser just proved the
        # password-backed session AND a code from the new authenticator, so it
        # gets a fresh two-factor-verified session in place of the ended one
        # (new cookie + access token). Every other browser must sign in again.
        from app.api.v1.auth import signed_in_response

        response = signed_in_response(user, two_factor_verified=True)
        return _with_extra(response, {"recovery_codes": codes})


class StatusResource(Resource):
    @active_user_required
    def get(self):
        return success_response({
            "enabled": two_factor.is_enabled(current_user),
            "required": two_factor.is_required(current_user),
            "recovery_codes_remaining": two_factor.recovery_codes_remaining(current_user),
        })


class RecoveryCodesResource(Resource):
    decorators = [limiter.limit(limit("two_factor_manage"))]

    @active_user_required
    def post(self):
        if not two_factor.is_enabled(current_user):
            return error_response("Two-factor authentication is off.", 409, code="two_factor_not_enabled")
        if not two_factor.verify_code(current_user, _body().get("code")):
            db.session.commit()
            return error_response("That code isn't right.", 422, code="invalid_two_factor_code")
        codes = two_factor.regenerate_recovery_codes(current_user)
        db.session.commit()
        log_action(current_user, "2fa.recovery_codes_regenerated", "User", current_user.id)
        return success_response({"recovery_codes": codes})


class DisableResource(Resource):
    decorators = [limiter.limit(limit("two_factor_manage"))]

    @active_user_required
    def post(self):
        data = _body()
        if two_factor.is_required(current_user):
            return error_response("Your role requires two-factor authentication, so it can't be turned off.", 403,
                                  code="two_factor_required")
        if not two_factor.is_enabled(current_user):
            return error_response("Two-factor authentication is already off.", 409, code="two_factor_not_enabled")
        if not current_user.check_password(data.get("password") or ""):
            return error_response("Your password isn't right.", 422, code="invalid_credentials")
        if not two_factor.verify_code(current_user, data.get("code")):
            db.session.commit()
            return error_response("That code isn't right.", 422, code="invalid_two_factor_code")
        two_factor.disable(current_user)
        db.session.commit()
        log_action(current_user, "2fa.disabled", "User", current_user.id)
        return success_response({"enabled": False})


class AdminResetResource(Resource):
    """Super Admin only: clears another account's 2FA (lost device and no
    recovery codes). The account must set it up again at the next sign-in
    (if its role requires it), and every session it has ends now."""

    @active_user_required
    def post(self, user_id):
        from app.services.user_admin import SUPER_ADMIN_ROLE

        if not current_user.has_role(SUPER_ADMIN_ROLE):
            return error_response("Only a Super Admin can reset two-factor authentication.", 403, code="forbidden")
        if user_id == current_user.id:
            return error_response("You can't reset your own two-factor authentication.", 400, code="self_action")
        target = db.session.get(User, user_id)
        if target is None:
            return error_response("User not found.", 404, code="not_found")
        two_factor.disable(target)
        invalidate_user_sessions(target, "two_factor_reset")
        db.session.commit()
        log_action(current_user, "2fa.reset_by_admin", "User", target.id)
        return success_response({"user_id": target.id, "enabled": False,
                                 "required": two_factor.is_required(target)})


api.add_resource(StatusResource, "")
api.add_resource(ChallengeResource, "/challenge")
api.add_resource(SetupStartResource, "/setup/start")
api.add_resource(SetupConfirmResource, "/setup/confirm")
api.add_resource(RecoveryCodesResource, "/recovery-codes")
api.add_resource(DisableResource, "/disable")
admin_api.add_resource(AdminResetResource, "/users/<int:user_id>/two-factor/reset")
