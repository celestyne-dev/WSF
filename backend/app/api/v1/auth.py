from datetime import datetime, timezone

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    current_user,
    get_jwt,
    jwt_required,
    verify_jwt_in_request,
)
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required
from app.extensions import db, limiter
from app.models.geography import Country
from app.models.token_blocklist import TokenBlocklist
from app.models.user import Role, User
from app.schemas.user import (
    ChangePasswordSchema,
    ForgotPasswordSchema,
    LoginSchema,
    RegisterSchema,
    ResetPasswordSchema,
    SelfProfileUpdateSchema,
    UserSchema,
)
from app.services import two_factor
from app.services.account_policy import get_account_policy, legal_document_version
from app.services.audit import log_action
from app.services.email_verification import send_verification, verify_token
from app.services.password_reset import request_password_reset, reset_password
from app.services.rate_limits import limit
from app.services.refresh_sessions import (
    RefreshSessionError,
    clear_refresh_cookie,
    create_session,
    csrf_problem,
    find_session,
    invalidate_user_sessions,
    read_refresh_cookie,
    revoke,
    set_refresh_cookie,
    validate_session,
)
from app.utils.responses import ApiError, error_response, success_response

auth_bp = Blueprint("auth", __name__)
api = Api(auth_bp)


def signed_in_response(user, status=200, two_factor_verified=False, extra=None):
    """Body: the user + a short-lived access token (kept in memory by the
    browser). The refresh credential goes ONLY into the HttpOnly cookie."""
    raw, session = create_session(user, two_factor_verified=two_factor_verified)
    db.session.commit()
    body = {"success": True, "data": {"user": user_schema.dump(user), "access_token": create_access_token(identity=user),
                                      **(extra or {})}}
    return set_refresh_cookie(make_response(jsonify(body), status), raw, session)


def needs_two_factor(user, session):
    """A session that did not pass two-factor can't be used by an account
    that has two-factor turned on (optional or required) or whose role
    requires it."""
    return (two_factor.is_enabled(user) or two_factor.is_required(user)) and not session.two_factor_verified


def _error_clearing_cookie(message, status, code):
    payload, status = error_response(message, status, code=code)
    return clear_refresh_cookie(make_response(jsonify(payload), status))

register_schema = RegisterSchema()
login_schema = LoginSchema()
user_schema = UserSchema()
change_password_schema = ChangePasswordSchema()
self_profile_update_schema = SelfProfileUpdateSchema()
forgot_password_schema = ForgotPasswordSchema()
reset_password_schema = ResetPasswordSchema()


class RegisterResource(Resource):
    @limiter.limit(limit("signup"))
    def post(self):
        data = register_schema.load(request.get_json(silent=True) or {})
        email = data["email"].lower()

        # Minimum age (Step 18): explicit, unticked-by-default confirmation,
        # checked before any lookup or write so nothing about the person is
        # stored when it's missing. No date of birth is collected.
        minimum_age = get_account_policy()["minimumAge"]
        if data.get("age_confirmed") is not True:
            raise ApiError(f"You must confirm that you are at least {minimum_age} years old to create an account.",
                           422, code="age_confirmation_required")

        if User.query.filter_by(email=email).first():
            return error_response("An account with this email already exists.", 409, code="email_taken")

        # A browser always sends a code CountrySelect offers, but a direct
        # API request must not be trusted to — same validation MeResource.patch
        # below applies to self-profile edits, so a malformed code 422s here
        # rather than reaching the country_code FK and risking a 500.
        country_code = (data.get("country_code") or "").strip().upper() or None
        if country_code and not db.session.get(Country, country_code):
            raise ApiError("Unknown country code.", 422, code="invalid_country")

        user = User(
            email=email,
            first_name=data["first_name"],
            last_name=data["last_name"],
            country_code=country_code,
        )
        accepted_at = datetime.now(timezone.utc)
        user.age_confirmed_at = accepted_at
        user.age_confirmed_minimum = minimum_age
        user.terms_version_accepted = legal_document_version("terms")
        user.privacy_version_accepted = legal_document_version("privacy")
        user.legal_accepted_at = accepted_at
        user.set_password(data["password"])

        member_role = Role.query.filter_by(name="member").first()
        if member_role:
            user.roles.append(member_role)

        # Batch 4 corrections: email ownership must be proven before the
        # account gets normal access (app/auth/decorators.py).
        user.email_verification_required = True
        db.session.add(user)
        db.session.commit()
        log_action(user, "user.register", "User", user.id)
        sent = send_verification(user)
        db.session.commit()

        return signed_in_response(user, status=201, extra={"verification_email_sent": sent})


