"""Studio -> Settings -> "Newsletter popup" and "Cookie consent".

Storage: rows in the existing generic SiteSetting key/value table (no new
table, no migration), like Appearance and Payments. Strictly validated:
numbers within ranges, plain text only (any markup is refused, never
stripped), unknown keys rejected. There is deliberately NO field for a
script, snippet, tag ID or URL: nothing an admin types here can execute.

Essential cookies cannot be switched off: the consent setting has no such
option. Only the banner copy and the consent VERSION are editable; raising
the version makes every visitor's stored choice stale, so they are asked
again (use it after a material change to the categories or the policy).
"""
import re

from app.extensions import db
from app.models.cms import SiteSetting

NEWSLETTER_POPUP_KEY = "newsletter_popup"
COOKIE_CONSENT_KEY = "cookie_consent"

# The newsletter signup wording version recorded with each subscription
# (NewsletterSubscriber.consent_version): bump when the consent sentence
# shown next to a signup form changes. Operational provenance only.
NEWSLETTER_CONSENT_VERSION = "newsletter-v1"
# The explicit, unchecked-by-default "also send me WSF Weekly" checkbox on
# other forms (resource download, community join, mentorship, nominations,
# story submissions): different wording, so a different version label.
NEWSLETTER_CHECKBOX_CONSENT_VERSION = "checkbox-opt-in-v1"

POPUP_DEFAULTS = {
    "enabled": True,
    "delaySeconds": 15,
    "scrollPercent": 45,
    "dismissDays": 14,
    "successDays": 365,
    "title": "WSF Weekly",
    "body": "Career moves, opportunities and women worth knowing, delivered to your inbox.",
    "ctaLabel": "Join WSF Weekly",
}
_POPUP_RANGES = {"delaySeconds": (0, 600), "scrollPercent": (0, 100), "dismissDays": (1, 365), "successDays": (1, 3650)}
_POPUP_TEXT = {"title": 80, "body": 240, "ctaLabel": 40}

CONSENT_DEFAULTS = {
    "bannerEnabled": True,
    "version": "1",
    "title": "We use cookies",
    "body": ("We use essential technologies to make WSF work. With your permission, we may also use analytics "
             "and marketing technologies to understand how the site is used and improve our content."),
}
_CONSENT_TEXT = {"title": 80, "body": 400}
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,19}$")
_MARKUP_RE = re.compile(r"[<>]|javascript:|on\w+\s*=", re.IGNORECASE)


class EngagementSettingsError(ValueError):
    pass


def _stored(key):
    setting = db.session.get(SiteSetting, key)
    return setting.value if setting is not None and isinstance(setting.value, dict) else {}


def _plain(value, label, limit):
    if not isinstance(value, str) or not value.strip():
        raise EngagementSettingsError(f"{label} is required.")
    value = value.strip()
    if len(value) > limit:
        raise EngagementSettingsError(f"{label} must be {limit} characters or fewer.")
    if _MARKUP_RE.search(value):
        raise EngagementSettingsError(f"{label} must be plain text (no HTML or scripts).")
    return value


def _merge(defaults, stored):
    out = dict(defaults)
    for k, v in stored.items():
        if k in defaults and isinstance(v, type(defaults[k])):
            out[k] = v
    return out


def get_newsletter_popup():
    return _merge(POPUP_DEFAULTS, _stored(NEWSLETTER_POPUP_KEY))


def get_cookie_consent():
    return _merge(CONSENT_DEFAULTS, _stored(COOKIE_CONSENT_KEY))


def _save(key, value):
    setting = db.session.get(SiteSetting, key)
    if setting is None:
        setting = SiteSetting(key=key)
        db.session.add(setting)
    setting.value = value


def save_newsletter_popup(data):
    if not isinstance(data, dict):
        raise EngagementSettingsError("newsletterPopup must be an object.")
    unknown = set(data) - set(POPUP_DEFAULTS)
    if unknown:
        raise EngagementSettingsError(f"Unknown newsletter popup setting(s): {', '.join(sorted(unknown))}.")
    value = get_newsletter_popup()
    if "enabled" in data:
        if not isinstance(data["enabled"], bool):
            raise EngagementSettingsError("enabled must be true or false.")
        value["enabled"] = data["enabled"]
    for field, (low, high) in _POPUP_RANGES.items():
        if field in data:
            v = data[field]
            if not isinstance(v, int) or isinstance(v, bool) or not low <= v <= high:
                raise EngagementSettingsError(f"{field} must be a whole number from {low} to {high}.")
            value[field] = v
    labels = {"title": "Title", "body": "Body", "ctaLabel": "Button label"}
    for field, limit in _POPUP_TEXT.items():
        if field in data:
            value[field] = _plain(data[field], labels[field], limit)
    _save(NEWSLETTER_POPUP_KEY, value)
    return value


def save_cookie_consent(data):
    if not isinstance(data, dict):
        raise EngagementSettingsError("cookieConsent must be an object.")
    unknown = set(data) - set(CONSENT_DEFAULTS)
    if unknown:
        raise EngagementSettingsError(f"Unknown cookie consent setting(s): {', '.join(sorted(unknown))}.")
    value = get_cookie_consent()
    if "bannerEnabled" in data:
        if not isinstance(data["bannerEnabled"], bool):
            raise EngagementSettingsError("bannerEnabled must be true or false.")
        value["bannerEnabled"] = data["bannerEnabled"]
    if "version" in data:
        if not isinstance(data["version"], str) or not _VERSION_RE.match(data["version"].strip()):
            raise EngagementSettingsError("Consent version must be 1-20 letters, numbers, dots, dashes or underscores.")
        value["version"] = data["version"].strip()
    labels = {"title": "Banner title", "body": "Banner text"}
    for field, limit in _CONSENT_TEXT.items():
        if field in data:
            value[field] = _plain(data[field], labels[field], limit)
    _save(COOKIE_CONSENT_KEY, value)
    return value
