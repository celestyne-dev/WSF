"""WSF Career Hub — a public discovery layer over the EXISTING Resources and
Learning programs. Nothing is copied into a new table: every result is a
live Resource or LearningProgram row, filtered by the same public
visibility rules their own public endpoints use, and rendered as one
normalized card shape so the page can mix both sources.

Classification reuses what already exists:
  * format  — Resource.type (extended with the Career Hub formats) and
              LearningProgram.program_type, mapped to one stable key set;
  * goal    — Topic.career_goal on the published Topics an item already
              carries (no second taxonomy, no per-item goal field);
  * access  — Resource.access_type / LearningProgram.access_type, grouped
              into Free / WSF Circle / Premium without mislabelling;
  * Circle  — resource_circle_inclusion / program_circle_inclusion, which
              sit beside the authoritative access checks they mirror.

Everything here is anonymous and display-only. Actual access, downloads,
purchases and enrollment are still enforced by the original Resource and
Learning endpoints; nothing here grants or implies an entitlement.

Query shape (no N+1, no whole-table load): one UNION ALL over both sources
selects only (source, id) for the requested page, ordered and limited in
SQL; one COUNT over the same union gives the total; then each source's
rows for that page are loaded in one batched query with eager loads, and
payment settings are read once for every price on the page.
"""
from datetime import date, datetime, time, timezone

from sqlalchemy import DateTime, and_, cast, false, func, literal, or_, select, true, union_all
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.utils.responses import ApiError

# --- vocabulary ------------------------------------------------------------------

FORMAT_LABELS = {
    "playbook": "Playbook",
    "workbook": "Workbook",
    "worksheet": "Worksheet",
    "toolkit": "Toolkit",
    "checklist": "Checklist",
    "scripts": "Scripts",
    "template": "Template",
    "planner": "Planner",
    "guide": "Guide",
    "challenge": "Challenge",
    "assessment": "Assessment",
    "research": "Research",
    "report": "Report",
    "ebook": "eBook",
    "course": "Course",
    "masterclass": "Masterclass",
    "program": "Program",
    "learning_series": "Learning series",
    "other": "Other",
}

# Resource.type (stored, title-case) -> format key. Legacy values with no
# Career Hub meaning of their own fall under "other" (never a video format).
RESOURCE_TYPE_FORMATS = {
    "Guide": "guide", "Workbook": "workbook", "Worksheet": "worksheet", "Template": "template",
    "Checklist": "checklist", "Planner": "planner", "Toolkit": "toolkit", "Ebook": "ebook", "Report": "report",
    "Playbook": "playbook", "Scripts": "scripts", "Challenge": "challenge", "Assessment": "assessment",
    "Research": "research", "Other": "other", "Download": "other", "External Resource": "other",
    "Video Resource": "other",
}
LEARNING_TYPE_FORMATS = {
    "course": "course", "masterclass": "masterclass", "program": "program",
    "learning_series": "learning_series", "challenge": "challenge",
}

GOAL_LABELS = {
    "find_a_job": "Find a job",
    "get_promoted": "Get promoted",
    "earn_more": "Earn more",
    "build_visibility": "Build visibility",
    "leadership": "Lead better",
    "career_change": "Change careers",
    "return_to_work": "Return to work",
    "networking": "Network better",
    "workplace_challenges": "Handle workplace challenges",
    "productivity": "Work smarter",
    "confidence": "Build confidence",
    "ai_at_work": "Use AI at work",
    "entrepreneurship": "Grow a business",
}
# The goals shown as shortcut pills at the top of the page.
FEATURED_GOALS = (
    "find_a_job", "get_promoted", "earn_more", "build_visibility", "leadership", "career_change",
    "return_to_work", "ai_at_work",
)

ACCESS_FILTERS = {"free": "Free", "circle": "WSF Circle", "premium": "Premium"}
SORTS = {"newest": "Newest", "featured": "Featured", "recently_added": "Recently added"}
DEFAULT_SORT = "newest"
DEFAULT_PAGE_SIZE = 12
MAX_PAGE_SIZE = 24
MAX_PAGE = 200
NEW_THIS_MONTH_LIMIT = 6

