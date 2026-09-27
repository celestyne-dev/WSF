"""Site Settings / Global Configuration — the one authoritative source for
global site identity, branding references, public contact information,
and SEO defaults.

Deliberately narrow: this does NOT own Navigation structure, Footer link
groups/social links, Homepage modules, or Page/Article content — those
stay exactly where they already live (see app/services/{navigation,
footer,homepage,pages}.py). It also does not own "audience_stats" (the
Partnerships/media-kit numbers also stored as a SiteSetting row) — that
key is read/written by app/api/v1/partnerships.py and passed through
AdminSettingsResource unvalidated, exactly as before this module existed.

Storage: a single row in the existing generic SiteSetting key/value table
(key="site_identity"), not a new model/migration — this is already the
established pattern for small global config (see FOOTER_SETTINGS_KEY),
and a whole-object full-replace on save (like Footer/Homepage's own
saves) keeps a single admin Save action atomic and avoids partial-update
ambiguity within this one blob.

Social profile URLs are deliberately NOT part of this module: SocialLink
rows are already fully owned (created/edited/reordered/hidden) by Footer
CMS's admin UI (see app/services/footer.py, AdminFooterResource). Adding
a second write path here for the same rows would risk exactly what this
task is meant to prevent — two editable copies of the same LinkedIn URL,
one of which silently loses on the next unrelated save. Instead, this
module *reads* the same real SocialLink rows Footer already manages
(get_visible_social_links) so the public payload and Organization
structured data reflect the single source of truth without duplicating
it.
"""
from app.extensions import db
from app.models.cms import SiteSetting, SocialLink
from app.models.media import Media

SITE_IDENTITY_KEY = "site_identity"

DEFAULT_SITE_IDENTITY = {
    "site_name": "Women Shaping Futures",
    "short_name": None,
    "tagline": None,
    "contact_email": None,
    "logo_media_id": None,
    "og_image_media_id": None,
    "seo_default_title": None,
    "seo_default_description": None,
}


def get_site_identity_raw():
    """The stored site_identity dict, merged over the structural defaults
    so a field an admin has never saved is None rather than a KeyError —
    never a fabricated value for contact/social-shaped fields (only
    site_name has a real, non-fake default: WSF's own public name).
    """
    setting = db.session.get(SiteSetting, SITE_IDENTITY_KEY)
    merged = dict(DEFAULT_SITE_IDENTITY)
    if setting is not None and isinstance(setting.value, dict):
        merged.update(setting.value)
    return merged


def get_site_identity_resolved():
    """get_site_identity_raw() with logo_media_id/og_image_media_id
    resolved to real Media rows (never a bare id or filesystem path) for
    admin/public dumping.
    """
    raw = get_site_identity_raw()
    logo = db.session.get(Media, raw["logo_media_id"]) if raw.get("logo_media_id") else None
    og_image = db.session.get(Media, raw["og_image_media_id"]) if raw.get("og_image_media_id") else None
    return {**raw, "logo": logo, "og_image": og_image}


def save_site_identity(data):
    setting = db.session.get(SiteSetting, SITE_IDENTITY_KEY)
    if setting is None:
        setting = SiteSetting(key=SITE_IDENTITY_KEY)
        db.session.add(setting)
    setting.value = {
        "site_name": data["site_name"],
        "short_name": data.get("short_name"),
        "tagline": data.get("tagline"),
        "contact_email": data.get("contact_email"),
        "logo_media_id": data.get("logo_media_id"),
        "og_image_media_id": data.get("og_image_media_id"),
        "seo_default_title": data.get("seo_default_title"),
        "seo_default_description": data.get("seo_default_description"),
    }


def get_visible_social_links():
    return SocialLink.query.filter_by(visible=True).order_by(SocialLink.sort_order).all()
