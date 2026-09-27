from flask import Blueprint, current_app
from flask_restful import Api, Resource

from app.models.cms import HomepageModule, Menu, SocialLink
from app.models.geography import Country
from app.schemas.cms import HomepageModuleSchema, SocialLinkSchema
from app.schemas.geography import CountrySchema
from app.services.footer import build_public_footer
from app.services.navigation import serialize_public_menu
from app.services.site_settings import get_site_identity_resolved, get_visible_social_links
from app.utils.responses import success_response

# Read-only, unauthenticated endpoints the public frontend needs before a
# more specific namespace exists for them (site-wide reference data,
# homepage layout, navigation). Article/topic/etc. listings get their own
# namespaces once built.
public_bp = Blueprint("public", __name__)
api = Api(public_bp)

country_schema = CountrySchema()
homepage_module_schema = HomepageModuleSchema()
social_link_schema = SocialLinkSchema()


def _public_media_ref(media):
    """A deliberately minimal public projection of a Media row — id,
    servable URL, alt text, dimensions, and named variants — never
    file_path/stored_filename/uploaded_by_id (unlike MediaSchema, which
    dumps every column and is only ever used elsewhere behind an admin
    permission or on the pre-existing, unrelated Homepage endpoint this
    task doesn't touch). Keys match every other media-carrying public
    payload's snake_case convention (Article.hero_media, HomepageModule.
    media, ...) so the frontend's one shared mapMediaRef() handles this
    the same way as any other media reference, with no separate mapper.
    """
    if media is None:
        return None
    return {
        "id": media.id,
        "public_url": media.public_url,
        "alt_text": media.alt_text,
        "width": media.width,
        "height": media.height,
        "variants": {v.variant: {"url": v.public_url, "width": v.width, "height": v.height} for v in media.variants},
    }


class CountriesResource(Resource):
    def get(self):
        countries = Country.query.order_by(Country.name).all()
        return success_response(country_schema.dump(countries, many=True))


class HomepageResource(Resource):
    def get(self):
        modules = HomepageModule.query.filter_by(enabled=True).order_by(HomepageModule.sort_order).all()
        # A cheap cache-invalidation hint for a CDN in front of this
        # high-traffic endpoint — no caching infrastructure added here,
        # just a deterministic timestamp a cache layer could key on.
        updated_at = max((m.updated_at for m in modules), default=None)
        meta = {"updatedAt": updated_at.isoformat() if updated_at else None}
        return success_response(homepage_module_schema.dump(modules, many=True), meta=meta)


class NavigationResource(Resource):
    def get(self):
        menus = {menu.key: serialize_public_menu(menu) for menu in Menu.query.all()}
        # `visible` was added to SocialLink for Footer CMS (the only public
        # consumer of a *hidden* social link's non-existence, until now) —
        # filtered here too since MobileNav also reads this endpoint's
        # socialLinks for its own social row and must honor the same
        # visibility toggle Footer CMS's admin UI controls.
        social_links = SocialLink.query.filter_by(visible=True).order_by(SocialLink.sort_order).all()
        return success_response({"menus": menus, "socialLinks": social_link_schema.dump(social_links, many=True)})


class SiteSettingsResource(Resource):
    """The one authoritative, public-safe global configuration payload —
    site identity, branding, public contact, real (visible) social
    profile URLs, and SEO defaults. See app/services/site_settings.py.

    This used to be a raw dump of every SiteSetting row, but nothing on
    the frontend ever read that shape (Partnerships' own "audience_stats"
    numbers are served by their own dedicated /partnerships/audience
    endpoint, not this one) — replacing it here is a safe, additive
    change: the {site, branding, contact, social, seo} shape below is
    entirely new, not a breaking change to something already consumed.
    """

    def get(self):
        identity = get_site_identity_resolved()
        social_links = get_visible_social_links()
        return success_response(
            {
                "site": {
                    "name": identity["site_name"],
                    "shortName": identity["short_name"],
                    "tagline": identity["tagline"],
                    # The canonical public origin stays environment-controlled
                    # (FRONTEND_URL) — never an admin-editable field, so a typo
                    # in Site Settings can never break routing/CORS. This is
                    # the display-only value CMS consumers (canonical links,
                    # JSON-LD) read.
                    "url": current_app.config["FRONTEND_URL"],
                },
                "branding": {"logo": _public_media_ref(identity["logo"])},
                "contact": {"email": identity["contact_email"]},
                "social": social_link_schema.dump(social_links, many=True),
                "seo": {
                    "defaultTitle": identity["seo_default_title"],
                    "defaultDescription": identity["seo_default_description"],
                    "defaultOgImage": _public_media_ref(identity["og_image"]),
                },
            }
        )


class FooterResource(Resource):
    """A dedicated, lightweight footer payload — separate from
    NavigationResource even though footer groups are Menu/MenuItem rows
    under the hood (see app/services/footer.py), so the footer's shape
    (settings + groups + socialLinks) doesn't get tangled up with
    Navigation's own primary/secondary/menus dict. One request, no
    admin metadata, no hidden/invalid items or unpublished settings —
    build_public_footer() already filters all of that out.
    """

    def get(self):
        return success_response(build_public_footer())


api.add_resource(CountriesResource, "/countries")
api.add_resource(HomepageResource, "/homepage")
api.add_resource(NavigationResource, "/navigation")
api.add_resource(FooterResource, "/footer")
api.add_resource(SiteSettingsResource, "/settings")
