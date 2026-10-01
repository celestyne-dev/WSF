import re

from marshmallow import ValidationError

from app.extensions import db
from app.models.cms import MENU_MAX_DEPTH, Menu, MenuItem
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


# ---------------------------------------------------------------------------
# Default-navigation bootstrap. Idempotent and safe to run against a real
# production database — the same category as seed_roles_and_permissions()/
# seed_countries(), never seed_demo_content() (which must never run in
# production). See seed_default_navigation()'s own docstring below for why
# this exists: an already-seeded "primary"/"secondary" menu must be healed
# in place (missing sections added) rather than left permanently stuck at
# whatever subset of sections existed the first time it was ever seeded.
# ---------------------------------------------------------------------------


def _canonical_effective_url(data):
    """The real destination a canonical item definition resolves to,
    computed the same way MenuItem.effective_url() resolves a real row —
    used so a destination-typed canonical item and an existing item are
    compared by where they actually point, not by which representation
    (route vs. entity-linked) happens to store that destination. Returns
    None for a "group" item (no destination of its own) or for an
    entity-typed item whose target doesn't exist/resolve.
    """
    item_type = data.get("item_type", "route")
    if item_type == "page":
        page = Page.query.get(data.get("page_id"))
        return f"/{page.slug}" if page else None
    if item_type == "topic":
        topic = Topic.query.get(data.get("topic_id"))
        return f"/topics/{topic.slug}" if topic else None
    if item_type == "series":
        series = Series.query.get(data.get("series_id"))
        return f"/series/{series.slug}" if series else None
    if item_type in ("route", "external"):
        return data.get("url")
    return None


def _canonical_item_key(data):
    """The destination identity a canonical default item and an existing
    MenuItem are compared by — deliberately never the label, so an admin's
    own relabeling of an existing item (e.g. shortening "WSF Weekly
    Newsletter" back to "Newsletter") is never treated as "missing" and
    never overwritten on a later heal run.

    Destination-typed items (route/external/page/topic/series) are
    identified by their EFFECTIVE public destination rather than their
    raw stored field, so an existing legacy route item (url="/about") and
    a newer canonical Page-backed item (page_id=<the About page>) that
    both resolve to "/about" compare equal — healing must never add a
    second About item merely because the underlying representation
    changed (see the identical rule already used by
    app/services/footer.py:heal_footer_defaults for the footer's Legal/
    About links). "group" items (e.g. the primary menu's "Topics"
    dropdown) have no public destination of their own, so they keep a
    separate, stable (item_type, label) identity — two different empty
    dropdowns must never be treated as "the same thing" just because
    neither has a URL. An entity-typed item whose target doesn't exist
    yet falls back to a type+raw-field identity so it isn't silently
    treated as satisfying nothing.
    """
    item_type = data.get("item_type", "route")
    if item_type == "group":
        return ("group", data.get("label"))
    dest = _canonical_effective_url(data)
    if dest is not None:
        return ("dest", dest)
    if item_type == "page":
        return (item_type, data.get("page_id"))
    if item_type == "topic":
        return (item_type, data.get("topic_id"))
    if item_type == "series":
        return (item_type, data.get("series_id"))
    return (item_type, data.get("label"))


def _existing_item_key(item):
    """Mirrors _canonical_item_key() exactly, using the real row's
    effective_url() instead of recomputing it from raw fields.
    """
    if item.item_type == "group":
        return ("group", item.label)
    dest = item.effective_url()
    if dest is not None:
        return ("dest", dest)
    if item.item_type == "page":
        return (item.item_type, item.page_id)
    if item.item_type == "topic":
        return (item.item_type, item.topic_id)
    if item.item_type == "series":
        return (item.item_type, item.series_id)
    return (item.item_type, item.label)


