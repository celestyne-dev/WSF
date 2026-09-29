import re

from marshmallow import ValidationError

from app.extensions import db
from app.models.cms import Menu, MenuItem, SiteSetting, SocialLink
from app.models.page import Page
from app.services.navigation import serialize_public_menu_item

# Any Menu whose key starts with this prefix is a footer group — a prefix
# convention (not a fixed enum) so admins can add new groups beyond the
# four seeded ones (Explore/Opportunities/About/Legal) without a
# migration. Reuses the exact Menu/MenuItem architecture Navigation CMS
# already built (see app/services/navigation.py) rather than a second,
# parallel footer-group system.
FOOTER_MENU_KEY_PREFIX = "footer_"

FOOTER_GROUP_LABEL_MAX = 40
FOOTER_MAX_GROUPS = 8

_HTML_TAG_RE = re.compile(r"<[^>]*>")


def footer_menu_key(existing_keys):
    """A fresh, unique footer_* key for a newly created group — admins
    never type or see this key, only the group's `heading`.
    """
    index = 1
    while f"{FOOTER_MENU_KEY_PREFIX}custom_{index}" in existing_keys:
        index += 1
    return f"{FOOTER_MENU_KEY_PREFIX}custom_{index}"


def get_footer_menus():
    return Menu.query.filter(Menu.key.like(f"{FOOTER_MENU_KEY_PREFIX}%")).order_by(Menu.sort_order, Menu.id).all()


# ---------------------------------------------------------------------------
# Default-footer bootstrap/healing. Idempotent and safe to run against a
# real production database — the same category as
# seed_roles_and_permissions()/seed_countries()/seed_default_navigation(),
# never seed_demo_content(). The single source of truth for the four
# canonical footer groups: both `flask seed-footer` and `flask seed-demo`
# (via seed_demo_content()) call heal_footer_defaults() below, so there is
# exactly one place this content is defined.
#
# Stable footer_* keys (not headings) are the identity an existing group
# is matched by — an admin who relabeled "Opportunity" or "WSF" to
# something else, or who never asked for the plural/renamed heading this
# module's canonical list uses, keeps their own heading forever; it is
# only ever set when a group doesn't exist yet and has to be created from
# scratch. See heal_footer_defaults()'s own docstring for the destination-
# level identity check (legacy route vs Page-backed link) this needs on
# top of that.
# ---------------------------------------------------------------------------

FOOTER_CANONICAL_GROUPS = [
    (
        "footer_explore",
        "Explore",
        [
            {"label": "Stories", "item_type": "route", "url": "/topics"},
            {"label": "Resources", "item_type": "route", "url": "/resources"},
            {"label": "Events", "item_type": "route", "url": "/events"},
        ],
    ),
    (
        "footer_opportunity",
        "Opportunities",
        [
            {"label": "Jobs", "item_type": "route", "url": "/jobs"},
            {"label": "Opportunities", "item_type": "route", "url": "/opportunities"},
            {"label": "Community", "item_type": "route", "url": "/community"},
            {"label": "Mentorship", "item_type": "route", "url": "/mentorship"},
        ],
    ),
    (
        "footer_wsf",
        "About",
        [
            {"label": "About", "item_type": "page", "page_key": "about"},
            {"label": "Contact", "item_type": "page", "page_key": "contact"},
            {"label": "Partner With Us", "item_type": "route", "url": "/partnerships"},
            {"label": "Advertise", "item_type": "route", "url": "/advertise"},
        ],
    ),
    (
        "footer_legal",
        "Legal",
        [
            {"label": "Privacy", "item_type": "page", "page_key": "privacy"},
            {"label": "Terms", "item_type": "page", "page_key": "terms"},
            {"label": "Cookies", "item_type": "page", "page_key": "cookies"},
            {"label": "Editorial Policy", "item_type": "page", "page_key": "editorial-policy"},
        ],
    ),
]


