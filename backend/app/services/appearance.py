"""Public design system ("Studio -> Settings -> Appearance"), phase 1:
global corner style only.

Storage: one row in the existing generic SiteSetting key/value table
(key="appearance"), like site_identity and payment settings: no new table,
no migration. Only controlled enum presets are ever stored (never raw CSS
values); anything unknown resolves to the default.

The frontend turns the preset into CSS design tokens (frontend/src/
index.css, [data-wsf-corners="..."] on <html>). The server writes that same
attribute into every HTML response (spa_shell), so the first paint already
uses the saved corners and React only agrees with it.
"""
from app.extensions import db
from app.models.cms import SiteSetting

APPEARANCE_KEY = "appearance"

# Square preserves today's site: before this setting existed, every card,
# button, callout, form field and Article image on the public site was
# square (only a few newer floating panels were rounded).
CORNER_STYLES = ("square", "subtle", "soft", "rounded")
DEFAULT_CORNER_STYLE = "square"


class AppearanceError(ValueError):
    pass


def resolve_corner_style(value):
    return value if value in CORNER_STYLES else DEFAULT_CORNER_STYLE


def get_appearance():
    setting = db.session.get(SiteSetting, APPEARANCE_KEY)
    raw = setting.value if setting is not None and isinstance(setting.value, dict) else {}
    return {"corner_style": resolve_corner_style(raw.get("corner_style"))}


def save_appearance(data):
    """Validates and stores the appearance payload (camelCase from Studio).
    Unknown keys and values are rejected (422), never stored."""
    if not isinstance(data, dict):
        raise AppearanceError("appearance must be an object.")
    unknown = set(data) - {"cornerStyle"}
    if unknown:
        raise AppearanceError(f"Unknown appearance setting(s): {', '.join(sorted(unknown))}.")
    corner = data.get("cornerStyle", DEFAULT_CORNER_STYLE)
    if corner not in CORNER_STYLES:
        raise AppearanceError(f"cornerStyle must be one of: {', '.join(CORNER_STYLES)}.")
    setting = db.session.get(SiteSetting, APPEARANCE_KEY)
    if setting is None:
        setting = SiteSetting(key=APPEARANCE_KEY)
        db.session.add(setting)
    setting.value = {"corner_style": corner}
    return get_appearance_payload_from({"corner_style": corner})


def get_appearance_payload_from(appearance):
    return {"cornerStyle": appearance["corner_style"]}


def public_appearance_payload():
    """The only appearance data the public site receives."""
    return get_appearance_payload_from(get_appearance())
