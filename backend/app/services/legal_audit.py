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
     "duration": "Until cleared, or until the consent version changes.", "consentRequired": False},
    {"name": "wsf_newsletter_popup", "provider": "WSF (first party)", "category": "essential",
     "purpose": "Remembers that the visitor closed or completed the newsletter popup, so it is not shown again.",
     "storage": "localStorage", "duration": "The dismissal/success period set in Studio.", "consentRequired": False},
    {"name": "wsf-reflection:* / wsf-checklist:*", "provider": "WSF (first party)", "category": "essential",
     "purpose": "Saves a learner's own reflection answers and checklist ticks on their device (never sent to WSF).",
     "storage": "localStorage", "duration": "Until cleared by the learner.", "consentRequired": False},
    {"name": "wsf_acquisition", "provider": "WSF (first party)", "category": "analytics",
     "purpose": "Records how the visitor arrived (referrer/UTM) for WSF's own analytics events.",
     "storage": "sessionStorage", "duration": "Browser session.", "consentRequired": True},
    {"name": "WSF analytics events (POST /api/v1/analytics/events)", "provider": "WSF (first party)", "category": "analytics",
     "purpose": "Counts engagement events (e.g. clicks, sign-ups) in WSF's own database.", "storage": "none (server request)",
     "duration": "Not stored in the browser.", "consentRequired": True},
    # Functional media the visitor came for (not advertising): Preferences.
    # Loaded automatically only with Preferences consent; otherwise only for
    # the one video the visitor presses Play on.
    {"name": "Embedded video players (YouTube no-cookie, Vimeo, Wistia, Loom)", "provider": "Third party", "category": "preferences",
     "purpose": "Plays lesson and event videos. The provider may set its own cookies/storage.", "storage": "third-party",
     "duration": "Set by the provider (not controlled by WSF).", "consentRequired": True},
)

# Integrations that have a Studio label but NO runtime code.
INACTIVE_INTEGRATIONS = ("Google Analytics", "Google Search Console", "Meta Pixel", "LinkedIn Insight Tag")


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
