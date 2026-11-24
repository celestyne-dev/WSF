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
    {"name": "wsf_refresh (sign-in session cookie)", "provider": "WSF (first party)", "category": "essential",
     "purpose": ("Keeps a signed-in member signed in: lets the site get a new short-lived access token after a "
                 "page load. Holds only a random identifier; the server stores just its hash and can revoke it."),
     "storage": ("cookie: HttpOnly (not readable by JavaScript), Secure, SameSite=Strict, "
                 "Path=/api/v1/auth/refresh (sent to no other address)"),
     "duration": ("30 days from sign-in (Max-Age), or until sign-out, a password reset or account deactivation "
                  "revokes it. The access token itself is never stored: it lives in page memory and expires "
                  "after 30 minutes."),
     "consentRequired": False},
    {"name": "wsf_cookie_consent", "provider": "WSF (first party)", "category": "essential",
     "purpose": "Remembers the visitor's cookie choices (version, time, categories).", "storage": "localStorage",
     "duration": ("12 calendar months from the choice, then removed and the visitor is asked again; "
                  "asked again immediately if the consent version changes sooner."),
     "consentRequired": False},
    # One browser key, two storage modes (frontend/src/utils/newsletterPopup.js
    # popupStorageFor / syncPopupStorage): sessionStorage without Preferences
    # consent, localStorage with it. Each mode is its own inventory entry.
    {"name": "WSF newsletter popup \u2014 session state", "provider": "WSF (first party)", "category": "essential",
     "purpose": ("Prevents the newsletter popup from interrupting again during the current browser session when "
                 "persistent Preferences storage has not been allowed. It does not persist across visits."),
     "storage": "sessionStorage (wsf_newsletter_popup)",
     "duration": "Until the browser tab/session ends (the browser then deletes it).",
     "consentRequired": False},
    {"name": "WSF newsletter popup \u2014 persistent preference", "provider": "WSF (first party)",
     "category": "preferences",
     "purpose": ("Remembers across visits that the visitor closed the newsletter popup or signed up, so it is not "
                 "shown again for the configured period. Used only with Preferences consent; withdrawing "
                 "Preferences deletes it (a session-only copy is kept instead)."),
     "storage": "localStorage (wsf_newsletter_popup)",
     "duration": ("Effective: suppresses the popup for the Studio dismissal period after closing it (default 14 days, "
                  "configurable 1-365) or the post-signup period after signing up (default 365 days, configurable "
                  "1-3650). Physical: the browser keeps the stored value until it is cleared, Preferences is "
                  "withdrawn, or the next close/signup overwrites it; after its period it no longer suppresses "
                  "anything."),
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
    {"name": "Rate-limit counters (Redis, database fallback)", "provider": "WSF (first party, server-side)",
     "category": "essential",
     "purpose": ("Limits how often one network address can sign in, sign up, reset a password, unsubscribe or "
                 "send forms, and how often one account can post, edit or report comments, to stop abuse. "
                 "Server-side only: nothing is stored on the visitor's device."),
     "storage": "server-side (Redis; PostgreSQL only while Redis is unavailable)",
     "duration": "Each counter lasts one rate-limit window (one minute to one day), then expires.",
     "consentRequired": False},
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
    {"name": "LinkedIn Insight Tag", "provider": "LinkedIn (third party)", "category": "marketing",
     "configKey": "linkedinPartnerId",
     "purpose": ("Campaign measurement. Loaded only with Marketing consent and never while the browser sends "
                 "Global Privacy Control."),
     "storage": "cookies/storage set by LinkedIn's script",
     "duration": ("Set by LinkedIn, not by WSF code. LinkedIn's tag has no off switch, so on withdrawal WSF "
                  "reloads the page to unload it; it never loads again without consent."),
     "consentRequired": True},
    {"name": "Meta Pixel (_fbp, _fbc cookies)", "provider": "Meta (third party)", "category": "marketing",
     "configKey": "metaPixelId",
     "purpose": ("Campaign measurement. Loaded only with Marketing consent and never with Global Privacy "
                 "Control; automatic collection of button and page details (autoConfig) is off."),
     "storage": "cookies set by Meta's script on WSF's domain (_fbp, _fbc) and Meta's own storage",
     "duration": ("Set by Meta's script, not by WSF code. On withdrawal WSF revokes consent in the pixel, "
                  "deletes the site's _fbp and _fbc cookies and reloads the page."),
     "consentRequired": True},
)

# Integrations that have a Studio label but NO runtime code.
INACTIVE_INTEGRATIONS = ("Google Search Console",)


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


# --- implementation facts (Batch 4) --------------------------------------------------------------
# Verified facts about how WSF actually handles personal data, read from code
# and configuration (aggregate counts only, never personal data). Each step
# adds its own section; the policy pages are NOT rewritten from here.


