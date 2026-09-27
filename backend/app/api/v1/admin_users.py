"""Admin CMS User / Role / Permission administration.

Split out of app/api/v1/admin.py (same precedent as admin_taxonomy.py) —
registered under the same "/api/v1/admin" prefix, so existing URLs
(/admin/users, /admin/roles) are unchanged.

Scope: internal CMS staff accounts only (app/models/user.py:User) — never
Community Members, public People/Authors, Newsletter subscribers, or
Mentorship/Submission/Nomination applicants. See
app/services/user_admin.py for the privilege-escalation and last-active-
Super-Admin rules enforced here.
"""

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.user import Permission, Role, User
from app.schemas.user import (
    AdminUserCreateSchema,
    AdminUserUpdateSchema,
    PermissionSchema,
    RoleAssignmentSchema,
    RoleWithCountSchema,
    UserSchema,
    UserStatusSchema,
)
from app.services.audit import log_action
from app.services.user_admin import (
    UserAdminError,
    assign_user_roles,
    create_staff_user,
    reset_user_password,
    set_user_status,
    update_user_identity,
)
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

admin_users_bp = Blueprint("admin_users", __name__)
api = Api(admin_users_bp)

user_schema = UserSchema()
role_schema = RoleWithCountSchema()
permission_schema = PermissionSchema()

# GET (view-only) accepts either the narrower users.view or the broader
# users.manage/roles.manage — a future read-only role only ever needs
# users.view granted, per spec.
VIEW_PERMISSIONS = ("users.view", "users.manage", "roles.manage")


def _user_query_with_roles():
    return User.query.options(selectinload(User.roles).selectinload(Role.permissions))


def _apply_user_filters(query):
    is_active = request.args.get("is_active")
    if is_active is not None and is_active != "":
        query = query.filter(User.is_active.is_(is_active.lower() in ("true", "1", "yes")))

    role = request.args.get("role")
    if role:
        query = query.filter(User.roles.any(Role.name == role))

    return apply_search(query, User, request.args, ["email", "first_name", "last_name"])


def _user_admin_error_to_api_error(exc):
    status = 409 if exc.code in ("last_super_admin", "email_taken") else 403
    if exc.code == "validation_error":
        status = 422
    return ApiError(str(exc), status, code=exc.code)


