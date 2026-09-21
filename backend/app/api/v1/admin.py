from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.cms import HomepageModule, Menu, SiteSetting
from app.models.user import Role, User
from app.schemas.cms import (
    HomepageInputSchema,
    HomepageModuleSchema,
    MenuSchema,
    NavigationInputSchema,
    SiteSettingsInputSchema,
)
from app.schemas.user import RoleSchema, UserSchema
from app.services.cms import replace_homepage_modules, replace_menu, replace_social_links, upsert_site_settings
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import success_response

admin_bp = Blueprint("admin", __name__)
api = Api(admin_bp)

user_schema = UserSchema()
role_schema = RoleSchema()
homepage_module_schema = HomepageModuleSchema()
menu_schema = MenuSchema()


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


class AdminHomepageResource(Resource):
    """The homepage builder always reads/writes the full ordered module
    list — see app/services/cms.py:replace_homepage_modules.
    """

    @permission_required("settings.manage")
    def get(self):
        modules = HomepageModule.query.order_by(HomepageModule.sort_order).all()
        return success_response(homepage_module_schema.dump(modules, many=True))

    @permission_required("settings.manage")
    def put(self):
        data = HomepageInputSchema().load(request.get_json(silent=True) or {})
        replace_homepage_modules(data["modules"])
        db.session.commit()
        modules = HomepageModule.query.order_by(HomepageModule.sort_order).all()
        return success_response(homepage_module_schema.dump(modules, many=True))


class AdminNavigationResource(Resource):
    @permission_required("settings.manage")
    def get(self):
        menus = Menu.query.all()
        return success_response(menu_schema.dump(menus, many=True))

    @permission_required("settings.manage")
    def put(self):
        data = NavigationInputSchema().load(request.get_json(silent=True) or {})
        for menu_data in data["menus"]:
            replace_menu(menu_data["key"], menu_data.get("heading"), menu_data.get("items", []))
        if data.get("social_links"):
            replace_social_links(data["social_links"])
        db.session.commit()

        menus = Menu.query.all()
        return success_response(menu_schema.dump(menus, many=True))


class AdminSettingsResource(Resource):
    @permission_required("settings.manage")
    def get(self):
        settings = SiteSetting.query.all()
        return success_response({setting.key: setting.value for setting in settings})

    @permission_required("settings.manage")
    def put(self):
        data = SiteSettingsInputSchema().load(request.get_json(silent=True) or {})
        upsert_site_settings(data["settings"])
        db.session.commit()

        settings = SiteSetting.query.all()
        return success_response({setting.key: setting.value for setting in settings})


api.add_resource(AdminUserListResource, "/users")
api.add_resource(AdminRoleListResource, "/roles")
api.add_resource(AdminHomepageResource, "/homepage")
api.add_resource(AdminNavigationResource, "/navigation")
api.add_resource(AdminSettingsResource, "/settings")
