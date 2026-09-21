from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.models.user import Role, User
from app.schemas.user import RoleSchema, UserSchema
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import success_response

admin_bp = Blueprint("admin", __name__)
api = Api(admin_bp)

user_schema = UserSchema()
role_schema = RoleSchema()


class AdminUserListResource(Resource):
    @permission_required("users.manage")
    def get(self):
        query = User.query.order_by(User.created_at.desc())
        query = apply_search(query, User, request.args, ["email", "first_name", "last_name"])
        result = paginate(query, user_schema)
        return success_response(result["items"], meta=result["meta"])


class AdminRoleListResource(Resource):
    @permission_required("users.manage")
    def get(self):
        roles = Role.query.order_by(Role.name).all()
        return success_response(role_schema.dump(roles, many=True))


api.add_resource(AdminUserListResource, "/users")
api.add_resource(AdminRoleListResource, "/roles")