CIRCLE_INCLUSION_LABELS = {
    "all": "Included with WSF Circle",
    "yearly_level": "Included with Yearly & Lifetime WSF Circle",
}


def url_value(key):
    """Stable, clean URL value for a goal/format key (get_promoted -> get-promoted)."""
    return key.replace("_", "-")


def from_url_value(value):
    return (value or "").strip().lower().replace("-", "_")


# --- per-item display helpers ------------------------------------------------------

_UNIT_WORDS = {"minutes": ("min", "min"), "hours": ("hour", "hours"), "days": ("day", "days"), "weeks": ("week", "weeks")}


def format_estimated_time(value, max_value, unit):
    """"10 min", "30–45 min", "1 hour", "1–2 hours", "7 days", "4 weeks",
    "Self-paced" — or None when no estimate is set."""
    if unit == "self_paced":
        return "Self-paced"
    if unit not in _UNIT_WORDS or not value:
        return None
    singular, plural = _UNIT_WORDS[unit]
    if max_value and max_value > value:
        return f"{value}–{max_value} {plural}"
    return f"{value} {singular if value == 1 else plural}"


def resource_estimated_time(resource):
    label = format_estimated_time(resource.estimated_time_value, resource.estimated_time_max_value, resource.estimated_time_unit)
    if label is None:
        return None
    return {
        "label": label,
        "unit": resource.estimated_time_unit,
        "value": resource.estimated_time_value,
        "maxValue": resource.estimated_time_max_value,
    }


def program_estimated_time(program):
    """Learning already has duration_value/duration_unit (minutes/hours/
    days/weeks) — reused as the estimate; a self-paced program with no
    duration reads "Self-paced"."""
    label = format_estimated_time(program.duration_value, None, program.duration_unit)
    if label is not None:
        return {"label": label, "unit": program.duration_unit, "value": program.duration_value, "maxValue": None}
    if program.delivery_mode == "self_paced":
        return {"label": "Self-paced", "unit": "self_paced", "value": None, "maxValue": None}
    return None


def _format(key):
    return {"key": key, "slug": url_value(key), "label": FORMAT_LABELS[key]} if key in FORMAT_LABELS else None


def resource_format(resource):
    return _format(RESOURCE_TYPE_FORMATS.get(resource.type))


def program_format(program):
    return _format(LEARNING_TYPE_FORMATS.get(program.program_type))


def resource_access(resource):
    level = {"circle_only": "circle", "premium": "premium"}.get(resource.access_type, "free")
    label = {
        "direct_download": "Free",
        "email_gate": "Free · email required",
        "member_only": "Free with a WSF account",
        "external_link": "Free · external link",
        "premium": "Premium",
        "circle_only": "WSF Circle Yearly & Lifetime" if resource.circle_access_level == "yearly_members" else "WSF Circle",
    }[resource.access_type]
    return {"level": level, "label": label}


def program_access(program):
    level = {"free": "free", "circle_only": "circle", "product": "premium", "external": "external"}[program.access_type]
    label = {"free": "Free", "circle_only": "WSF Circle", "product": "Premium", "external": "External programme"}[program.access_type]
    return {"level": level, "label": label}


def _circle(inclusion):
    scope = inclusion["scope"] if inclusion["included"] else None
    return {"included": inclusion["included"], "scope": scope, "label": CIRCLE_INCLUSION_LABELS.get(scope)}


def _goal_and_category(topics):
    """First published Topic (editorial sort order) as the card category;
    the first published Topic carrying a career goal gives the goal."""
    from app.services.public_visibility import is_public_taxonomy

    public = sorted((t for t in topics if is_public_taxonomy(t)), key=lambda t: (t.sort_order, t.name))
    category = {"slug": public[0].slug, "name": public[0].name} if public else None
    goal_topic = next((t for t in public if t.career_goal in GOAL_LABELS), None)
    goal = (
        {"key": goal_topic.career_goal, "slug": url_value(goal_topic.career_goal), "label": GOAL_LABELS[goal_topic.career_goal]}
        if goal_topic else None
    )
    return goal, category


def _image(media, title):
    if media is None:
        return None, title
    variants = {v.variant: {"url": v.public_url, "width": v.width, "height": v.height} for v in media.variants}
    return (
        {"id": media.id, "public_url": media.public_url, "alt_text": media.alt_text or "", "width": media.width,
         "height": media.height, "variants": variants},
        media.alt_text or title,
    )