def _newsletter_facts():
    from app.models.newsletter import SUBSCRIBER_STATUSES, NewsletterSubscriber
    from app.services import newsletter as nl
    from app.services.engagement_settings import NEWSLETTER_CHECKBOX_CONSENT_VERSION, NEWSLETTER_CONSENT_VERSION

    counts = {s: NewsletterSubscriber.query.filter_by(status=s).count() for s in SUBSCRIBER_STATUSES}
    return [
        "Newsletter: double opt-in controlled by WSF (unticked checkbox consent, then an emailed confirmation "
        f"link valid {nl.CONFIRMATION_LIFETIME.days} days); only confirmed subscribers are exported.",
        f"Newsletter consent wording versions: form {NEWSLETTER_CONSENT_VERSION}, other forms' checkbox "
        f"{NEWSLETTER_CHECKBOX_CONSENT_VERSION}, legacy reconfirmation {nl.RECONFIRM_CONSENT_VERSION}.",
        "Newsletter subscriber states: " + ", ".join(f"{k}={v}" for k, v in counts.items()) + ".",
        "Newsletter delivery: provider-neutral. WSF does not send newsletters; staff export confirmed subscribers "
        "and record external sends (service name, reference, recipient count). Unsubscribes from an external service "
        "are imported as WSF suppressions (CSV). No sending-provider API is integrated.",
        "Newsletter unsubscribe is authoritative in WSF: suppressed addresses are never reactivated by a signup "
        "alone; only a fresh signup plus a click on its confirmation link.",
    ]


def _email_facts():
    from app.services.site_settings import get_site_identity_raw

    address = (get_site_identity_raw().get("postal_address") or "").strip()
    return [
        "Email classes: transactional (password reset, sign-in security, event registration, learning enrolment, "
        "newsletter confirmation; no unsubscribe action) and optional (comment reply notifications; opt-in, footer "
        "unsubscribe link + List-Unsubscribe with RFC 8058 one-click). Every email carries the common footer "
        "(organisation name, postal address, Privacy Policy link).",
        ("Email footer postal address: set in Studio." if address else
         "WARNING: email footer postal address is NOT SET (Studio -> Settings -> Site Identity -> Postal address). "
         "Complete it before any newsletter marketing is sent; it is never invented."),
    ]


def _account_facts():
    from app.services.account_privacy import FK_TREATMENT, GRACE_PERIOD

    counts = {}
    for decision, _note in FK_TREATMENT.values():
        counts[decision] = counts.get(decision, 0) + 1
    return [
        "Account self-service: JSON data export (Account -> Privacy & data) and deletion with a "
        f"{GRACE_PERIOD.days}-day grace period (all sessions revoked at request; cancellable by signing in or the "
        "emailed link; purged automatically by the scheduled maintenance job).",
        f"Account deletion treatment of {len(FK_TREATMENT)} references to the account: "
        + ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        + ". Payment records are kept and detached; comments become 'Former member' (or are removed on request); "
          "published reader stories are anonymised; the audit log keeps actions without the identity link.",
        "Privacy requests: Studio log (access, correction, deletion, other) with a 30-day operational target.",
        _signup_age_fact(),
    ]


def _signup_age_fact():
    from app.services.account_policy import get_account_policy

    age = get_account_policy()["minimumAge"]
    return (f"Minimum age at signup: {age} (Studio setting, 16-21). Explicit unticked confirmation "
            f"'I confirm that I am at least {age} years old.'; no date of birth collected; the confirmation time, the "
            "age confirmed and the Terms/Privacy versions in force are stored on the account (null for accounts "
            "created before this rule or by staff).")


def _retention_facts():
    from app.services.retention import FIXED_RULES, RETENTION_RULES, get_retention_settings

    values = get_retention_settings()
    periods = [f"{RETENTION_RULES[k][4]}: {v} {RETENTION_RULES[k][3]}" for k, v in values.items()
               if k != "unverifiedAccountDays"]
    periods += [f"{label}: {value} days" for value, label in FIXED_RULES.values()]
    return [
        "Retention (daily, logged counts only): " + "; ".join(periods) + ".",
        "WARNING: the unverified-accounts rule (30 days) is NOT active: WSF has no email-verification flow, "
        "so every member is unverified and the rule would delete them all.",
    ]


# Mirrors frontend src/utils/collectionNotices.js (its test checks each
# placement on the real form); kept here so the audit lists where notices are.
COLLECTION_NOTICE_FORMS = (
    "signup (Terms + Privacy)", "newsletter forms and popup (Privacy)", "contact (Privacy acknowledgement)",
    "comments (Community Guidelines/Terms + Privacy)", "story submission (Privacy + Terms)",
    "event registration (Privacy)", "learning enrolment (Privacy)", "nomination (Privacy)",
    "mentorship application (Privacy)", "community join (Privacy)", "resource download (Privacy)",
    "directory submission (Privacy + Terms)", "partnership enquiry (Privacy)", "advertising enquiry (Privacy)",
)


def _notice_facts():
    return ["Point-of-collection notices with a Privacy Policy link: " + "; ".join(COLLECTION_NOTICE_FORMS) + ". "
            "Forms with an optional newsletter box also say a confirmation link is emailed first."]


FACT_SECTIONS = [("Newsletter", _newsletter_facts), ("Email", _email_facts), ("Account", _account_facts),
                 ("Retention", _retention_facts), ("Notices", _notice_facts)]


def implementation_facts():
    lines = []
    for title, builder in FACT_SECTIONS:
        for line in builder():
            lines.append((title, line))
    return lines
