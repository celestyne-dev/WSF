"""Homepage Builder — the two configurable, reusable section types:

* ``career_pathways`` ("Career Pathways / Start Here"): 2–8 editor-written
  pathway cards, each linking to a destination chosen with the SAME
  destination architecture as Navigation CMS (route / page / topic /
  series / external — app/services/navigation.py), never a fallback "/".
* ``content_collection``: one entity type (articles, people,
  opportunities, jobs, events, resources, learning), either hand-picked
  (manual: ordered slugs) or automatic (entity-aware sort + filters).

This module owns three things for both types:

1. ``normalize_module_config()`` — strict write-time validation plus
   normalization (keys irrelevant to the chosen entity/mode/destination
   are dropped, so stale config can never survive a save and GET→PUT→GET
   round-trips byte-for-byte).
2. ``resolve_homepage_extras()`` — public, anonymous resolution, done
   server-side ONCE per homepage request and embedded as ``resolved`` in
   both ``GET /public/homepage`` and the SPA bootstrap (so the browser
   makes no extra request per section) and reused by the prerender.
3. ``extra_module_warnings()`` — non-blocking Studio warnings.

Every public item is built with the same anonymous builder/schema the
entity's own public list endpoint uses (see app/services/public_hubs.py),
so a homepage section can never expose more than an anonymous API caller
already gets — entitlement-gated content stays gated.

"Most read" is deliberately NOT offered: the only popularity signal is the
public, unauthenticated, client-sent ``article_view`` analytics event,
which anyone can inflate, so it is not reliable enough to rank with.
Products are deferred too (no clean public product card contract on the
homepage yet).
"""
from datetime import date

from marshmallow import ValidationError
from sqlalchemy import or_
from sqlalchemy.orm import selectinload

from app.extensions import db

CAREER_PATHWAYS = "career_pathways"
CONTENT_COLLECTION = "content_collection"
EXTRA_MODULE_TYPES = (CAREER_PATHWAYS, CONTENT_COLLECTION)

# --- career pathways ---------------------------------------------------------

PATHWAY_MIN_CARDS = 2
PATHWAY_MAX_CARDS = 8

# Controlled icon set (frontend maps each key to a lucide-react icon in
# components/home/CareerPathwaysModule.jsx). Never a free-text icon name.
PATHWAY_ICONS = (
    "briefcase", "graduation-cap", "users", "book-open", "lightbulb", "compass", "calendar",
    "sparkles", "heart-handshake", "rocket", "target", "megaphone", "globe", "award",
)

# The Navigation CMS destination types minus "group" (a card must go
# somewhere). Resource/learning/opportunity hubs and detail pages are
# internal routes ("/resources", "/learning/some-course", ...).
PATHWAY_DESTINATION_TYPES = ("route", "page", "topic", "series", "external")

_PATHWAY_CARD_KEYS = {
    "title", "description", "eyebrow", "icon", "mediaId", "ariaLabel",
    "destinationType", "url", "pageId", "topicId", "seriesId", "openNewTab",
}
_PATHWAY_CONFIG_KEYS = {"eyebrow", "cards"}

# --- content collection -----------------------------------------------------

COLLECTION_ENTITY_TYPES = ("articles", "people", "opportunities", "jobs", "events", "resources", "learning")
COLLECTION_SELECTION_MODES = ("manual", "automatic")
COLLECTION_LAYOUTS = ("grid", "compact")
COLLECTION_MIN_ITEMS = 1
COLLECTION_MAX_ITEMS = 8
COLLECTION_DEFAULT_ITEMS = 4

_COLLECTION_CONFIG_KEYS = {"eyebrow", "entityType", "layout", "itemCount", "sort", "filters", "slugs"}


def _resource_choices():
    from app.models.resource import ACCESS_TYPES, RESOURCE_TYPES

    return ACCESS_TYPES, RESOURCE_TYPES


def _learning_types():
    from app.models.learning import LEARNING_PROGRAM_TYPES

    return LEARNING_PROGRAM_TYPES