def _dedupe_canonical_destinations(existing_items, canonical_dest_keys):
    """Repairs the specific regression an older version of this healer
    could create: because identity used to be (item_type, raw field)
    rather than effective destination, re-running `flask seed-navigation`
    against a database with a legacy route item (e.g. url="/about")
    added a SECOND, Page-backed item for the same canonical destination
    instead of recognizing the legacy one as already satisfying it (see
    _canonical_item_key()'s docstring).

    Deliberately narrow: only collapses a destination that is part of
    THIS menu's own canonical set (`canonical_dest_keys`, the "dest"-
    tagged keys this call's canonical_items actually define) — an
    unrelated admin-created duplicate (two custom links that happen to
    share a destination this function never seeded) is never touched,
    since that is not this regression. Among items sharing a canonical
    destination, the one with the lowest id (the one that existed first)
    is kept; every later duplicate is deleted. A destination with only
    one occurrence is left completely alone. Returns the set of deleted
    item ids so the caller can drop them from its own in-memory list.
    """
    by_dest = {}
    for item in existing_items:
        key = _existing_item_key(item)
        if key[0] != "dest" or key not in canonical_dest_keys:
            continue
        by_dest.setdefault(key, []).append(item)

    removed_ids = set()
    for items in by_dest.values():
        if len(items) < 2:
            continue
        items = sorted(items, key=lambda it: it.id)
        for duplicate in items[1:]:
            db.session.delete(duplicate)
            removed_ids.add(duplicate.id)
    return removed_ids


def _build_menu_item(menu_id, data, parent_id=None):
    item = MenuItem(
        menu_id=menu_id,
        parent_id=parent_id,
        label=data["label"],
        item_type=data.get("item_type", "route"),
        url=data.get("url"),
        topic_id=data.get("topic_id"),
        series_id=data.get("series_id"),
        page_id=data.get("page_id"),
        open_new_tab=data.get("open_new_tab", False),
        style=data.get("style", "standard"),
        sort_order=0,
        visible=True,
    )
    db.session.add(item)
    db.session.flush()  # assign item.id before recursing into children
    for index, child_data in enumerate(data.get("children") or []):
        child = _build_menu_item(menu_id, child_data, parent_id=item.id)
        child.sort_order = index
    return item


def heal_menu_defaults(key, canonical_items):
    """Ensure every canonical top-level destination in `canonical_items`
    is present somewhere in the `key` menu, adding only what's missing —
    never renaming, reordering, or removing anything that already exists,
    whether that item was seeded earlier or hand-added/edited by an admin
    through AdminNavigation. Idempotent: once every canonical destination
    is present, a further call is a no-op.

    This is the fix for a real regression class: "primary"/"secondary"
    were seeded once (see seed_default_navigation()) back when the site
    had fewer top-level sections (e.g. before Events/Community/Shop/
    Partnerships existed), and the old create-only seed guard
    (`_seed_menu_if_empty`, still used for the footer_* menus) never adds
    anything to a menu that already has at least one item — so a database
    seeded early is permanently stuck missing every section added since,
    with no automated way to catch back up. This heals that in place
    without touching what's already there, and is called from both
    `flask seed-navigation` (safe on a real production database) and
    `flask seed-demo` (so a fresh dev database still gets the full menu on
    the very first run, same as before).

    Also repairs the one duplicate this healer could previously create
    itself, before destination identity accounted for route-vs-entity
    representations of the same URL (see _dedupe_canonical_destinations()):
    a database that already has both a legacy route item and a newer
    Page-backed item for the same canonical destination (e.g. two "About"
    entries, one url="/about" and one page_id=<About page>) is collapsed
    back down to one on the next heal, keeping the item that existed
    first and touching nothing else.
    """
    menu = Menu.query.filter_by(key=key).first()
    if menu is None:
        menu = Menu(key=key)
        db.session.add(menu)
        db.session.flush()

    existing_items = MenuItem.query.filter_by(menu_id=menu.id, parent_id=None).order_by(MenuItem.sort_order).all()

    canonical_keys = [_canonical_item_key(c) for c in canonical_items]
    canonical_dest_keys = {k for k in canonical_keys if k[0] == "dest"}

    removed_ids = _dedupe_canonical_destinations(existing_items, canonical_dest_keys)
    if removed_ids:
        existing_items = [it for it in existing_items if it.id not in removed_ids]

    existing_keys = {_existing_item_key(it) for it in existing_items}
    rank_by_key = {k: idx for idx, k in enumerate(canonical_keys)}

    missing = [(idx, c) for idx, c in enumerate(canonical_items) if canonical_keys[idx] not in existing_keys]
    if not missing:
        return  # every canonical destination already exists — nothing to heal

    merged = list(existing_items)
    for rank, canonical in missing:
        new_item = _build_menu_item(menu.id, canonical)
        # Insert right before the first still-existing item that comes
        # after this one in canonical order, wherever that sibling
        # currently sits — an admin-added custom item (no canonical rank
        # at all) never blocks or repositions this insertion.
        insert_at = len(merged)
        for pos, existing in enumerate(merged):
            existing_rank = rank_by_key.get(_existing_item_key(existing))
            if existing_rank is not None and existing_rank > rank:
                insert_at = pos
                break
        merged.insert(insert_at, new_item)

    for index, item in enumerate(merged):
        item.sort_order = index
        db.session.add(item)


