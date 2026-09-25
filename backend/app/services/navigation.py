import re

from marshmallow import ValidationError

from app.models.cms import MENU_MAX_DEPTH
from app.models.page import Page
from app.models.taxonomy import Series, Topic

# Reject internal destinations that would let Navigation CMS link into the
# admin app or the API itself (spec: "internal link safety" / "reserved
# routes") — a plain shape check, not a full route-table lookup, since
# rebuilding that lookup here would duplicate the frontend router.
_UNSAFE_INTERNAL_PREFIXES = ("/admin", "/api")
_EXTERNAL_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)


def validate_route_url(url, field_name="url"):
    if not url:
        raise ValidationError("An internal path is required for this item type.", field_name=field_name)
    if not url.startswith("/"):
        raise ValidationError('Internal paths must start with "/".', field_name=field_name)
    if len(url) > 1 and url[1] == "/":
        raise ValidationError('Internal paths must be a real path, not "//".', field_name=field_name)
    lowered = url.lower()
    if any(lowered == p or lowered.startswith(p + "/") for p in _UNSAFE_INTERNAL_PREFIXES):
        raise ValidationError("Navigation cannot link into admin or API routes.", field_name=field_name)
    return url


def validate_external_url(url, field_name="url"):
    if not url:
        raise ValidationError("A URL is required for external links.", field_name=field_name)
    if not _EXTERNAL_URL_RE.match(url):
        raise ValidationError("External links must be a full http:// or https:// URL.", field_name=field_name)
    return url


def validate_item_type_requirements(data):
    """Cross-field check: what a given item_type requires is present, and
    nothing irrelevant to it was also supplied — see MENU_ITEM_TYPES'
    docstring for what each type means.
    """
    item_type = data.get("item_type", "route")

    if item_type == "route":
        validate_route_url(data.get("url"))
    elif item_type == "external":
        validate_external_url(data.get("url"))
    elif item_type == "topic":
        if not data.get("topic_id"):
            raise ValidationError("A Topic must be selected for this item type.", field_name="topic_id")
        if Topic.query.get(data["topic_id"]) is None:
            raise ValidationError("Selected Topic does not exist.", field_name="topic_id")
    elif item_type == "series":
        if not data.get("series_id"):
            raise ValidationError("A Series must be selected for this item type.", field_name="series_id")
        if Series.query.get(data["series_id"]) is None:
            raise ValidationError("Selected Series does not exist.", field_name="series_id")
    elif item_type == "page":
        if not data.get("page_id"):
            raise ValidationError("A Page must be selected for this item type.", field_name="page_id")
        if Page.query.get(data["page_id"]) is None:
            raise ValidationError("Selected Page does not exist.", field_name="page_id")
    elif item_type == "group":
        pass  # no destination required or allowed


def validate_depth(items_data, depth=1):
    """Rejects nesting deeper than MENU_MAX_DEPTH (default: top-level +
    one level of children) — matches what the header/mobile-nav components
    actually render; see MENU_MAX_DEPTH's docstring. A plain nested-array
    payload can't express a genuine cycle (an item can't nest itself), so
    there is no separate "circular parent" check to perform here.
    """
    if depth > MENU_MAX_DEPTH:
        raise ValidationError(f"Navigation supports at most {MENU_MAX_DEPTH} levels.", field_name="children")
    for item in items_data:
        children = item.get("children") or []
        if children:
            validate_depth(children, depth + 1)


def compute_item_warnings(item):
    """Non-blocking warnings for this item alone (not its children — each
    child gets its own via the same schema Method, since the admin tree
    dumps every level). Never raised as errors: a Topic/Series/Page can
    legitimately go back to draft after being linked, and that shouldn't
    block unrelated navigation edits from saving.
    """
    warnings = []
    if item.item_type == "topic":
        if item.topic is None:
            warnings.append("Linked Topic no longer exists.")
        elif item.topic.status != "published":
            warnings.append("Destination is not currently public (Topic is not published).")
    elif item.item_type == "series":
        if item.series is None:
            warnings.append("Linked Series no longer exists.")
        elif item.series.status != "published":
            warnings.append("Destination is not currently public (Series is not published).")
    elif item.item_type == "page":
        if item.page is None:
            warnings.append("Linked Page no longer exists.")
        elif item.page.status != "published":
            warnings.append("Destination is not currently public (Page is not published).")
    elif item.item_type in ("route", "external") and not item.url:
        warnings.append("No destination set yet.")
    return warnings


def _item_is_public(item):
    return item.visible and item.is_entity_public()


def serialize_public_menu_item(item):
    """The public shape for one navigation item: only what a header/mobile
    nav needs to render (label, resolved url, presentation hints), never
    raw entity FKs, warnings, or the item's internal id-as-editable-state.
    An invisible or no-longer-public child is dropped entirely — never
    sent to the client disabled, since that would leak its existence/label.
    A "group" item left with no visible children (nothing under it is
    public right now) is dropped too, rather than rendering an empty,
    non-clickable heading.
    """
    children = [serialize_public_menu_item(c) for c in item.children if _item_is_public(c)]
    children = [c for c in children if c is not None]
    if item.item_type == "group" and not children:
        return None
    return {
        "id": item.id,
        "label": item.label,
        "url": item.effective_url(),
        "itemType": item.item_type,
        "openNewTab": item.open_new_tab,
        "style": item.style,
        "children": children,
    }


def serialize_public_menu(menu):
    items = [serialize_public_menu_item(i) for i in menu.top_level_items() if _item_is_public(i)]
    items = [i for i in items if i is not None]
    return {"id": menu.id, "key": menu.key, "heading": menu.heading, "items": items}


def find_duplicate_top_level_destinations(items):
    """A same-menu, same-level duplicate destination is almost always a
    mistake (spec: "warn/prevent accidental duplicate top-level items");
    it's a warning, not a hard block, since a duplicate across different
    dropdowns can be intentional.
    """
    seen = {}
    warnings = {}
    for item in items:
        dest = item.effective_url()
        if not dest:
            continue
        if dest in seen:
            warnings.setdefault(item.id, []).append(f'Duplicate destination "{dest}" (also used by "{seen[dest]}").')
        else:
            seen[dest] = item.label
    return warnings