# entity -> its automatic-mode sorts (first = default) and filters
# (filter key -> kind). "featured" as a sort means "featured items only,
# newest first"; "closing_soon" means a real future deadline, soonest
# first (undated records are excluded from it).
COLLECTION_SPECS = {
    "articles": {"sorts": ("latest", "featured"), "filters": {"topic": "topic", "series": "series"}},
    "people": {"sorts": ("newest", "featured"), "filters": {"series": "series"}},
    "opportunities": {"sorts": ("newest", "closing_soon"), "filters": {}},
    "jobs": {"sorts": ("newest", "closing_soon"), "filters": {}},
    "events": {"sorts": ("upcoming",), "filters": {}},
    "resources": {"sorts": ("newest", "featured"), "filters": {"accessType": "access_type", "resourceType": "resource_type"}},
    "learning": {"sorts": ("newest", "featured"), "filters": {"programType": "program_type"}},
}


def _error(message):
    return ValidationError(message, field_name="config")


def _plain_text(value, label, max_length, required=False):
    """Trimmed plain text (no markup), or None when blank and optional."""
    from app.services.footer import _HTML_TAG_RE

    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise _error(f"{label} is required.")
        return None
    if not isinstance(value, str):
        raise _error(f"{label} must be text.")
    value = value.strip()
    if len(value) > max_length:
        raise _error(f"{label} must be {max_length} characters or fewer.")
    if _HTML_TAG_RE.search(value):
        raise _error(f"{label} must be plain text (no HTML).")
    return value