def _canonical_effective_url(item_data):
    """The real destination a canonical item definition resolves to,
    computed the same way MenuItem.effective_url() computes it for a real
    row — a page-backed canonical item and an existing legacy route item
    pointing at that same page's public URL (e.g. a pre-Pages-CMS
    `url="/privacy"` link) must compare equal here, or healing would add a
    second, duplicate link to a destination the footer already has.
    """
    if item_data["item_type"] == "page":
        page = Page.query.filter_by(key=item_data["page_key"]).first()
        return f"/{page.slug}" if page else None
    return item_data.get("url")


def _build_footer_item(menu_id, item_data):
    """Builds one canonical item as a real MenuItem row. Returns None
    (adds nothing) for a page-backed item whose target system Page
    doesn't exist yet — safe to call before `flask seed-pages` has run;
    that destination is simply picked up on a later heal once the page
    exists, rather than crashing this one.
    """
    page_id = None
    if item_data["item_type"] == "page":
        page = Page.query.filter_by(key=item_data["page_key"]).first()
        if page is None:
            return None
        page_id = page.id
    item = MenuItem(
        menu_id=menu_id,
        label=item_data["label"],
        item_type=item_data["item_type"],
        url=item_data.get("url"),
        page_id=page_id,
        sort_order=0,
        visible=True,
    )
    db.session.add(item)
    db.session.flush()
    return item


def heal_footer_defaults():
    """Ensure every canonical footer destination in FOOTER_CANONICAL_GROUPS
    is present somewhere in the footer, adding only what's genuinely
    missing — never renaming, reordering, hiding, or removing anything
    that already exists, whether it was seeded earlier or hand-added/
    edited by an admin through AdminFooter. Idempotent: once every
    canonical destination is present, a further call is a no-op.

    Matches destinations across the WHOLE footer (every footer_* group,
    including admin-created custom ones), not just within the canonical
    group a destination "belongs" to — an admin may have moved a link to
    a different group on purpose, and a legacy route item (item_type=
    "route", url="/privacy") already satisfies the canonical Page-backed
    "Privacy" link just as well as a real page-typed item would, via
    MenuItem.effective_url()'s identity (see _canonical_effective_url()).
    This is what fixes the actual regression: this footer was seeded back
    when fewer destinations exist (before Resources/Events/Community/
    Mentorship/Contact/Advertise/Cookies/Editorial Policy existed, and
    before Privacy/Terms/About were Page-backed), and the old create-only
    `_seed_menu_if_empty` guard never adds anything to a group that
    already has at least one item — so it's permanently stuck missing
    every destination added since, with no automated way to catch back
    up. Called from both `flask seed-footer` (safe on a real production
    database) and `flask seed-demo` (so a fresh dev database still gets
    the full footer on the very first run, same as before).

    Returns {"created_groups": [...], "added_items": [(group_key, label), ...]}
    so a CLI command can report exactly what happened.
    """
    existing_menus = {m.key: m for m in get_footer_menus()}
    existing_destinations = set()
    for menu in existing_menus.values():
        for item in menu.top_level_items():
            dest = item.effective_url()
            if dest:
                existing_destinations.add(dest)

    created_groups = []
    added_items = []

    for key, heading, canonical_items in FOOTER_CANONICAL_GROUPS:
        existing_menu = existing_menus.get(key)

        canonical_dests = [_canonical_effective_url(c) for c in canonical_items]
        rank_by_dest = {d: idx for idx, d in enumerate(canonical_dests) if d is not None}

        missing = [
            (idx, canonical_items[idx], canonical_dests[idx])
            for idx in range(len(canonical_items))
            if canonical_dests[idx] is not None and canonical_dests[idx] not in existing_destinations
        ]
        if not missing:
            continue  # nothing to add here — never create an empty group just to hold nothing

        is_new_menu = existing_menu is None
        if is_new_menu:
            menu = Menu(key=key, heading=heading, sort_order=len(existing_menus))
            db.session.add(menu)
            db.session.flush()
            existing_menus[key] = menu
        else:
            menu = existing_menu

        merged = [] if is_new_menu else list(menu.top_level_items())
        for rank, item_data, dest in missing:
            new_item = _build_footer_item(menu.id, item_data)
            if new_item is None:
                continue
            insert_at = len(merged)
            for pos, existing in enumerate(merged):
                existing_rank = rank_by_dest.get(existing.effective_url())
                if existing_rank is not None and existing_rank > rank:
                    insert_at = pos
                    break
            merged.insert(insert_at, new_item)
            existing_destinations.add(dest)
            added_items.append((key, item_data["label"]))

        for index, item in enumerate(merged):
            item.sort_order = index
            db.session.add(item)

        if is_new_menu:
            created_groups.append(key)

    db.session.commit()
    return {"created_groups": created_groups, "added_items": added_items}