class LoginResource(Resource):
    # Login brute-force protection (see task spec's RATE LIMITING/LOGIN
    # BRUTE FORCE sections): conservative enough to not bother a real user
    # mistyping a password a few times, tight enough to make scripted
    # credential-stuffing slow. Per-IP, counted in the shared store (Redis,
    # PostgreSQL while Redis is down; app/services/rate_limit_storage.py),
    # so all workers share one count — this is not account lockout (no account-level state is written), so it can't be
    # used to lock a legitimate user out by repeatedly failing their login.
    @limiter.limit(limit("login"))
    def post(self):
        data = login_schema.load(request.get_json(silent=True) or {})
        user = User.query.filter_by(email=data["email"].lower()).first()

        if not user or not user.check_password(data["password"]):
            return error_response("Invalid email or password.", 401, code="invalid_credentials")
        if not user.is_active:
            return error_response("This account has been deactivated.", 403, code="account_inactive")
        if user.deletion_scheduled_for is not None:
            # Scheduled for deletion (Step 16): no session, only the option to
            # cancel the deletion (app/services/account_privacy.py).
            from app.services.account_privacy import issue_login_cancel_token

            return success_response({"deletion_pending": True,
                                     "deletion_scheduled_for": user.deletion_scheduled_for.isoformat(),
                                     "cancel_token": issue_login_cancel_token(user)})

        # Two-factor (app/services/two_factor.py): the password alone never
        # creates a session for an account that has, or must have, 2FA.
        if two_factor.is_enabled(user):
            log_action(user, "2fa.challenge_issued", "User", user.id)
            return success_response({"two_factor": "challenge",
                                     "two_factor_token": two_factor.issue_token(user, "challenge")})
        if two_factor.is_required(user):
            log_action(user, "2fa.setup_required", "User", user.id)
            return success_response({"two_factor": "setup",
                                     "two_factor_token": two_factor.issue_token(user, "setup")})

        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action(user, "user.login", "User", user.id)

        return signed_in_response(user)


class RefreshResource(Resource):
    """The only endpoint the HttpOnly refresh cookie is ever sent to (its
    Path). POST: a fresh access token + the user (silent refresh on page
    load). DELETE: sign out. Both are CSRF-checked (header + Origin, see
    app/services/refresh_sessions.py)."""

    decorators = [limiter.limit(limit("session_refresh"))]

    def post(self):
        problem = csrf_problem()
        if problem:
            return error_response("This request can't use the session cookie.", 403, code=problem)
        raw = read_refresh_cookie()
        if not raw:
            # Not signed in on this browser: a normal answer, not an error.
            return success_response(None)
        try:
            session, user = validate_session(raw)
        except RefreshSessionError as exc:
            return _error_clearing_cookie("Your session has ended. Please sign in again.", 401, f"session_{exc}")
        if needs_two_factor(user, session):
            # Defence in depth: turning 2FA on or changing roles already ends
            # older sessions (invalidate_user_sessions); this also covers a
            # deploy that adds a role to TWO_FACTOR_REQUIRED_ROLES.
            revoke(session, "two_factor_required")
            db.session.commit()
            return _error_clearing_cookie("Two-factor authentication is now required. Please sign in again.", 401,
                                          "session_two_factor_required")
        session.last_used_at = datetime.now(timezone.utc)
        db.session.commit()
        return success_response({"user": user_schema.dump(user), "access_token": create_access_token(identity=user)})

    def delete(self):
        problem = csrf_problem()
        if problem:
            return error_response("This request can't use the session cookie.", 403, code=problem)
        session = find_session(read_refresh_cookie())
        revoke(session, "sign_out")
        # Also block the presented access token for its remaining minutes.
        try:
            verify_jwt_in_request(optional=True)
            payload = get_jwt()
        except Exception:  # an expired/invalid access token must not stop sign-out
            payload = {}
        if payload.get("jti"):
            db.session.add(TokenBlocklist(
                jti=payload["jti"], token_type=payload.get("type", "access"),
                user_id=int(payload["sub"]) if payload.get("sub") else None,
                expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            ))
        db.session.commit()
        if session is not None:
            log_action(db.session.get(User, session.user_id), "user.logout", "User", session.user_id)
        return clear_refresh_cookie(make_response(jsonify({"success": True, "data": None, "message": "Signed out."}), 200))


