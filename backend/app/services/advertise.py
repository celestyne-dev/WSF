"""Advertise page bootstrap — the single source of truth for the
AdvertisePage(id=1) baseline and the eight canonical AdvertiseOffering
rows, using the same production-safe contract as
app/services/pages.py:seed_system_pages() and
app/services/footer.py:heal_footer_defaults().

Used by `flask seed-advertise` (safe against a real production database —
same category as seed_roles_and_permissions()/seed_countries()/
seed_system_pages()/heal_footer_defaults(), never seed_demo_content()) and
also called from seed_demo_content() for local convenience, same as those
siblings.

Why this exists: GET /api/v1/advertise/public 404s whenever AdvertisePage
row id=1 is missing or its status isn't "published" (see
app/api/v1/advertise.py:PublicAdvertiseResource — intentional, preserved
here). Migration e7f3b2a9c1d4 inserts that row, but deliberately leaves it
"draft" with no real content and seeds zero AdvertiseOffering rows — so a
freshly migrated, properly bootstrapped site still 404s on /advertise
until an administrator manually opens AdminAdvertise and publishes it.
This module closes that gap without ever touching a row an administrator
has started curating.
"""
from app.extensions import db
from app.models.cms import AdvertiseOffering, AdvertisePage


def _heading(text):
    return {"type": "heading", "text": text}


def _paragraph(text):
    return {"type": "paragraph", "text": text}


def _list(items):
    return {"type": "list", "items": items}


# The exact hero/CTA copy migration e7f3b2a9c1d4 inserts for the
# migration-seeded row — used only to recognize that row as still
# genuinely untouched (see _is_untouched_placeholder below), never
# written from here as a "default" on a row that already differs from
# this in any way.
_MIGRATION_DEFAULT_TEXT_FIELDS = {
    "hero_heading": "Advertise With Women Shaping Futures",
    "hero_description": (
        "Reach ambitious, career-driven women across media, leadership, careers, business, "
        "and community — through a trusted global editorial platform."
    ),
    "cta_heading": "Let's talk",
    "cta_description": "Tell us about your goals and our team will follow up.",
    "cta_button_label": "Get in touch",
}

# Every other column the migration leaves blank/None/empty-list. If any of
# these is non-blank, something has written to this row since the
# migration ran, so it is never considered an untouched placeholder.
_BLANK_SCALAR_FIELDS_ON_MIGRATION = (
    "hero_media_id", "audience_overview", "contact_email", "contact_note",
    "media_kit_title", "media_kit_url", "media_kit_updated_at", "seo",
)
_BLANK_LIST_FIELDS_ON_MIGRATION = ("intro_content", "why_content", "faq")


def _is_untouched_placeholder(page):
    """Strict, narrow, testable definition of "this is still exactly the
    row migration e7f3b2a9c1d4 inserted, nothing else has touched it" —
    every field the migration set to real text must still equal that
    exact text, every field it left blank must still be blank, and
    status must still be its "draft" default. If ANY of that has
    changed — including an admin publishing it with no other edits, or
    editing just one field while leaving the rest blank — this returns
    False and the row is left completely alone. Never a loose heuristic
    (e.g. "no content" or "still draft" alone): both are necessary, not
    sufficient, so a real admin edit can never be silently overwritten
    or republished.
    """
    if page.status != "draft":
        return False
    for field, default_value in _MIGRATION_DEFAULT_TEXT_FIELDS.items():
        if getattr(page, field) != default_value:
            return False
    for field in _BLANK_SCALAR_FIELDS_ON_MIGRATION:
        if getattr(page, field):
            return False
    for field in _BLANK_LIST_FIELDS_ON_MIGRATION:
        if getattr(page, field):
            return False
    return True


# Baseline content applied in full only when the page is genuinely
# missing or is the untouched placeholder above — never a partial
# "fill in whatever's blank" pass against a page an admin is actively
# curating. After either of those two cases, AdminAdvertise (the CMS) is
# the sole source of truth; this module never runs again against that
# same row in a way that changes it.
BASELINE_PAGE_FIELDS = dict(
    _MIGRATION_DEFAULT_TEXT_FIELDS,
    intro_content=[
        _paragraph(
            "Women Shaping Futures partners with brands, employers, and organizations that want to reach "
            "an engaged, global audience of ambitious, career-driven women. Every sponsored placement is "
            "clearly disclosed and never presented as independent editorial coverage."
        ),
    ],
    audience_overview=(
        "Our audience spans media, leadership, careers, business, and community — professionals actively "
        "building their careers who are looking for the next opportunity, resource, or community to join."
    ),
    why_content=[
        _heading("Why partner with us"),
        _list(
            [
                "A trusted editorial voice read by career-driven women around the world.",
                "Multiple commercial formats, from sponsored editorial to event sponsorship.",
                "Transparent, clearly disclosed sponsored content that never compromises editorial trust.",
            ]
        ),
    ],
    contact_email="partnerships@womenshapingfutures.org",
    contact_note="Our team reviews every inquiry and typically responds within a few business days.",
    faq=[
        {
            "question": "How is sponsored content disclosed?",
            "answer": (
                "Every sponsored placement is clearly labeled and never presented as independent "
                "editorial coverage."
            ),
        },
        {
            "question": "Do you offer custom packages?",
            "answer": "Tell us your goals in the form below and our team will put together options that fit.",
        },
    ],
    seo={
        "title": "Advertise With Women Shaping Futures",
        "description": (
            "Sponsor editorial content, newsletters, events, and more on Women Shaping Futures — a "
            "trusted global platform for ambitious, career-driven women."
        ),
    },
)

