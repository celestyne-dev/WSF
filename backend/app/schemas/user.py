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
