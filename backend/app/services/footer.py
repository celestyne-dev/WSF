import re

from marshmallow import ValidationError

from app.extensions import db
from app.models.cms import Menu, SiteSetting, SocialLink
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