def _iso(value):
    return value.isoformat() if value else None


def _product_pricing(product):
    """A product-access Learning program's price comes from its linked
    Product (Product stays the one source of truth); shown only while that
    Product is active with a visible, positive price."""
    from app.services.money import format_money, legacy_whole_units_to_minor

    if product is None or product.status != "active" or not product.price_visible:
        return None
    whole = product.sale_price if product.sale_price is not None else product.price
    if not whole or whole <= 0:
        return None
    try:
        minor = legacy_whole_units_to_minor(whole, product.currency)
        formatted = format_money(minor, product.currency)
    except Exception:  # unknown/legacy currency: show nothing rather than a wrong price
        return None
    price = {"currency": product.currency, "amountMinor": minor, "formatted": formatted, "checkoutAvailable": False}
    return {"prices": [price], "defaultCurrency": product.currency, "oneTime": True}


def build_resource_card(resource, settings):
    from app.services.payment_providers import TRANSACTION_RESOURCE_PURCHASE
    from app.services.pricing import public_pricing_payload
    from app.services.resource_access import resource_circle_inclusion

    goal, category = _goal_and_category(resource.topics)
    image, alt = _image(resource.cover_media, resource.name)
    pricing = None
    if resource.access_type == "premium":
        payload = public_pricing_payload(resource, TRANSACTION_RESOURCE_PURCHASE, settings)
        if payload["prices"]:
            pricing = {**payload, "oneTime": True}
    published = resource.published_date
    return {
        "id": f"resource-{resource.id}",
        "sourceType": "resource",
        "sourceId": resource.id,
        "slug": resource.slug,
        "title": resource.name,
        "summary": resource.short_description or resource.subtitle,
        "image": image,
        "imageAlt": alt,
        "format": resource_format(resource),
        "goal": goal,
        "category": category,
        "estimatedTime": resource_estimated_time(resource),
        "access": resource_access(resource),
        "circle": _circle(resource_circle_inclusion(resource)),
        "pricing": pricing,
        "publishedAt": published.isoformat() if published else None,
        "featured": resource.featured,
        "url": f"/resources/{resource.slug}",
    }


def build_program_card(program):
    from app.services.learning_access import program_circle_inclusion

    goal, category = _goal_and_category(program.topics)
    image, alt = _image(program.hero_media, program.title)
    return {
        "id": f"learning-{program.id}",
        "sourceType": "learning",
        "sourceId": program.id,
        "slug": program.slug,
        "title": program.title,
        "summary": program.short_description or program.subtitle,
        "image": image,
        "imageAlt": alt,
        "format": program_format(program),
        "goal": goal,
        "category": category,
        "estimatedTime": program_estimated_time(program),
        "access": program_access(program),
        "circle": _circle(program_circle_inclusion(program)),
        "pricing": _product_pricing(program.product) if program.access_type == "product" else None,
        "publishedAt": _iso(program.published_at),
        "featured": program.featured,
        "url": f"/learning/{program.slug}",
    }


# --- filters -------------------------------------------------------------------------


def parse_filters(args):
    """Validated, normalized filters from query args. Unknown values are a
    422 (`invalid_filter`) — the page never silently shows a different set
    than the URL asked for. `goal` accepts a canonical goal (get-promoted)
    or, as an alias, a published Topic slug (salary-negotiation), so
    Career Pathways can deep-link to either."""
    from app.models.taxonomy import Topic

    def _bad(name):
        raise ApiError(f"Unknown {name} filter.", 422, code="invalid_filter")

    q = (args.get("q") or "").strip()[:100]
    goal = topic = None
    raw_goal = (args.get("goal") or "").strip().lower()
    if raw_goal:
        key = from_url_value(raw_goal)
        if key in GOAL_LABELS:
            goal = key
        elif Topic.query.filter_by(slug=raw_goal, status="published").first() is not None:
            topic = raw_goal
        else:
            _bad("goal")
    fmt = from_url_value(args.get("format"))
    if fmt and fmt not in FORMAT_LABELS:
        _bad("format")
    access = (args.get("access") or "").strip().lower()
    if access and access not in ACCESS_FILTERS:
        _bad("access")
    sort = from_url_value(args.get("sort")) or DEFAULT_SORT
    if sort not in SORTS:
        _bad("sort")
    try:
        page = int(args.get("page") or 1)
        page_size = int(args.get("pageSize") or DEFAULT_PAGE_SIZE)
    except (TypeError, ValueError):
        raise ApiError("page and pageSize must be whole numbers.", 422, code="invalid_filter")
    if page < 1 or page > MAX_PAGE or page_size < 1 or page_size > MAX_PAGE_SIZE:
        raise ApiError(f"page must be 1–{MAX_PAGE} and pageSize 1–{MAX_PAGE_SIZE}.", 422, code="invalid_filter")
    return {"q": q, "goal": goal, "topic": topic, "format": fmt or None, "access": access or None,
            "sort": sort, "page": page, "page_size": page_size}