def _positive_int(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _error(f"{label} must be a valid id.")
    return value


# --- write-time validation + normalization -----------------------------------


def _normalize_pathway_card(raw, index):
    from app.models.media import Media
    from app.services.navigation import clean_item_destination, validate_item_type_requirements

    label = f"Pathway card {index + 1}"
    if not isinstance(raw, dict):
        raise _error(f"{label} is not a valid card.")
    unknown = set(raw) - _PATHWAY_CARD_KEYS
    if unknown:
        raise _error(f"{label} has unknown field(s): {', '.join(sorted(unknown))}.")

    title = _plain_text(raw.get("title"), f"{label} title", 80, required=True)
    card = {
        "title": title,
        "description": _plain_text(raw.get("description"), f"{label} description", 240),
        "eyebrow": _plain_text(raw.get("eyebrow"), f"{label} label", 40),
        "ariaLabel": _plain_text(raw.get("ariaLabel"), f"{label} accessibility text", 160),
        "icon": None,
        "mediaId": None,
    }

    icon, media_id = raw.get("icon") or None, raw.get("mediaId") or None
    if icon and media_id:
        raise _error(f"{label}: choose an icon or an image, not both.")
    if icon:
        if icon not in PATHWAY_ICONS:
            raise _error(f"{label}: unknown icon.")
        card["icon"] = icon
    if media_id:
        media_id = _positive_int(media_id, f"{label} image")
        if db.session.get(Media, media_id) is None:
            raise _error(f"{label}: the selected image no longer exists.")
        card["mediaId"] = media_id

    dest_type = raw.get("destinationType")
    if dest_type not in PATHWAY_DESTINATION_TYPES:
        raise _error(f"{label} needs a destination (internal path, Page, Topic, Series or external URL).")
    snake = {
        "item_type": dest_type,
        "url": raw.get("url").strip() if isinstance(raw.get("url"), str) else raw.get("url"),
        "page_id": raw.get("pageId"),
        "topic_id": raw.get("topicId"),
        "series_id": raw.get("seriesId"),
        "open_new_tab": bool(raw.get("openNewTab")),
    }
    for key in ("page_id", "topic_id", "series_id"):
        if snake[key] is not None and snake[key] != "":
            snake[key] = _positive_int(snake[key], f"{label} destination")
        else:
            snake[key] = None
    snake = clean_item_destination(snake)
    if snake.get("url") is not None and len(snake["url"]) > 500:
        raise _error(f"{label}: the link is too long.")
    try:
        validate_item_type_requirements(snake)
    except ValidationError as exc:
        messages = exc.messages if isinstance(exc.messages, list) else [str(exc.messages)]
        raise _error(f"{label}: {' '.join(str(m) for m in messages)}")
    card.update({
        "destinationType": dest_type,
        "url": snake["url"],
        "pageId": snake["page_id"],
        "topicId": snake["topic_id"],
        "seriesId": snake["series_id"],
        "openNewTab": snake["open_new_tab"],
    })
    return card


def normalize_pathways_config(config, enabled):
    if not isinstance(config, dict):
        raise _error("Invalid configuration.")
    unknown = set(config) - _PATHWAY_CONFIG_KEYS
    if unknown:
        raise _error(f"Unknown setting(s): {', '.join(sorted(unknown))}.")
    cards_raw = config.get("cards") or []
    if not isinstance(cards_raw, list):
        raise _error("Pathway cards must be a list.")
    if len(cards_raw) > PATHWAY_MAX_CARDS:
        raise _error(f"Career Pathways supports at most {PATHWAY_MAX_CARDS} cards.")
    if enabled and len(cards_raw) < PATHWAY_MIN_CARDS:
        raise _error(f"Add at least {PATHWAY_MIN_CARDS} pathway cards (or disable the section).")
    return {
        "eyebrow": _plain_text(config.get("eyebrow"), "Eyebrow", 60),
        "cards": [_normalize_pathway_card(card, i) for i, card in enumerate(cards_raw)],
    }


def _validate_filter_value(kind, value, label):
    from app.models.taxonomy import Series, Topic

    if kind in ("topic", "series"):
        if not isinstance(value, str) or not value.strip():
            raise _error(f"{label} must be a {kind} slug.")
        model = Topic if kind == "topic" else Series
        if model.query.filter_by(slug=value.strip()).first() is None:
            raise _error(f"{label}: that {kind.title()} doesn't exist.")
        return value.strip()
    if kind == "access_type":
        allowed = _resource_choices()[0]
    elif kind == "resource_type":
        allowed = _resource_choices()[1]
    else:
        allowed = _learning_types()
    if value not in allowed:
        raise _error(f"{label} must be one of: {', '.join(allowed)}.")
    return value


def _entity_model(entity):
    from app.models.article import Article
    from app.models.learning import LearningProgram
    from app.models.opportunity import Event, Job, Opportunity
    from app.models.people import Person
    from app.models.resource import Resource

    return {
        "articles": Article, "people": Person, "opportunities": Opportunity, "jobs": Job,
        "events": Event, "resources": Resource, "learning": LearningProgram,
    }[entity]


def normalize_collection_config(config, selection_mode):
    if not isinstance(config, dict):
        raise _error("Invalid configuration.")
    unknown = set(config) - _COLLECTION_CONFIG_KEYS
    if unknown:
        raise _error(f"Unknown setting(s): {', '.join(sorted(unknown))}.")
    entity = config.get("entityType")
    if entity not in COLLECTION_ENTITY_TYPES:
        raise _error(f"Choose what this collection shows ({', '.join(COLLECTION_ENTITY_TYPES)}).")
    if selection_mode not in COLLECTION_SELECTION_MODES:
        raise ValidationError("Choose manual or automatic selection.", field_name="selection_mode")
    layout = config.get("layout") or COLLECTION_LAYOUTS[0]
    if layout not in COLLECTION_LAYOUTS:
        raise _error(f"Layout must be one of: {', '.join(COLLECTION_LAYOUTS)}.")
    spec = COLLECTION_SPECS[entity]
    normalized = {
        "eyebrow": _plain_text(config.get("eyebrow"), "Eyebrow", 60),
        "entityType": entity,
        "layout": layout,
    }

    if selection_mode == "manual":
        # Mode-irrelevant keys (sort/filters/itemCount) are dropped, never kept stale.
        slugs = config.get("slugs") or []
        if not isinstance(slugs, list) or not all(isinstance(s, str) and s.strip() for s in slugs):
            raise _error("Selected items must be a list of slugs.")
        slugs = [s.strip() for s in slugs]
        if not slugs:
            raise _error("Pick at least one item, or switch to automatic selection.")
        if len(slugs) > COLLECTION_MAX_ITEMS:
            raise _error(f"Pick at most {COLLECTION_MAX_ITEMS} items.")
        if len(set(slugs)) != len(slugs):
            raise _error("Each item can only be picked once.")
        model = _entity_model(entity)
        existing = {row.slug for row in model.query.filter(model.slug.in_(slugs)).all()}
        missing = [s for s in slugs if s not in existing]
        if missing:
            raise _error(f"These items don't exist: {', '.join(missing)}.")
        normalized["slugs"] = slugs
        return normalized

    item_count = config.get("itemCount", COLLECTION_DEFAULT_ITEMS)
    if isinstance(item_count, bool) or not isinstance(item_count, int) or not (
        COLLECTION_MIN_ITEMS <= item_count <= COLLECTION_MAX_ITEMS
    ):
        raise _error(f"Show between {COLLECTION_MIN_ITEMS} and {COLLECTION_MAX_ITEMS} items.")
    sort = config.get("sort") or spec["sorts"][0]
    if sort not in spec["sorts"]:
        raise _error(f"{entity.title()} can be sorted by: {', '.join(spec['sorts'])}.")
    filters_raw = config.get("filters") or {}
    if not isinstance(filters_raw, dict):
        raise _error("Filters must be an object.")
    unsupported = set(filters_raw) - set(spec["filters"])
    if unsupported:
        raise _error(f"{entity.title()} can't be filtered by: {', '.join(sorted(unsupported))}.")
    filters = {}
    for key, kind in spec["filters"].items():
        value = filters_raw.get(key)
        if value is None or value == "":
            continue
        filters[key] = _validate_filter_value(kind, value, f"Filter {key}")
    normalized.update({"itemCount": item_count, "sort": sort, "filters": filters})
    return normalized


def _validate_section_cta(data):
    """New types: the section CTA is all-or-nothing, and an internal path
    can't point into /admin or /api (navigation's own route rule)."""
    from app.services.navigation import validate_route_url

    label, url = data.get("cta_label"), data.get("cta_url")
    label = label.strip() if isinstance(label, str) else label
    url = url.strip() if isinstance(url, str) else url
    if bool(label) != bool(url):
        raise ValidationError("A section link needs both a label and a destination.", field_name="cta_url")
    if url and url.startswith("/"):
        validate_route_url(url, field_name="cta_url")
    data["cta_label"], data["cta_url"] = label or None, url or None
    # These sections have a single CTA; a stale secondary one never persists.
    data["secondary_cta_label"] = data["secondary_cta_url"] = None


def normalize_module_config(data):
    """Called from HomepageModuleInputSchema's post_load. Mutates and
    returns `data` with a normalized `config` for the two extra types;
    every other type is untouched (full backward compatibility)."""
    module_type = data.get("type")
    if module_type == CAREER_PATHWAYS:
        data["config"] = normalize_pathways_config(data.get("config") or {}, data.get("enabled", True))
        data["selection_mode"] = None
        _validate_section_cta(data)
    elif module_type == CONTENT_COLLECTION:
        data["config"] = normalize_collection_config(data.get("config") or {}, data.get("selection_mode"))
        _validate_section_cta(data)
    return data


# --- public resolution ---------------------------------------------------------


def _resolve_pathway_cards(modules):
    """All pathway modules' cards in one batched pass (≤4 queries total)."""
    from app.models.media import Media
    from app.models.page import Page
    from app.models.taxonomy import Series, Topic
    from app.services.navigation import validate_external_url, validate_route_url

    ids = {"pageId": set(), "topicId": set(), "seriesId": set(), "mediaId": set()}
    for module in modules:
        for card in (module.config or {}).get("cards") or []:
            if isinstance(card, dict):
                for key in ids:
                    if isinstance(card.get(key), int):
                        ids[key].add(card[key])

    def _published(model, wanted):
        if not wanted:
            return {}
        return {row.id: row for row in model.query.filter(model.id.in_(wanted), model.status == "published").all()}

    pages = _published(Page, ids["pageId"])
    topics = _published(Topic, ids["topicId"])
    series = _published(Series, ids["seriesId"])
    media = {m.id: m for m in Media.query.filter(Media.id.in_(ids["mediaId"])).all()} if ids["mediaId"] else {}

    def _href(card):
        dest = card.get("destinationType")
        try:
            if dest == "route":
                return validate_route_url(card.get("url")), "internal"
            if dest == "external":
                return validate_external_url(card.get("url")), "external"
        except ValidationError:
            return None, None
        if dest == "page" and card.get("pageId") in pages:
            return f"/{pages[card['pageId']].slug}", "internal"
        if dest == "topic" and card.get("topicId") in topics:
            return f"/topics/{topics[card['topicId']].slug}", "internal"
        if dest == "series" and card.get("seriesId") in series:
            return f"/series/{series[card['seriesId']].slug}", "internal"
        return None, None

    resolved = {}
    for module in modules:
        cards = []
        for card in (module.config or {}).get("cards") or []:
            if not isinstance(card, dict) or not card.get("title"):
                continue
            href, link_type = _href(card)
            if not href:
                continue  # unpublished / missing / invalid destination: omitted, never "/"
            image = media.get(card.get("mediaId"))
            cards.append({
                "title": card["title"],
                "description": card.get("description"),
                "eyebrow": card.get("eyebrow"),
                "ariaLabel": card.get("ariaLabel"),
                "icon": card.get("icon") if card.get("icon") in PATHWAY_ICONS else None,
                "image": {
                    "url": image.public_url, "alt": image.alt_text or "", "width": image.width, "height": image.height,
                } if image is not None else None,
                "href": href,
                "linkType": link_type,
                "openNewTab": bool(card.get("openNewTab")) and link_type == "external",
            })
        resolved[module.id] = {"cards": cards}
    return resolved


def _published_article_rows(query):
    from app.models.article import Article

    return query.filter(Article.status == "published")


def _query_collection(entity, config, manual_slugs, limit):
    """Rows for one collection, public anonymous visibility only, in
    display order. Over-fetches where visibility needs a Python check."""
    from app.extensions import db as _db
    from app.models.article import Article
    from app.models.learning import LearningProgram
    from app.models.opportunity import Event, Job, Opportunity
    from app.models.people import Person
    from app.models.resource import Resource
    from app.models.taxonomy import Series, Topic

    today = date.today()
    sort = config.get("sort")
    filters = config.get("filters") or {}

    if entity == "articles":
        query = _published_article_rows(Article.query.options(
            selectinload(Article.author), selectinload(Article.topics), selectinload(Article.tags),
            selectinload(Article.series), selectinload(Article.category), selectinload(Article.hero_media),
        ))
        if not manual_slugs:
            if filters.get("topic"):
                query = query.filter(Article.topics.any(Topic.slug == filters["topic"]))
            if filters.get("series"):
                query = query.filter(Article.series.has(Series.slug == filters["series"]))
            if sort == "featured":
                query = query.filter(Article.featured.is_(True))
            query = query.order_by(Article.publish_date.desc().nullslast(), Article.id.desc())
        model = Article
    elif entity == "people":
        query = Person.query.options(selectinload(Person.organization), selectinload(Person.series)).filter(
            Person.status == "published"
        )
        if not manual_slugs:
            if filters.get("series"):
                query = query.filter(Person.series.any(Series.slug == filters["series"]))
            if sort == "featured":
                query = query.filter(Person.featured.is_(True))
            query = query.order_by(Person.created_at.desc(), Person.id.desc())
        model = Person
    elif entity in ("opportunities", "jobs"):
        model = Opportunity if entity == "opportunities" else Job
        query = model.query.options(selectinload(model.organization))
        if entity == "opportunities":
            query = query.options(selectinload(Opportunity.countries_eligible), selectinload(Opportunity.topics))
            query = query.filter(Opportunity.status == "published")
        else:
            query = query.filter(Job.status.in_(["published", "scheduled"]))
        # Expired records never show, in either mode.
        query = query.filter(or_(model.expiry_date.is_(None), model.expiry_date >= today))
        query = query.filter(or_(model.deadline.is_(None), model.deadline >= today))
        if not manual_slugs:
            if sort == "closing_soon":
                query = query.filter(model.deadline.isnot(None)).order_by(model.deadline.asc(), model.id.asc())
            else:
                query = query.order_by(model.published_date.desc().nullslast(), model.created_at.desc(), model.id.desc())
    elif entity == "events":
        model = Event
        query = (
            Event.query.options(selectinload(Event.organizer), selectinload(Event.speakers), selectinload(Event.sponsors))
            .filter(Event.status.in_(["published", "cancelled", "postponed", "scheduled"]))
            .filter(_db.func.coalesce(Event.end_date, Event.date) >= today)
        )
        if not manual_slugs:
            query = query.order_by(Event.date.asc(), Event.id.asc())
    elif entity == "resources":
        model = Resource
        query = Resource.query.options(
            selectinload(Resource.images), selectinload(Resource.topics), selectinload(Resource.tags),
            selectinload(Resource.author), selectinload(Resource.sponsor), selectinload(Resource.cover_media),
        ).filter(Resource.status.in_(["published", "scheduled"]))
        if not manual_slugs:
            if filters.get("accessType"):
                query = query.filter(Resource.access_type == filters["accessType"])
            if filters.get("resourceType"):
                query = query.filter(Resource.type == filters["resourceType"])
            if sort == "featured":
                query = query.filter(Resource.featured.is_(True))
            query = query.order_by(Resource.published_date.desc().nullslast(), Resource.id.desc())
    else:  # learning
        model = LearningProgram
        query = LearningProgram.query.options(
            selectinload(LearningProgram.primary_instructor), selectinload(LearningProgram.co_instructors),
            selectinload(LearningProgram.provider_organization), selectinload(LearningProgram.topics),
            selectinload(LearningProgram.event_links), selectinload(LearningProgram.hero_media),
        ).filter(LearningProgram.status == "published")
        if not manual_slugs:
            if filters.get("programType"):
                query = query.filter(LearningProgram.program_type == filters["programType"])
            if sort == "featured":
                query = query.filter(LearningProgram.featured.is_(True))
            query = query.order_by(LearningProgram.created_at.desc(), LearningProgram.id.desc())

    if manual_slugs:
        rows = query.filter(model.slug.in_(manual_slugs)).all()
        by_slug = {row.slug: row for row in rows}
        return [by_slug[s] for s in manual_slugs if s in by_slug]
    # Jobs/events/resources apply one more public-visibility check in Python
    # (the same helper their public endpoints use), so they get headroom;
    # every other entity's SQL filter is already exact.
    return query.limit(limit * 3 if entity in _PYTHON_VISIBILITY_CHECKED else limit).all()


_PYTHON_VISIBILITY_CHECKED = ("jobs", "events", "resources")


def _build_collection_items(entity, rows, limit):
    """Each row through the same anonymous public builder its own list
    endpoint uses; rows that fail the public visibility check are skipped."""
    if entity == "articles":
        from app.schemas.article import PublicArticleSchema, article_summary_schema

        # The public list's summary shape, minus the author's article_count:
        # no article card reads it and it costs one COUNT query per card.
        schema = PublicArticleSchema(many=True, exclude=tuple(article_summary_schema().exclude) + ("author.article_count",))
        return schema.dump(rows[:limit])
    if entity == "people":
        from app.schemas.people import PersonSchema
        from app.services.public_visibility import public_person_dump

        schema = PersonSchema()
        return [public_person_dump(schema.dump(p), p) for p in rows[:limit]]
    if entity == "opportunities":
        from app.api.v1.opportunities import build_public_opportunity_payload

        return [build_public_opportunity_payload(o, None, detail=False) for o in rows[:limit]]
    if entity == "jobs":
        from app.api.v1.jobs import build_public_job_payload
        from app.services.job_access import is_job_application_open

        return [build_public_job_payload(j, None, detail=False) for j in [j for j in rows if is_job_application_open(j)][:limit]]
    if entity == "events":
        from app.schemas.opportunity import EventSchema
        from app.services.event_registrations import is_event_publicly_visible
        from app.services.public_visibility import public_event_dump

        schema = EventSchema()
        return [public_event_dump(schema.dump(e), e) for e in [e for e in rows if is_event_publicly_visible(e)][:limit]]
    if entity == "resources":
        from app.api.v1.resources import build_public_resource_payload, prefetch_linked_products

        # Visibility first, then the limit, then the payload build — with
        # linked products fetched in one query, not one per card.
        visible = [r for r in rows if r.is_publicly_visible()][:limit]
        products = prefetch_linked_products(visible)
        return [build_public_resource_payload(r, None, linked_products=products) for r in visible]
    from app.schemas.learning import learning_program_summary_schema
    from app.services.public_visibility import public_learning_dump

    schema = learning_program_summary_schema()
    return [public_learning_dump(schema.dump(p), p) for p in rows[:limit]]


def resolve_collection(module):
    config = module.config or {}
    entity = config.get("entityType")
    if entity not in COLLECTION_ENTITY_TYPES:
        return {"entityType": None, "items": []}
    manual = module.selection_mode == "manual"
    slugs = [s for s in (config.get("slugs") or []) if isinstance(s, str) and s][:COLLECTION_MAX_ITEMS] if manual else []
    if manual and not slugs:
        return {"entityType": entity, "items": []}
    limit = len(slugs) if manual else config.get("itemCount") or COLLECTION_DEFAULT_ITEMS
    if not isinstance(limit, int) or limit < 1:
        limit = COLLECTION_DEFAULT_ITEMS
    limit = min(limit, COLLECTION_MAX_ITEMS)
    rows = _query_collection(entity, config, slugs, limit)
    return {"entityType": entity, "items": _build_collection_items(entity, rows, limit)}


def resolve_homepage_extras(modules):
    """{module.id: resolved} for every career_pathways/content_collection
    module in `modules` — resolved once per homepage request."""
    pathways = [m for m in modules if m.type == CAREER_PATHWAYS]
    resolved = _resolve_pathway_cards(pathways) if pathways else {}
    for module in modules:
        if module.type == CONTENT_COLLECTION:
            resolved[module.id] = resolve_collection(module)
    return resolved


def public_module_config(module):
    """The public endpoint exposes only the display fields of these two
    types' config — never raw destination ids or manually picked slugs
    (which could name a draft record)."""
    config = module.config or {}
    if module.type == CAREER_PATHWAYS:
        return {"eyebrow": config.get("eyebrow")}
    return {"eyebrow": config.get("eyebrow"), "entityType": config.get("entityType"), "layout": config.get("layout")}


def attach_public_extras(dumped_modules, modules, resolved):
    """Post-process a HomepageModuleSchema(many=True) dump in place."""
    by_id = {m.id: m for m in modules}
    for entry in dumped_modules:
        module = by_id.get(entry.get("id"))
        if module is not None and module.type in EXTRA_MODULE_TYPES:
            entry["config"] = public_module_config(module)
            entry["resolved"] = resolved.get(module.id) or ({"cards": []} if module.type == CAREER_PATHWAYS else {"items": []})
    return dumped_modules


# --- Studio warnings -------------------------------------------------------------


def extra_module_warnings(module):
    warnings = []
    config = module.config or {}
    if module.type == CAREER_PATHWAYS:
        cards = config.get("cards") or []
        live = _resolve_pathway_cards([module]).get(module.id, {}).get("cards", [])
        hidden = len(cards) - len(live)
        if hidden:
            warnings.append(
                f"{hidden} pathway card(s) point to an unpublished or missing destination and are hidden publicly."
            )
        if len(live) == 0:
            warnings.append("No pathway card currently has a live destination — the section is hidden.")
        elif len(live) < PATHWAY_MIN_CARDS:
            warnings.append(f"Only {len(live)} pathway card is live; at least {PATHWAY_MIN_CARDS} are recommended.")
    elif module.type == CONTENT_COLLECTION:
        result = resolve_collection(module)
        if module.selection_mode == "manual":
            hidden = len(config.get("slugs") or []) - len(result["items"])
            if hidden > 0:
                warnings.append(f"{hidden} selected item(s) are unpublished, expired or past and are hidden publicly.")
        if not result["items"]:
            warnings.append("This collection currently has no public items — the section is hidden.")
    return warnings
