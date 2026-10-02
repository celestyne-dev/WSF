from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    current_user,
    get_jwt,
    jwt_required,
)
from flask_restful import Api, Resource

from app.extensions import db, limiter
from app.models.token_blocklist import TokenBlocklist
from app.models.user import Role, User
from app.schemas.user import ChangePasswordSchema, LoginSchema, RegisterSchema, UserSchema
from app.services.audit import log_action
from app.utils.responses import error_response, success_response

auth_bp = Blueprint("auth", __name__)
api = Api(auth_bp)

register_schema = RegisterSchema()
login_schema = LoginSchema()
user_schema = UserSchema()
change_password_schema = ChangePasswordSchema()


class RegisterResource(Resource):
    def post(self):
        data = register_schema.load(request.get_json(silent=True) or {})
        email = data["email"].lower()

        if User.query.filter_by(email=email).first():
            return error_response("An account with this email already exists.", 409, code="email_taken")

        user = User(
            email=email,
            first_name=data["first_name"],
            last_name=data["last_name"],
            country_code=data.get("country_code"),
        )
        user.set_password(data["password"])

        member_role = Role.query.filter_by(name="member").first()
        if member_role:
            user.roles.append(member_role)

        db.session.add(user)
        db.session.commit()
        log_action(user, "user.register", "User", user.id)

        return success_response(
            {
                "user": user_schema.dump(user),
                "access_token": create_access_token(identity=user),
                "refresh_token": create_refresh_token(identity=user),
            },
            status=201,
        )


class LoginResource(Resource):
    # Login brute-force protection (see task spec's RATE LIMITING/LOGIN
    # BRUTE FORCE sections): conservative enough to not bother a real user
    # mistyping a password a few times, tight enough to make scripted
    # credential-stuffing slow. Per-IP, in-memory (see app/extensions.py's
    # limiter setup for the multi-worker-process caveat) — this is not
    # account lockout (no account-level state is written), so it can't be
    # used to lock a legitimate user out by repeatedly failing their login.
    @limiter.limit("10 per minute")
    def post(self):
        data = login_schema.load(request.get_json(silent=True) or {})
        user = User.query.filter_by(email=data["email"].lower()).first()

        if not user or not user.check_password(data["password"]):
            return error_response("Invalid email or password.", 401, code="invalid_credentials")
        if not user.is_active:
            return error_response("This account has been deactivated.", 403, code="account_inactive")

        user.last_login_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action(user, "user.login", "User", user.id)

        return success_response(
            {
                "user": user_schema.dump(user),
                "access_token": create_access_token(identity=user),
                "refresh_token": create_refresh_token(identity=user),
            }
        )


class RefreshResource(Resource):
    @jwt_required(refresh=True)
    def post(self):
        # Mirrors LoginResource's is_active check: a deactivated account
        # must not be able to keep minting fresh access tokens off a
        # refresh token that predates the deactivation.
        if not current_user or not current_user.is_active:
            return error_response("This account has been deactivated.", 403, code="account_inactive")
        return success_response({"access_token": create_access_token(identity=current_user)})


class LogoutResource(Resource):
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

        current_user.set_password(data["new_password"])
        current_user.must_change_password = False
        db.session.commit()
        # No `changes` payload — nothing here is safe or useful to audit
        # beyond the fact that it happened (log_action's own redaction in
        # app/services/audit.py would scrub a password value anyway, but
        # this endpoint never hands it one to begin with).
        log_action(current_user, "user.password_change", "User", current_user.id)

        return success_response(user_schema.dump(current_user))


class MeResource(Resource):
    @jwt_required()
    def get(self):
        if not current_user or not current_user.is_active:
            return error_response("Account is inactive or no longer exists.", 403, code="forbidden")
        return success_response(user_schema.dump(current_user))


api.add_resource(RegisterResource, "/register")
api.add_resource(LoginResource, "/login")
api.add_resource(RefreshResource, "/refresh")
api.add_resource(LogoutResource, "/logout")
api.add_resource(MeResource, "/me")
api.add_resource(ChangePasswordResource, "/change-password")
