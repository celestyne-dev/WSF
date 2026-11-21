from flask import Blueprint, current_app
from flask_restful import Api, Resource

from app.models.cms import Menu, SocialLink
from app.models.geography import Country
from app.schemas.cms import HomepageModuleSchema, SocialLinkSchema
from app.schemas.geography import CountrySchema
from app.services.footer import build_public_footer
from app.services.homepage import get_enabled_homepage_modules, public_homepage_modules_payload
from app.services.navigation import serialize_public_menu
from app.services.appearance import public_appearance_payload
from app.services.engagement_settings import get_cookie_consent, get_newsletter_page, get_newsletter_popup
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
        modules = get_enabled_homepage_modules()
        # A cheap cache-invalidation hint for a CDN in front of this
        # high-traffic endpoint — no caching infrastructure added here,
        # just a deterministic timestamp a cache layer could key on.
        updated_at = max((m.updated_at for m in modules), default=None)
        meta = {"updatedAt": updated_at.isoformat() if updated_at else None}
        return success_response(public_homepage_modules_payload(modules), meta=meta)


class HandpickedResource(Resource):
    """GET /public/homepage/handpicked — the Handpicked section for the
    signed-in reader, from their Career Goals (deterministic; no tracking).
    Anonymous readers, or readers without goals, get `personalized: false`
    and keep the editorial selection already on the page. Never cached
    publicly and never a crawlable page."""

    def get(self):
        from flask_jwt_extended import current_user, verify_jwt_in_request

        from app.services.homepage_editorial import personalized_handpicked
        from app.services.spa_shell import _redact_internal_media_fields

        user = None
        try:
            verify_jwt_in_request(optional=True)
            user = current_user if current_user and current_user.is_active else None
        except Exception:
            user = None
        result = personalized_handpicked(user) if user is not None else None
        body = {"personalized": result is not None}
        if result is not None:
            body.update(_redact_internal_media_fields(result))
        payload, status = success_response(body)
        return payload, status, {"Cache-Control": "private, no-store"}


def public_navigation_payload():
    """GET /public/navigation's body; also embedded once in every server
    HTML page (spa_shell shell bootstrap) so the header's first frame
    already has the real navigation."""
    menus = {menu.key: serialize_public_menu(menu) for menu in Menu.query.all()}
    # Only visible social links: MobileNav reads socialLinks here and must
    # honor the Footer CMS visibility toggle.
    social_links = SocialLink.query.filter_by(visible=True).order_by(SocialLink.sort_order).all()
    return {"menus": menus, "socialLinks": social_link_schema.dump(social_links, many=True)}


class NavigationResource(Resource):
    def get(self):
        return success_response(public_navigation_payload())


def public_settings_payload():
    """GET /public/settings' body; also embedded in every server HTML page
    (spa_shell shell bootstrap)."""
    identity = get_site_identity_resolved()
    social_links = get_visible_social_links()
    return (
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
            # Controlled design presets only (app/services/appearance.py).
            "appearance": public_appearance_payload(),
            # Plain-text, validated engagement settings
            # (app/services/engagement_settings.py). No scripts or IDs.
            "newsletterPopup": get_newsletter_popup(),
            "newsletterPage": get_newsletter_page(),
            "cookieConsent": get_cookie_consent(),
            "seo": {
                "defaultTitle": identity["seo_default_title"],
                "defaultDescription": identity["seo_default_description"],
                "defaultOgImage": _public_media_ref(identity["og_image"]),
            },
        }
    )


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
        return success_response(public_settings_payload())


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
api.add_resource(HandpickedResource, "/homepage/handpicked")
api.add_resource(NavigationResource, "/navigation")
api.add_resource(FooterResource, "/footer")
api.add_resource(SiteSettingsResource, "/settings")
