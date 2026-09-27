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