def seed_default_navigation():
    """Idempotent, production-safe default-navigation bootstrap for the
    two structural header menus. Safe to run on a completely empty
    database (creates "primary"/"secondary" from scratch, same as a first
    `seed-demo` run always has) and equally safe to run repeatedly against
    a real production database that has never run — and must never run —
    `seed-demo` (see heal_menu_defaults()'s docstring for why this is not
    a create-only guard). The "Topics" dropdown is built from whatever
    Topic rows actually exist and are published at the time this runs,
    never a hardcoded demo slug list, so it stays correct as real topics
    are added later — an empty "Topics" group (no topics published yet)
    is expected and simply won't render publicly until the CMS has
    published at least one Topic (see serialize_public_menu_item).
    """
    about_page = Page.query.filter_by(key="about").first()
    topics = Topic.query.filter_by(status="published").order_by(Topic.sort_order, Topic.id).all()

    primary_items = [
        {"label": "Stories", "item_type": "route", "url": "/topics"},
        {
            "label": "Topics",
            "item_type": "group",
            "children": [{"label": t.name, "item_type": "topic", "topic_id": t.id} for t in topics],
        },
        {
            "label": "People",
            "item_type": "route",
            "url": "/people",
            "children": [
                {"label": "People Directory", "item_type": "route", "url": "/people"},
                {"label": "Authors", "item_type": "route", "url": "/authors"},
                {"label": "Series", "item_type": "route", "url": "/series"},
            ],
        },
        {"label": "Opportunities", "item_type": "route", "url": "/opportunities"},
        {"label": "Resources", "item_type": "route", "url": "/resources"},
        {"label": "Events", "item_type": "route", "url": "/events"},
        {"label": "Community", "item_type": "route", "url": "/community"},
        {"label": "Shop", "item_type": "route", "url": "/shop"},
    ]
    secondary_items = [
        {"label": "WSF Weekly Newsletter", "item_type": "route", "url": "/newsletter"},
        {"label": "Partner With Us", "item_type": "route", "url": "/partnerships"},
    ]
    if about_page is not None:
        secondary_items.append({"label": "About", "item_type": "page", "page_id": about_page.id})

    heal_menu_defaults("primary", primary_items)
    heal_menu_defaults("secondary", secondary_items)
    # Self-contained commit — same convention as seed_roles_and_permissions()/
    # seed_countries(), since `flask seed-navigation` calls this directly
    # with no other commit in the request/command lifecycle. Calling this
    # from inside seed_demo_content() (which commits again at its own end)
    # is still safe: this only flushes work that function has already
    # finished building by the time it gets here.
    db.session.commit()