def _resource_visible(Resource, today):
    return or_(
        Resource.status == "published",
        and_(Resource.status == "scheduled", Resource.published_date.isnot(None), Resource.published_date <= today),
    )


def _topic_clause(relationship, filters):
    from app.models.taxonomy import Topic

    clauses = []
    if filters.get("goal"):
        clauses.append(relationship.any(and_(Topic.career_goal == filters["goal"], Topic.status == "published")))
    if filters.get("topic"):
        clauses.append(relationship.any(and_(Topic.slug == filters["topic"], Topic.status == "published")))
    return clauses


def _search_clause(columns, q):
    if not q:
        return []
    like = f"%{q}%"
    return [or_(*[col.ilike(like) for col in columns])]


def _resource_select(filters, today):
    from app.models.resource import Resource

    clauses = [_resource_visible(Resource, today)]
    clauses += _search_clause([Resource.name, Resource.subtitle, Resource.short_description], filters.get("q"))
    clauses += _topic_clause(Resource.topics, filters)
    if filters.get("format"):
        types = [t for t, key in RESOURCE_TYPE_FORMATS.items() if key == filters["format"]]
        clauses.append(Resource.type.in_(types) if types else false())
    access = filters.get("access")
    if access == "free":
        clauses.append(Resource.access_type.in_(("direct_download", "email_gate", "member_only", "external_link")))
    elif access == "circle":
        clauses.append(Resource.access_type == "circle_only")
    elif access == "premium":
        clauses.append(Resource.access_type == "premium")
    published = func.coalesce(cast(Resource.published_date, DateTime(timezone=True)), Resource.created_at)
    return select(
        literal("resource").label("source"),
        Resource.id.label("id"),
        published.label("published"),
        Resource.created_at.label("created"),
        Resource.featured.label("featured"),
    ).where(and_(*clauses))


def _program_select(filters):
    from app.models.learning import LearningProgram

    clauses = [LearningProgram.status == "published"]
    clauses += _search_clause(
        [LearningProgram.title, LearningProgram.subtitle, LearningProgram.short_description], filters.get("q")
    )
    clauses += _topic_clause(LearningProgram.topics, filters)
    if filters.get("format"):
        types = [t for t, key in LEARNING_TYPE_FORMATS.items() if key == filters["format"]]
        clauses.append(LearningProgram.program_type.in_(types) if types else false())
    access = filters.get("access")
    if access == "free":
        clauses.append(LearningProgram.access_type == "free")
    elif access == "circle":
        clauses.append(LearningProgram.access_type == "circle_only")
    elif access == "premium":
        clauses.append(LearningProgram.access_type == "product")
    published = func.coalesce(LearningProgram.published_at, LearningProgram.created_at)
    return select(
        literal("learning").label("source"),
        LearningProgram.id.label("id"),
        published.label("published"),
        LearningProgram.created_at.label("created"),
        LearningProgram.featured.label("featured"),
    ).where(and_(*clauses) if clauses else true())


def _order(union, sort):
    newest = (union.c.published.desc(), union.c.source, union.c.id.desc())
    if sort == "featured":
        return (union.c.featured.desc(),) + newest
    if sort == "recently_added":
        return (union.c.created.desc(), union.c.source, union.c.id.desc())
    return newest