class LogoutResource(Resource):
    """Blocks the presented access token only (kept for API clients).
    Browsers sign out with DELETE /auth/refresh, which also revokes the
    refresh session and clears the cookie."""

    @jwt_required(verify_type=False)
    def post(self):
        jwt_payload = get_jwt()
        db.session.add(
            TokenBlocklist(
                jti=jwt_payload["jti"],
                token_type=jwt_payload["type"],
                user_id=current_user.id if current_user else None,
                expires_at=datetime.fromtimestamp(jwt_payload["exp"], tz=timezone.utc),
            )
        )
        db.session.commit()
        return success_response(None, message="Logged out.")


class ChangePasswordResource(Resource):
    """Self-service password change — the only way must_change_password
    ever clears (see app/auth/decorators.py's centralized enforcement,
    which otherwise rejects every permission/role-gated request from an
    account still carrying that flag). Deliberately plain @jwt_required()
    rather than the RBAC decorators: a forced-change user must be able to
    reach this endpoint precisely because she can't reach anything else.

    A successful change ends EVERY credential issued before it — this
    browser's access token and refresh session included, every other
    browser's, and any unused two-factor sign-in token
    (invalidate_user_sessions) — and expires this browser's refresh cookie.
    No replacement session is issued: the member signs in again with the
    new password, going through two-factor as usual.
    """

    @jwt_required()
    def post(self):
        if not current_user or not current_user.is_active:
            return error_response("Account is inactive or no longer exists.", 403, code="forbidden")

        data = change_password_schema.load(request.get_json(silent=True) or {})

        if not current_user.check_password(data["current_password"]):
            return error_response("Current password is incorrect.", 401, code="invalid_credentials")
        if data["new_password"] != data["confirm_password"]:
            return error_response(
                "New password and confirmation do not match.", 422, code="password_mismatch"
            )
        if data["new_password"] == data["current_password"]:
            return error_response(
                "New password must be different from your current password.", 422, code="password_unchanged"
            )

        user = current_user._get_current_object()
        user.set_password(data["new_password"])
        user.must_change_password = False
        invalidate_user_sessions(user, "password_changed")
        db.session.commit()
        # No `changes` payload — nothing here is safe or useful to audit
        # beyond the fact that it happened (log_action's own redaction in
        # app/services/audit.py would scrub a password value anyway, but
        # this endpoint never hands it one to begin with).
        log_action(user, "user.password_change", "User", user.id)

        body = {"success": True, "data": {"session_ended": True},
                "message": "Your password has been changed. Please sign in again."}
        return clear_refresh_cookie(make_response(jsonify(body), 200))


class MeResource(Resource):
    @jwt_required()
    def get(self):
        if not current_user or not current_user.is_active:
            return error_response("Account is inactive or no longer exists.", 403, code="forbidden")
        return success_response(user_schema.dump(current_user))

    # @active_user_required (not @jwt_required()) deliberately: self-profile
    # editing is a normal protected action, not a session/auth operation, so
    # it goes through the same centralized guard as every CMS endpoint —
    # including the must_change_password block. A forced-change account
    # must finish POST /auth/change-password before she can touch her
    # profile, same as she's blocked from everything else.
    @active_user_required
    def patch(self):
        data = self_profile_update_schema.load(request.get_json(silent=True) or {}, partial=True)

        for field in ("first_name", "last_name", "display_name", "bio"):
            if field in data and isinstance(data[field], str):
                data[field] = data[field].strip()
        if data.get("first_name") == "":
            raise ApiError("First name cannot be blank.", 422, code="validation_error")
        if data.get("last_name") == "":
            raise ApiError("Last name cannot be blank.", 422, code="validation_error")

        if "country_code" in data:
            code = (data["country_code"] or "").strip().upper() or None
            if code and not db.session.get(Country, code):
                raise ApiError("Unknown country code.", 422, code="invalid_country")
            data["country_code"] = code

        for field, value in data.items():
            setattr(current_user, field, value)
        db.session.commit()
        # Audit WHICH fields changed, never the submitted values — bio/name
        # content has no business living in audit metadata even though
        # it isn't on _SENSITIVE_KEYS's denylist (see app/services/audit.py).
        log_action(
            current_user,
            "user.profile_update",
            "User",
            current_user.id,
            changes={"fields": sorted(data.keys())},
        )

        return success_response(user_schema.dump(current_user))