class AdminUserListResource(Resource):
    @permission_required(*VIEW_PERMISSIONS)
    def get(self):
        query = _apply_user_filters(_user_query_with_roles().order_by(User.created_at.desc()))
        result = paginate(query, user_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("users.manage")
    def post(self):
        data = AdminUserCreateSchema().load(request.get_json(silent=True) or {})
        try:
            user, temporary_password = create_staff_user(
                email=data["email"],
                first_name=data["first_name"],
                last_name=data["last_name"],
                role_names=data["role_names"],
                is_active=data["is_active"],
                actor=current_user,
            )
        except UserAdminError as exc:
            raise _user_admin_error_to_api_error(exc)

        log_action(
            current_user,
            "user.create",
            "User",
            entity_id=user.id,
            changes={"email": user.email, "role_names": data["role_names"], "is_active": user.is_active},
        )
        payload = user_schema.dump(user)
        # Returned exactly once, in this creation response only — never
        # logged, audited, or retrievable again. If lost, use the password
        # reset action instead of re-creating the account.
        payload["temporary_password"] = temporary_password
        return success_response(payload, status=201)


class AdminUserDetailResource(Resource):
    @permission_required(*VIEW_PERMISSIONS)
    def get(self, user_id):
        user = _user_query_with_roles().filter_by(id=user_id).first()
        if not user:
            raise ApiError("User not found.", 404, code="not_found")
        return success_response(user_schema.dump(user))

    @permission_required("users.manage")
    def patch(self, user_id):
        user = db.session.get(User, user_id)
        if not user:
            raise ApiError("User not found.", 404, code="not_found")

        data = AdminUserUpdateSchema().load(request.get_json(silent=True) or {}, partial=True)
        try:
            update_user_identity(user, **data)
        except UserAdminError as exc:
            raise _user_admin_error_to_api_error(exc)

        log_action(current_user, "user.update", "User", entity_id=user.id, changes=data)
        return success_response(user_schema.dump(user))


class AdminUserStatusResource(Resource):
    @permission_required("users.manage")
    def patch(self, user_id):
        user = db.session.get(User, user_id)
        if not user:
            raise ApiError("User not found.", 404, code="not_found")

        data = UserStatusSchema().load(request.get_json(silent=True) or {})
        try:
            set_user_status(user, data["is_active"], actor=current_user)
        except UserAdminError as exc:
            raise _user_admin_error_to_api_error(exc)

        log_action(
            current_user,
            "user.activate" if data["is_active"] else "user.deactivate",
            "User",
            entity_id=user.id,
        )
        return success_response(user_schema.dump(user))


class AdminUserRolesResource(Resource):
    @permission_required("roles.manage")
    def put(self, user_id):
        user = _user_query_with_roles().filter_by(id=user_id).first()
        if not user:
            raise ApiError("User not found.", 404, code="not_found")

        data = RoleAssignmentSchema().load(request.get_json(silent=True) or {})
        try:
            assign_user_roles(user, data["role_names"], actor=current_user)
        except UserAdminError as exc:
            raise _user_admin_error_to_api_error(exc)

        log_action(current_user, "user.roles_update", "User", entity_id=user.id, changes={"role_names": data["role_names"]})
        return success_response(user_schema.dump(user))


class AdminUserPasswordResetResource(Resource):
    """Admin-set temporary password — see app/services/user_admin.py. No
    email-delivery flow exists in this app, so this is the whole reset
    path: an admin generates a new temporary password here and relays it
    to the staff member out-of-band (never through this API response's
    audit trail, and never a second time — if lost, reset again).
    """

    @permission_required("users.manage")
    def post(self, user_id):
        user = db.session.get(User, user_id)
        if not user:
            raise ApiError("User not found.", 404, code="not_found")

        temporary_password = reset_user_password(user)
        log_action(current_user, "user.password_reset", "User", entity_id=user.id)
        return success_response({"temporary_password": temporary_password})


class AdminRoleListResource(Resource):
    @permission_required(*VIEW_PERMISSIONS)
    def get(self):
        roles = Role.query.order_by(Role.name).all()
        counts = dict(
            db.session.query(Role.id, func.count(User.id))
            .select_from(Role)
            .join(Role.users)
            .group_by(Role.id)
            .all()
        )
        dumped = role_schema.dump(roles, many=True)
        for role, row in zip(roles, dumped):
            row["user_count"] = counts.get(role.id, 0)
        return success_response(dumped)


class AdminRoleDetailResource(Resource):
    @permission_required(*VIEW_PERMISSIONS)
    def get(self, role_id):
        role = db.session.get(Role, role_id)
        if not role:
            raise ApiError("Role not found.", 404, code="not_found")
        data = role_schema.dump(role)
        data["user_count"] = User.query.filter(User.roles.any(Role.id == role.id)).count()
        return success_response(data)


class AdminPermissionListResource(Resource):
    """Read-only — permissions are code-defined (see app/services/rbac.py)
    so ordinary admins can never invent an arbitrary permission string.
    """

    @permission_required(*VIEW_PERMISSIONS)
    def get(self):
        permissions = Permission.query.order_by(Permission.name).all()
        return success_response(permission_schema.dump(permissions, many=True))


api.add_resource(AdminUserListResource, "/users")
api.add_resource(AdminUserDetailResource, "/users/<int:user_id>")
api.add_resource(AdminUserStatusResource, "/users/<int:user_id>/status")
api.add_resource(AdminUserRolesResource, "/users/<int:user_id>/roles")
api.add_resource(AdminUserPasswordResetResource, "/users/<int:user_id>/reset-password")
api.add_resource(AdminRoleListResource, "/roles")
api.add_resource(AdminRoleDetailResource, "/roles/<int:role_id>")
api.add_resource(AdminPermissionListResource, "/permissions")
