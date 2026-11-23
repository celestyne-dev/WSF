"""Studio -> Settings -> Integrations: optional third-party measurement.

Every integration here is INACTIVE until its ID is entered. Only a bare
identifier is stored, validated against the provider's exact ID format:
never a script, snippet, URL or HTML. The script URLs themselves are fixed
constants in the frontend (frontend/src/utils/trackers/), so nothing typed
in Studio can make the site load arbitrary code.

Consent still decides whether a configured integration runs in a visitor's
browser (frontend/src/utils/consent.js):
- Google Analytics 4: Analytics consent.
- LinkedIn Insight Tag and Meta Pixel: Marketing consent, and never while
  the browser sends Global Privacy Control.

IDs are not secrets (they are visible in any page that loads the tag), so
they are part of the public settings payload.
"""
import re

from app.extensions import db
from app.models.cms import SiteSetting

TRACKING_KEY = "tracking"

TRACKING_DEFAULTS = {
    "ga4MeasurementId": "",
    "linkedinPartnerId": "",
    "metaPixelId": "",
}

_FORMATS = {
    # GA4 web data stream Measurement ID, e.g. G-ABC123XYZ9.
    "ga4MeasurementId": (re.compile(r"^G-[A-Z0-9]{4,20}$"), "a GA4 Measurement ID such as G-ABC123XYZ9"),
    # Numeric IDs shown in each provider's own tag setup screen.
    "linkedinPartnerId": (re.compile(r"^[0-9]{4,12}$"), "the numeric LinkedIn Insight Tag Partner ID"),
    "metaPixelId": (re.compile(r"^[0-9]{6,20}$"), "the numeric Meta Pixel ID"),
}


class TrackingSettingsError(ValueError):
    pass


def get_tracking_settings():
    setting = db.session.get(SiteSetting, TRACKING_KEY)
    stored = setting.value if setting is not None and isinstance(setting.value, dict) else {}
    out = dict(TRACKING_DEFAULTS)
    for key in TRACKING_DEFAULTS:
        value = stored.get(key)
        if isinstance(value, str) and (value == "" or _FORMATS[key][0].match(value)):
            out[key] = value
    return out


def active_trackers():
    """Which integrations are configured (has an ID). Inactive ones are
    absent: nothing about them reaches a browser."""
    return {key: value for key, value in get_tracking_settings().items() if value}


def save_tracking_settings(data):
    if not isinstance(data, dict):
        raise TrackingSettingsError("tracking must be an object.")
    unknown = set(data) - set(TRACKING_DEFAULTS)
    if unknown:
        raise TrackingSettingsError(f"Unknown integration setting(s): {', '.join(sorted(unknown))}.")
    value = get_tracking_settings()
    for key, raw in data.items():
        if not isinstance(raw, str):
            raise TrackingSettingsError(f"{key} must be text.")
        cleaned = raw.strip().upper() if key == "ga4MeasurementId" else raw.strip()
        pattern, example = _FORMATS[key]
        if cleaned and not pattern.match(cleaned):
            raise TrackingSettingsError(f"Enter {example}, or leave it empty to keep it off.")
        value[key] = cleaned
    setting = db.session.get(SiteSetting, TRACKING_KEY)
    if setting is None:
        setting = SiteSetting(key=TRACKING_KEY)
        db.session.add(setting)
    setting.value = value
    return value
