from marshmallow import fields, validate

from app.extensions import ma
from app.models.user import Permission, Role, User


class PermissionSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Permission
        load_instance = False


class RoleSchema(ma.SQLAlchemyAutoSchema):
    permissions = ma.Nested(PermissionSchema, many=True, dump_only=True)

    class Meta:
        model = Role
        load_instance = False


class RoleWithCountSchema(RoleSchema):
    """Only for the Admin Roles list/detail endpoints — never nested under
    UserSchema, where dumping a user_count per role on every listed user
    would mean one extra query per role per row (see admin_users.py, which
    computes counts once via a single grouped query and merges them in
    rather than a Method field that would re-query per role here).
    """

    user_count = fields.Integer(dump_only=True)


class AdminUserCreateSchema(ma.Schema):
    email = fields.Email(required=True)
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    role_names = fields.List(fields.String(), required=False, load_default=list)
    is_active = fields.Boolean(required=False, load_default=True)


class AdminUserUpdateSchema(ma.Schema):
    first_name = fields.String(required=False, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=False, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=False)
    country_code = fields.String(required=False, allow_none=True, validate=validate.Length(min=2, max=10))


class UserStatusSchema(ma.Schema):
    is_active = fields.Boolean(required=True)


class RoleAssignmentSchema(ma.Schema):
    role_names = fields.List(fields.String(), required=True)


class UserSchema(ma.SQLAlchemyAutoSchema):
    roles = ma.Nested(RoleSchema, many=True, dump_only=True)
    full_name = fields.String(dump_only=True)
    # SQLAlchemyAutoSchema's default include_fk=False silently drops every
    # FK column (country_code, avatar_media_id) from the auto-generated
    # field set — declared explicitly here so /auth/me and /account can
    # actually see a user's own country (avatar_media_id stays out: no
    # avatar self-service in this module, see spec).
    country_code = fields.String(dump_only=True)

    class Meta:
        model = User
        load_instance = False
        exclude = ("password_hash",)


class RegisterSchema(ma.Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True, validate=validate.Length(min=8))
    first_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=True, validate=validate.Length(min=1, max=100))
    country_code = fields.String(required=False, allow_none=True, validate=validate.Length(min=2, max=10))


class LoginSchema(ma.Schema):
    email = fields.Email(required=True)
    password = fields.String(required=True, load_only=True)


class ChangePasswordSchema(ma.Schema):
    # min=8 mirrors RegisterSchema's own password policy above — the one
    # rule a self-chosen password must meet, same as public registration.
    current_password = fields.String(required=True, load_only=True)
    new_password = fields.String(required=True, load_only=True, validate=validate.Length(min=8))
    confirm_password = fields.String(required=True, load_only=True)


class ForgotPasswordSchema(ma.Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(ma.Schema):
    token = fields.String(required=True, validate=validate.Length(min=1))
    # min=8 mirrors RegisterSchema/ChangePasswordSchema's own password
    # policy — the one rule a password chosen through recovery must meet
    # too, same as everywhere else a user picks her own password.
    new_password = fields.String(required=True, load_only=True, validate=validate.Length(min=8))
    confirm_password = fields.String(required=True, load_only=True)


class SelfProfileUpdateSchema(ma.Schema):
    """PATCH /api/v1/auth/me — deliberately narrow: only the fields a
    public/staff account may edit about herself. No email, roles,
    permissions, is_active, is_verified, must_change_password, or any other
    admin/security field — see AdminUserUpdateSchema/AdminUserCreateSchema
    above for the separate admin-only path that can touch those.
    """

    first_name = fields.String(required=False, validate=validate.Length(min=1, max=100))
    last_name = fields.String(required=False, validate=validate.Length(min=1, max=100))
    display_name = fields.String(required=False, allow_none=True, validate=validate.Length(max=150))
    bio = fields.String(required=False, allow_none=True, validate=validate.Length(max=2000))
    country_code = fields.String(required=False, allow_none=True, validate=validate.Length(min=2, max=10))