# The eight paid commercial formats publicly described on both /advertise
# (as AdvertiseOffering rows, via this seed) and /partnerships (as the
# "Available Partnership Formats" cards, see frontend/src/pages/
# PartnershipsPage.jsx's buildFormats()) and selectable in the public
# partnership inquiry dropdown (PAID_PARTNERSHIP_TYPES in
# app/models/commerce.py) — one canonical set of names and descriptions,
# not three. `name` is this list's safe canonical identity: an offering
# is only ever created here if no existing AdvertiseOffering already has
# that exact name, so an admin's own edits (to these eight or to any
# other offering they created) are never duplicated or overwritten. No
# public prices are invented — pricing_mode stays "contact" for all eight,
# consistent with the rest of this CMS's existing architecture.
CANONICAL_OFFERINGS = [
    dict(
        name="Sponsored Editorial",
        short_description="A commissioned story or profile, clearly labeled, written in our editorial voice.",
        full_description=(
            "Partner with our editorial team on a sponsored story or profile that reaches our audience in "
            "our own voice — always clearly disclosed, never presented as independent editorial judgment."
        ),
        features=[
            "Clearly disclosed sponsored placement",
            "Written in our editorial voice",
            "Distributed across our channels",
        ],
        cta_label="Enquire",
        display_order=0,
    ),
    dict(
        name="Sponsored Series",
        short_description="Co-brand an ongoing series like Founder Stories with your organization.",
        full_description=(
            "Attach your brand to one of our recurring editorial series, with visibility across multiple "
            "installments rather than a single placement."
        ),
        features=["Multi-part visibility", "Consistent brand association", "Clearly disclosed sponsorship"],
        cta_label="Enquire",
        display_order=1,
    ),
    dict(
        name="Newsletter Sponsorship",
        short_description="A dedicated placement in WSF Weekly, reaching our engaged newsletter subscribers.",
        full_description=(
            "Reach our newsletter subscribers directly with a dedicated sponsored placement in WSF Weekly."
        ),
        features=["Dedicated newsletter placement", "Engaged subscriber audience", "Flexible scheduling"],
        cta_label="Enquire",
        display_order=2,
    ),
    dict(
        name="Social Media Campaigns",
        short_description="Custom content across our LinkedIn audience and other social channels.",
        full_description=(
            "Custom-built social content campaigns reaching our LinkedIn following and other social channels."
        ),
        features=["Custom creative", "Multi-platform reach", "Performance reporting"],
        cta_label="Enquire",
        display_order=3,
    ),
    dict(
        name="Employer Branding",
        short_description="Featured job placements and employer profile pages for talent attraction.",
        full_description=(
            "Build employer brand visibility through featured job placements and a dedicated employer "
            "profile page."
        ),
        features=["Featured job placements", "Employer profile page", "Talent attraction reach"],
        cta_label="Enquire",
        display_order=4,
    ),
    dict(
        name="Event Sponsorship",
        short_description="Brand presence at the Women in Leadership Summit and WSF webinars.",
        full_description=(
            "Secure brand presence at our flagship events, including the Women in Leadership Summit and "
            "WSF webinars."
        ),
        features=["Flagship event visibility", "Webinar brand presence", "Audience engagement"],
        cta_label="Enquire",
        display_order=5,
    ),
    dict(
        name="Sponsored Resources",
        short_description="Co-branded guides, templates, and worksheets in our resource library.",
        full_description="Co-brand a guide, template, or worksheet distributed through our resource library.",
        features=["Co-branded resource", "Ongoing library placement", "Clearly disclosed sponsorship"],
        cta_label="Enquire",
        display_order=6,
    ),
    dict(
        name="Research Partnerships",
        short_description="Co-commissioned reports and original research on women in business.",
        full_description="Partner with us on original research and co-commissioned reports on women in business.",
        features=["Co-commissioned research", "Original data and insights", "Shared distribution"],
        cta_label="Enquire",
        display_order=7,
    ),
]
for _offering in CANONICAL_OFFERINGS:
    _offering.setdefault("pricing_mode", "contact")


def _seed_missing_offerings():
    existing_names = {name for (name,) in db.session.query(AdvertiseOffering.name).all()}
    created = []
    for fields in CANONICAL_OFFERINGS:
        if fields["name"] in existing_names:
            continue
        db.session.add(AdvertiseOffering(**fields))
        created.append(fields["name"])
    return created


def seed_advertise_page_and_offerings():
    """Idempotent, create-or-heal-blank-placeholder-only bootstrap for the
    Advertise page and its canonical offerings. Safe to run repeatedly
    and safe on a real production database — same category as
    seed_roles_and_permissions()/seed_countries()/seed_system_pages()/
    heal_footer_defaults(), never seed_demo_content(). Self-contained
    commit, like those, since `flask seed-advertise` calls this directly.

    Returns {"page_action": "created" | "healed" | "left_untouched",
    "offerings_created": [names actually created]}.
    """
    page = db.session.get(AdvertisePage, 1)
    if page is None:
        page = AdvertisePage(id=1)
        db.session.add(page)
        page_action = "created"
    elif _is_untouched_placeholder(page):
        page_action = "healed"
    else:
        page_action = "left_untouched"

    if page_action in ("created", "healed"):
        for field, value in BASELINE_PAGE_FIELDS.items():
            setattr(page, field, value)
        page.status = "published"

    offerings_created = _seed_missing_offerings()
    db.session.commit()
    return {"page_action": page_action, "offerings_created": offerings_created}