def _load_cards(keys):
    """(source, id) pairs -> cards in the same order: one batched query per
    source with eager loads, and payment settings read once."""
    from app.models.learning import LearningProgram
    from app.models.media import Media
    from app.models.resource import Resource
    from app.services.payment_settings import get_payment_settings

    resource_ids = [i for s, i in keys if s == "resource"]
    program_ids = [i for s, i in keys if s == "learning"]
    resources = {}
    if resource_ids:
        rows = Resource.query.options(
            selectinload(Resource.topics), selectinload(Resource.prices),
            selectinload(Resource.cover_media).selectinload(Media.variants),
        ).filter(Resource.id.in_(resource_ids)).all()
        resources = {r.id: r for r in rows}
    programs = {}
    if program_ids:
        rows = LearningProgram.query.options(
            selectinload(LearningProgram.topics), selectinload(LearningProgram.product),
            selectinload(LearningProgram.hero_media).selectinload(Media.variants),
        ).filter(LearningProgram.id.in_(program_ids)).all()
        programs = {p.id: p for p in rows}
    settings = get_payment_settings() if any(r.access_type == "premium" for r in resources.values()) else None
    cards = []
    for source, item_id in keys:
        if source == "resource" and item_id in resources:
            cards.append(build_resource_card(resources[item_id], settings))
        elif source == "learning" and item_id in programs:
            cards.append(build_program_card(programs[item_id]))
    return cards


def search_career_hub(filters, today=None):
    today = today or date.today()
    union = union_all(_resource_select(filters, today), _program_select(filters)).subquery("career_hub")
    total = db.session.execute(select(func.count()).select_from(union)).scalar() or 0
    offset = (filters["page"] - 1) * filters["page_size"]
    rows = db.session.execute(
        select(union.c.source, union.c.id).order_by(*_order(union, filters["sort"])).limit(filters["page_size"]).offset(offset)
    ).all()
    total_pages = (total + filters["page_size"] - 1) // filters["page_size"] if total else 0
    return {
        "items": _load_cards([(r.source, r.id) for r in rows]),
        # Same pagination keys as every other list endpoint (frontend
        # api/client.js unwraps them into {items, pagination}).
        "meta": {"page": filters["page"], "per_page": filters["page_size"], "total": total, "total_pages": total_pages},
    }


def new_this_month(today=None, limit=NEW_THIS_MONTH_LIMIT):
    """Public items first published during the current calendar month
    (Resource.published_date / LearningProgram.published_at), newest
    first, bounded. Items with no publication date never qualify."""
    from app.models.learning import LearningProgram
    from app.models.resource import Resource

    today = today or date.today()
    month_start = today.replace(day=1)
    start_dt = datetime.combine(month_start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(today, time.max, tzinfo=timezone.utc)
    filters = {"sort": DEFAULT_SORT}
    resources = _resource_select(filters, today).where(
        Resource.published_date.isnot(None), Resource.published_date >= month_start, Resource.published_date <= today
    )
    programs = _program_select(filters).where(
        LearningProgram.published_at.isnot(None), LearningProgram.published_at >= start_dt, LearningProgram.published_at <= end_dt
    )
    union = union_all(resources, programs).subquery("career_hub_new")
    rows = db.session.execute(select(union.c.source, union.c.id).order_by(*_order(union, DEFAULT_SORT)).limit(limit)).all()
    return _load_cards([(r.source, r.id) for r in rows])


def career_hub_meta(today=None):
    """Filter vocabulary for the page (stable URL values + labels) and the
    New This Month strip. Formats are the full Career Hub set; goals are
    the canonical list (shortcut pills first)."""
    goals = [{"key": g, "slug": url_value(g), "label": GOAL_LABELS[g], "featured": g in FEATURED_GOALS} for g in GOAL_LABELS]
    formats = [{"key": f, "slug": url_value(f), "label": FORMAT_LABELS[f]} for f in FORMAT_LABELS]
    return {
        "goals": goals,
        "formats": formats,
        "access": [{"key": k, "slug": k, "label": v} for k, v in ACCESS_FILTERS.items()],
        "sorts": [{"key": k, "slug": url_value(k), "label": v} for k, v in SORTS.items()],
        "newThisMonth": new_this_month(today),
    }