class ForgotPasswordResource(Resource):
    """Always responds with the same generic success message — see
    app/services/password_reset.py's request_password_reset(), which
    never raises and never reveals whether the email matched an account.
    """

    # Conservative but not punitive: a real user mistyping/retrying a
    # forgot-password request a couple of times in an hour is fine; a
    # script trying to enumerate accounts or mail-bomb an address is not.
    # Same per-IP shared-store limiter as LoginResource above.
    @limiter.limit(limit("password_reset_request"))
    def post(self):
        data = forgot_password_schema.load(request.get_json(silent=True) or {})
        request_password_reset(data["email"])
        return success_response(
            None,
            message="If an account exists for that email, we have sent password reset instructions.",
        )


class ResetPasswordResource(Resource):
    """Consumes a one-time reset token (see
    app/services/password_reset.py) and sets a new password. Does NOT
    log the user in — no tokens are issued here; see the schema module
    docstring/spec for why (this is a recovery action, not a session
    start, and the user should prove the new password back at /login).
    """

    @limiter.limit(limit("password_reset_submit"))
    def post(self):
        data = reset_password_schema.load(request.get_json(silent=True) or {})

        if data["new_password"] != data["confirm_password"]:
            return error_response(
                "New password and confirmation do not match.", 422, code="password_mismatch"
            )

        reset_password(data["token"], data["new_password"])

        return success_response(
            None, message="Your password has been reset. You may now sign in with your new password."
        )


class VerifyEmailResource(Resource):
    """POST {token}: the emailed link opens a page whose button posts the
    token, so a mail scanner opening the link can't verify on anyone's behalf.
    Public: it proves control of the inbox, nothing more."""

    @limiter.limit(limit("email_verification_confirm"))
    def post(self):
        outcome, _user = verify_token((request.get_json(silent=True) or {}).get("token"))
        if outcome in ("verified", "already_verified"):
            return success_response({"result": outcome}, message="Your email address is confirmed.")
        if outcome == "expired":
            raise ApiError("This link has expired. Sign in and ask for a new one.", 410, code="verification_expired")
        if outcome == "superseded":
            raise ApiError("A newer link was sent. Please use the most recent email.", 410,
                           code="verification_superseded")
        raise ApiError("This link isn't valid.", 404, code="verification_invalid")


class ResendVerificationResource(Resource):
    """POST: email a fresh verification link to the signed-in account's own
    address. Plain @jwt_required() so an unverified account can use it; also
    how existing members verify. Shared-store rate limit."""

    @jwt_required()
    @limiter.limit(limit("email_verification_resend"))
    def post(self):
        if not current_user or not current_user.is_active:
            return error_response("Account is inactive or no longer exists.", 403, code="forbidden")
        if current_user.email_verified_at is not None:
            return success_response({"result": "already_verified"}, message="Your email address is already confirmed.")
        sent = send_verification(current_user)
        db.session.commit()
        if not sent:
            raise ApiError("We couldn't send the email just now. Please try again in a few minutes.", 503,
                           code="email_send_failed")
        return success_response({"result": "sent"}, message="We've emailed you a new link.")


api.add_resource(RegisterResource, "/register")
api.add_resource(VerifyEmailResource, "/verify-email")
api.add_resource(ResendVerificationResource, "/verify-email/resend")
api.add_resource(LoginResource, "/login")
api.add_resource(RefreshResource, "/refresh")
api.add_resource(LogoutResource, "/logout")
api.add_resource(MeResource, "/me")
api.add_resource(ChangePasswordResource, "/change-password")
api.add_resource(ForgotPasswordResource, "/forgot-password")
api.add_resource(ResetPasswordResource, "/reset-password")
