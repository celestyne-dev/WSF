"""Read-only legal/privacy audit helpers (`flask --app run:app
legal-pages-audit`). Never writes, never prints user data.

1. audit_legal_pages(): structure/review facts for the four core legal
   system Pages. Structural gaps are WARNINGS (headings are editorial
   choices); a missing or unpublished core legal Page is HIGHLIGHTED.
2. TECHNOLOGY_INVENTORY: the browser storage and third-party technologies
   WSF's own code actually uses, kept next to the code that creates them
   (a test checks every storage key the frontend writes is listed here).
   Names and durations are only what the code itself sets; nothing is
   invented. This is input for the real Cookie Policy, not the policy.
"""
from app.models.page import Page

LEGAL_PAGE_KEYS = ("privacy", "terms", "cookies", "editorial-policy")

# category: essential | preferences | analytics | marketing
TECHNOLOGY_INVENTORY = (
    {"name": "wsf_access_token / wsf_refresh_token", "provider": "WSF (first party)", "category": "essential",
     "purpose": "Keeps a signed-in member signed in (authentication).", "storage": "localStorage",
     "duration": "Until sign-out; the tokens inside expire per the server's JWT settings.", "consentRequired": False},
    {"name": "wsf_cookie_consent", "provider": "WSF (first party)", "category": "essential",
     "purpose": "Remembers the visitor's cookie choices (version, time, categories).", "storage": "localStorage",
     "duration": ("12 calendar months from the choice, then removed and the visitor is asked again; "
                  "asked again immediately if the consent version changes sooner."),
     "consentRequired": False},
    {"name": "wsf_newsletter_popup", "provider": "WSF (first party)", "category": "preferences",
     "purpose": "Remembers that the visitor closed or completed the newsletter popup, so it is not shown again.",
     "storage": ("localStorage only with Preferences consent; otherwise sessionStorage (this browser session). "
                 "Withdrawing Preferences deletes the localStorage copy."),
     "duration": ("localStorage: kept until cleared; it suppresses the popup for the dismissal period (default 14 days) "
                  "or the post-signup period (default 365 days) set in Studio. sessionStorage: until the browser "
                  "session ends."),
     "consentRequired": True},
    {"name": "wsf-reflection:* / wsf-checklist:*", "provider": "WSF (first party)", "category": "essential",
     "purpose": "Saves a learner's own reflection answers and checklist ticks on their device (never sent to WSF).",
     "storage": "localStorage", "duration": "Until cleared by the learner.", "consentRequired": False},
    {"name": "Self-hosted web fonts (Fraunces, Inter)", "provider": "WSF (first party)", "category": "essential",
     "purpose": ("Typefaces for the site, served from WSF's own server (no request to Google or any other "
                 "font service). Licensed under the SIL Open Font License 1.1."),
     "storage": "none (static file; the browser's ordinary HTTP cache)",
     "duration": "Not stored by WSF in the browser; the files are cached like any page asset.", "consentRequired": False},
    {"name": "wsf_acquisition", "provider": "WSF (first party)", "category": "analytics",
     "purpose": "Records how the visitor arrived (referrer/UTM) for WSF's own analytics events.",
     "storage": "sessionStorage", "duration": "Browser session.", "consentRequired": True},
    {"name": "WSF analytics events (POST /api/v1/analytics/events)", "provider": "WSF (first party)", "category": "analytics",
     "purpose": "Counts engagement events (e.g. clicks, sign-ups) in WSF's own database.", "storage": "none (server request)",
     "duration": "Not stored in the browser.", "consentRequired": True},
    # Functional media the visitor came for (not advertising): Preferences.
    # Loaded automatically only with Preferences consent; otherwise a
    # placeholder ("This video is hosted by {provider}. Playing it may set
    # cookies.") offers "Play video" (this one video only, no consent change)
    # and "Always allow videos" (grants Preferences).
    {"name": "Embedded video players (YouTube no-cookie, Vimeo, Wistia, Loom)", "provider": "Third party", "category": "preferences",
     "purpose": ("Plays lesson and event videos. The provider may set its own cookies/storage. Without Preferences "
                 "consent no player loads until the visitor presses Play on that video."),
     "storage": "third-party",
     "duration": "Set by the provider (not controlled by WSF).", "consentRequired": True},
    # Configurable third party: present in the code but INACTIVE until an ID is
    # saved in Studio (app/services/tracking_settings.py); `configKey` says
    # which setting switches it on. Runs only with its consent category.
    {"name": "Google Analytics 4 (_ga, _ga_<container-id> cookies)", "provider": "Google (third party)",
     "category": "analytics", "configKey": "ga4MeasurementId",
     "purpose": ("Measures how the site is used. Loaded only after Analytics consent, with Consent Mode v2 "
                 "(ad_storage, analytics_storage, ad_user_data, ad_personalization default to denied; only "
                 "analytics_storage is granted). Google Signals and ad personalization are off."),
     "storage": "cookies set by Google's script on WSF's domain (_ga, _ga_*)",
     "duration": ("Set by Google's script, not by WSF code. On withdrawal WSF stops measurement and deletes "
                  "the site's _ga and _ga_* cookies."),
     "consentRequired": True},
)

# Integrations that have a Studio label but NO runtime code.
INACTIVE_INTEGRATIONS = ("Google Search Console", "Meta Pixel", "LinkedIn Insight Tag")


def configurable_status():
    """[(inventory name, configured?)] for integrations switched on by a
    Studio setting. Requires an app context."""
    from app.services.tracking_settings import active_trackers

    active = active_trackers()
    return [(t["name"], t["configKey"] in active) for t in TECHNOLOGY_INVENTORY if t.get("configKey")]


def _headings(blocks):
    return [b.get("text") for b in (blocks or []) if isinstance(b, dict) and b.get("type") == "heading" and b.get("text")]


def audit_legal_pages():
    rows, highlights, warnings = [], [], []
    for key in LEGAL_PAGE_KEYS:
        page = Page.query.filter_by(key=key).first()
        if page is None:
            highlights.append(f'The "{key}" page does not exist (run `flask seed-pages`, then review its wording).')
            rows.append({"key": key, "exists": False})
            continue
        seo = page.seo or {}
        public = page.status == "published"
        row = {
            "key": key, "exists": True, "title": page.title, "status": page.status,
            "effectiveDate": page.effective_date.isoformat() if page.effective_date else None,
            "lastReviewedAt": page.last_reviewed_at.isoformat() if page.last_reviewed_at else None,
            "blocks": len(page.content or []), "headings": _headings(page.content),
            "seoTitle": bool(seo.get("title")), "seoDescription": bool(seo.get("description")),
            "canonical": seo.get("canonical") or "default", "public": public,
        }
        rows.append(row)
        if not public:
            highlights.append(f'The "{key}" page is {page.status}: it is not publicly available.')
        if not row["effectiveDate"]:
            warnings.append(f'"{key}": no effective date is set.')
        if not row["lastReviewedAt"]:
            warnings.append(f'"{key}": never marked as reviewed.')
        if len(row["headings"]) < 3:
            warnings.append(f'"{key}": only {len(row["headings"])} section heading(s); check it covers what WSF actually does.')
        if not row["seoDescription"]:
            warnings.append(f'"{key}": no SEO description.')
    return {"pages": rows, "highlights": highlights, "warnings": warnings}
