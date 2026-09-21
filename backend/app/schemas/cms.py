from marshmallow import fields, validate

from app.extensions import ma
from app.models.cms import HomepageModule, SiteSetting, SocialLink


class HomepageModuleSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = HomepageModule
        load_instance = False


class MenuItemSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    label = fields.String()
    url = fields.String()
    sort_order = fields.Integer()
    visible = fields.Boolean()
    children = fields.List(fields.Nested(lambda: MenuItemSchema()), dump_only=True)


class MenuSchema(ma.Schema):
    id = fields.Integer(dump_only=True)
    key = fields.String()
    heading = fields.String(allow_none=True)
    items = fields.Method("get_items")

    def get_items(self, obj):
        return MenuItemSchema(many=True).dump(obj.top_level_items())


class SiteSettingSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = SiteSetting
        load_instance = False


class SocialLinkSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = SocialLink
        load_instance = False


class HomepageModuleInputSchema(ma.Schema):
    type = fields.String(required=True)
    enabled = fields.Boolean(required=False, load_default=True)
    heading = fields.String(required=False, allow_none=True)
    subheading = fields.String(required=False, allow_none=True)
    selection_mode = fields.String(required=False, allow_none=True, data_key="selectionMode")
    config = fields.Dict(required=False, load_default=dict)


class HomepageInputSchema(ma.Schema):
    modules = fields.List(fields.Nested(HomepageModuleInputSchema), required=True)


class MenuItemInputSchema(ma.Schema):
    label = fields.String(required=True, validate=validate.Length(min=1, max=100))
    url = fields.String(required=True, validate=validate.Length(min=1, max=300))
    visible = fields.Boolean(required=False, load_default=True)
    children = fields.List(fields.Nested(lambda: MenuItemInputSchema()), required=False, load_default=list)


class MenuInputSchema(ma.Schema):
    key = fields.String(required=True)
    heading = fields.String(required=False, allow_none=True)
    items = fields.List(fields.Nested(MenuItemInputSchema), required=False, load_default=list)


class NavigationInputSchema(ma.Schema):
    menus = fields.List(fields.Nested(MenuInputSchema), required=True)
    social_links = fields.List(fields.Dict(), required=False, load_default=list, data_key="socialLinks")


class SiteSettingsInputSchema(ma.Schema):
    settings = fields.Dict(required=True)