def reject_html(value, field_name, max_length):
    """Plain-text guard for footer copy (brand description, newsletter
    heading/description, copyright text, group headings) — spec: "Do not
    permit raw HTML/JS... reject unsafe content." A blunt "no angle-bracket
    tags" check is enough here since none of these fields are meant to
    support any markup at all (unlike Article/Page content, which goes
    through the block editor's own sanitizer).
    """
    if value is None:
        return value
    if len(value) > max_length:
        raise ValidationError(f"Must be {max_length} characters or fewer.", field_name=field_name)
    if _HTML_TAG_RE.search(value):
        raise ValidationError("HTML/script content is not allowed here.", field_name=field_name)
    return value


def validate_group_label(label):
    return reject_html(label, "heading", FOOTER_GROUP_LABEL_MAX)


def serialize_public_footer_group(menu):
    """A hidden group, or one left with no visible/public-eligible links
    after filtering, is dropped entirely — spec: "if a group has no
    visible valid links, hide the empty group publicly." Reuses
    serialize_public_menu_item() so a footer link gets exactly the same
    entity-eligibility/URL-resolution treatment as a Navigation item —
    no separate rules to keep in sync.
    """
    if not menu.visible:
        return None
    items = [serialize_public_menu_item(i) for i in menu.top_level_items() if i.visible and i.is_entity_public()]
    items = [i for i in items if i is not None]
    if not items:
        return None
    return {"key": menu.key, "heading": menu.heading, "items": items}


def serialize_public_footer_groups():
    groups = [serialize_public_footer_group(menu) for menu in get_footer_menus()]
    return [g for g in groups if g is not None]


# Display name used only to build a social link's default accessible name
# when no admin-provided `label` override is set (spec: "Women Shaping
# Futures on LinkedIn" rather than icon-only ambiguity) — mirrors the
# frontend's SocialIcon platform keys.
SOCIAL_PLATFORM_LABELS = {
    "linkedin": "LinkedIn",
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "threads": "Threads",
    "pinterest": "Pinterest",
    "youtube": "YouTube",
    "whatsapp": "WhatsApp",
    "twitter": "Twitter",
}

ORGANIZATION_NAME = "Women Shaping Futures"


def social_link_accessible_label(link):
    if link.label:
        return link.label
    platform_label = SOCIAL_PLATFORM_LABELS.get(link.platform, link.platform.title())
    return f"{ORGANIZATION_NAME} on {platform_label}"


def serialize_public_social_links():
    links = SocialLink.query.filter_by(visible=True).order_by(SocialLink.sort_order).all()
    return [
        {"platform": link.platform, "url": link.url, "label": social_link_accessible_label(link)}
        for link in links
    ]


# Presentation-only defaults so the public footer never renders blank
# copy before an admin has opened AdminFooter for the first time — these
# match Footer.jsx's previous hard-coded copy exactly, so first deploy
# looks identical to before this feature existed.
DEFAULT_FOOTER_SETTINGS = {
    "brandDescription": "",
    "newsletterHeading": "WSF Weekly",
    "newsletterDescription": "Stories, jobs, and opportunities — every Thursday.",
    "newsletterVisible": True,
    "contactEmail": "",
    "copyrightText": "Women Shaping Futures. All rights reserved.",
}

FOOTER_SETTINGS_KEY = "footer"


def get_footer_settings():
    setting = db.session.get(SiteSetting, FOOTER_SETTINGS_KEY)
    value = setting.value if setting else None
    return {**DEFAULT_FOOTER_SETTINGS, **(value or {})}


def build_public_footer():
    return {
        "settings": get_footer_settings(),
        "groups": serialize_public_footer_groups(),
        "socialLinks": serialize_public_social_links(),
    }
