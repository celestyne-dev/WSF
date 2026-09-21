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

from app.extensions import db
from app.models.token_blocklist import TokenBlocklist
from app.models.user import Role, User
from app.schemas.user import LoginSchema, RegisterSchema, UserSchema
from app.services.audit import log_action
from app.utils.responses import error_response, success_response

auth_bp = Blueprint("auth", __name__)
api = Api(auth_bp)

register_schema = RegisterSchema()
login_schema = LoginSchema()
user_schema = UserSchema()


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


class MeResource(Resource):
    @jwt_required()
    def get(self):
        return success_response(user_schema.dump(current_user))


api.add_resource(RegisterResource, "/register")
api.add_resource(LoginResource, "/login")
api.add_resource(RefreshResource, "/refresh")
api.add_resource(LogoutResource, "/logout")
api.add_resource(MeResource, "/me")
