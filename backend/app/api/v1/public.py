from flask import Blueprint
from flask_restful import Api, Resource

from app.models.cms import HomepageModule, Menu, SiteSetting, SocialLink
from app.models.geography import Country
from app.schemas.cms import HomepageModuleSchema, MenuSchema, SiteSettingSchema, SocialLinkSchema
from app.schemas.geography import CountrySchema
from app.utils.responses import success_response

# Read-only, unauthenticated endpoints the public frontend needs before a
# more specific namespace exists for them (site-wide reference data,
# homepage layout, navigation). Article/topic/etc. listings get their own
# namespaces once built.
public_bp = Blueprint("public", __name__)
api = Api(public_bp)

country_schema = CountrySchema()
homepage_module_schema = HomepageModuleSchema()
menu_schema = MenuSchema()
site_setting_schema = SiteSettingSchema()
social_link_schema = SocialLinkSchema()


class CountriesResource(Resource):
    def get(self):
        countries = Country.query.order_by(Country.name).all()
        return success_response(country_schema.dump(countries, many=True))


class HomepageResource(Resource):
    def get(self):
        modules = HomepageModule.query.filter_by(enabled=True).order_by(HomepageModule.sort_order).all()
        return success_response(homepage_module_schema.dump(modules, many=True))


class NavigationResource(Resource):
    def get(self):
        menus = {menu.key: menu_schema.dump(menu) for menu in Menu.query.all()}
        social_links = SocialLink.query.order_by(SocialLink.sort_order).all()
        return success_response({"menus": menus, "socialLinks": social_link_schema.dump(social_links, many=True)})


class SiteSettingsResource(Resource):
    def get(self):
        settings = SiteSetting.query.all()
        return success_response({setting.key: setting.value for setting in settings})


api.add_resource(CountriesResource, "/countries")
api.add_resource(HomepageResource, "/homepage")
api.add_resource(NavigationResource, "/navigation")
api.add_resource(SiteSettingsResource, "/settings")
