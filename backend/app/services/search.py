"""The one authoritative site-wide search service — see api/v1/search.py
for the thin route that calls this. Every eligibility rule, searchable
field, and relevance decision lives here so the frontend never has to
duplicate "is this record public" logic (see spec's "one authoritative
search service" requirement).

Design, in one paragraph: each content type gets its own small query
function that (a) applies that type's OWN authoritative public-visibility
filter — mirrored from its own listing endpoint, never invented here —
and (b) matches the normalized query against that type's meaningful public
fields, using PostgreSQL full-text search for Article (title/subtitle/
excerpt/topics/series/author plus real body-block text via
wsf_article_search_vector(), see the search migration) and plain
`ILIKE` for every other type's short text columns — the same technique
`app/utils/filtering.py:apply_search` already uses everywhere else in this
app, which is the simplest robust choice at this project's real scale.
Each type function returns a bounded candidate list already carrying a
simple, explainable relevance tier (0=exact title/name match, 1=starts
with, 2=contains, 3=secondary-field match only) computed the same way for
every type, so merging results across types for the "all" view is a plain
sort — no cross-type score normalization needed.
"""
import re
import unicodedata
from datetime import date

from sqlalchemy import or_

from app.extensions import db
from app.models.article import Article
from app.models.commerce import Product, ProductCategory
from app.models.opportunity import Event, Job, Opportunity
from app.models.page import Page
from app.models.people import Author, Organization, Person
from app.models.resource import Resource
from app.models.taxonomy import Series, Topic
from app.utils.filtering import apply_country_or_region_filter

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 200

# How many candidates each type contributes to the merged "all" view before
# the shared tier sort runs — bounded so a query that matches hundreds of
# Articles can never crowd every other type out of the result pool (spec:
# "avoid a search where articles completely hide People/Jobs/..."), and
# bounded so this never turns into an unbounded per-type table scan.
CANDIDATE_POOL_PER_TYPE = 40

DEFAULT_PER_PAGE = 20
MAX_PER_PAGE = 50

# System pages only — "general" pages have no public render route in this
# app yet (see app/models/page.py), so including them here would produce a
# search result that 404s. Legal pages are included but intentionally
# de-prioritized (see PAGE_BASE_TIER_PENALTY below) so they don't outrank
# genuinely relevant editorial content for a broad query.
_SEARCHABLE_PAGE_KEYS = ("about", "contact", "privacy", "terms", "cookies", "editorial-policy")
_LOW_PRIORITY_PAGE_KEYS = ("privacy", "terms", "cookies")

# Human-readable type labels — never a raw model/table name (spec: no
# "article_record"/"resource_entity"). Doubles as the controlled `type`
# filter vocabulary accepted by the API.
TYPE_LABELS = {
    "articles": "Story",
    "people": "Person",
    "authors": "Author",
    "organizations": "Organization",
    "topics": "Topic",
    "series": "Series",
    "jobs": "Job",
    "opportunities": "Opportunity",
    "events": "Event",
    "resources": "Resource",
    "products": "Product",
    "pages": "Page",
}
SEARCHABLE_TYPES = tuple(TYPE_LABELS.keys())


class SearchValidationError(Exception):
    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


def normalize_query(raw):
    """Whitespace/Unicode normalization only — never rewrites the query
    into a different meaning. NFKC canonicalizes visually-identical Unicode
    forms (full-width characters, combining marks) without changing what
    the text says; collapsing whitespace and trimming just tidies input,
    it never drops words.
    """
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw)
    return re.sub(r"\s+", " ", text).strip()


def validate_query(query):
    """Raises for a query that's too short/long to search meaningfully.
    An EMPTY query is valid input (see api/v1/search.py) — it just means
    "no search performed yet", not an error.
    """
    if not query:
        return
    if len(query) < MIN_QUERY_LENGTH:
        raise SearchValidationError(
            f"Search must be at least {MIN_QUERY_LENGTH} characters.", "query_too_short"
        )
    if len(query) > MAX_QUERY_LENGTH:
        raise SearchValidationError(
            f"Search must be {MAX_QUERY_LENGTH} characters or fewer.", "query_too_long"
        )


def _tier(term, *fields):
    """The shared 0-3 relevance tier used across every content type (spec
    section 11's suggested order, collapsed to what's comparable across
    wildly different content types): 0 exact match on the primary field,
    1 primary field starts with the query, 2 primary field contains it,
    3 only a secondary field matched. `fields[0]` must be the primary
    title/name field; the rest are secondary fields already known to
    contain the term (the caller only reaches this branch because SOME
    field matched).
    """
    primary = (fields[0] or "").strip().lower()
    needle = term.strip().lower()
    if primary == needle:
        return 0
    if primary.startswith(needle):
        return 1
    if needle in primary:
        return 2
    return 3


def _media_url(media):
    if media is None:
        return None
    return media.variant_url("card") or media.public_url


def _truncate(text, length=160):
    if not text:
        return None
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= length:
        return text
    return text[:length].rsplit(" ", 1)[0] + "…"


def _result(result_type, title, excerpt, url, image, tier, extra=None):
    return {
        "resultType": TYPE_LABELS[result_type],
        "resultTypeKey": result_type,
        "title": title,
        "excerpt": excerpt,
        "url": url,
        "image": image,
        "meta": extra or {},
        "_tier": tier,
    }


# ---------------------------------------------------------------------------
# Per-type search — eligibility mirrors each type's own public listing
# endpoint exactly (see the file named in each comment); never invented
# independently here.
# ---------------------------------------------------------------------------


def _search_articles(term, filters):
    like = f"%{term}%"
    query = Article.query.filter(Article.status == "published")  # api/v1/articles.py public list
    if filters.get("topic"):
        query = query.filter(Article.topics.any(slug=filters["topic"], status="published"))

    fts = db.func.wsf_article_search_vector(Article.title, Article.subtitle, Article.excerpt, Article.content).op(
        "@@"
    )(db.func.websearch_to_tsquery("english", term))
    query = query.filter(
        or_(
            fts,
            Article.title.ilike(like),
            Article.subtitle.ilike(like),
            Article.excerpt.ilike(like),
            Article.topics.any(Topic.name.ilike(like)),
            Article.series.has(Series.name.ilike(like)),
            Article.author.has(Author.name.ilike(like)),
        )
    )
    rows = query.order_by(Article.publish_date.desc().nullslast()).limit(CANDIDATE_POOL_PER_TYPE).all()

    results = []
    for a in rows:
        topic_name = a.topics[0].name if a.topics else None
        results.append(
            _result(
                "articles",
                a.title,
                _truncate(a.excerpt) or _truncate(a.subtitle),
                f"/{a.slug}",
                _media_url(a.hero_media),
                _tier(term, a.title, a.subtitle, a.excerpt, a.author.name if a.author else None),
                {"publishedDate": a.publish_date.isoformat() if a.publish_date else None, "topic": topic_name},
            )
        )
    return results


def _search_people(term, filters):
    like = f"%{term}%"
    query = Person.query.filter(Person.status == "published")  # api/v1/people.py public list
    query = apply_country_or_region_filter(query, Person, filters)
    query = query.filter(
        or_(
            Person.name.ilike(like),
            Person.title.ilike(like),
            Person.industry.ilike(like),
            Person.profession.ilike(like),
            Person.short_bio.ilike(like),
            Person.organization.has(Organization.name.ilike(like)),
        )
    )
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    results = []
    for p in rows:
        org_name = p.organization.name if p.organization else None
        excerpt = " — ".join(filter(None, [p.title, org_name])) or _truncate(p.short_bio)
        results.append(
            _result(
                "people",
                p.name,
                excerpt,
                f"/people/{p.slug}",
                _media_url(p.photo),
                _tier(term, p.name, p.title, org_name, p.short_bio),
                {"title": p.title, "organization": org_name},
            )
        )
    return results


def _search_authors(term, filters):
    like = f"%{term}%"
    # active = publicly listed (see app/models/people.py:AUTHOR_STATUSES).
    query = Author.query.filter(Author.status == "active")
    if filters.get("topic"):
        query = query.filter(Author.topics.any(slug=filters["topic"], status="published"))
    query = query.filter(or_(Author.name.ilike(like), Author.role.ilike(like), Author.short_bio.ilike(like)))
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "authors",
            a.name,
            a.role or _truncate(a.short_bio),
            f"/authors/{a.slug}",
            _media_url(a.photo),
            _tier(term, a.name, a.role, a.short_bio),
            {"role": a.role},
        )
        for a in rows
    ]


def _search_organizations(term, filters):
    like = f"%{term}%"
    query = Organization.query.filter(Organization.status == "published")  # api/v1/organizations.py public list
    query = apply_country_or_region_filter(query, Organization, filters)
    query = query.filter(
        or_(
            Organization.name.ilike(like),
            Organization.industry.ilike(like),
            Organization.location.ilike(like),
            Organization.short_description.ilike(like),
        )
    )
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "organizations",
            o.name,
            o.short_description and _truncate(o.short_description) or o.industry,
            f"/organizations/{o.slug}",
            _media_url(o.logo),
            _tier(term, o.name, o.industry, o.short_description),
            {"industry": o.industry, "location": o.location},
        )
        for o in rows
    ]


def _search_topics(term, filters):
    like = f"%{term}%"
    query = Topic.query.filter(Topic.status == "published")  # api/v1/taxonomy.py public list
    query = query.filter(or_(Topic.name.ilike(like), Topic.description.ilike(like)))
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "topics",
            t.name,
            _truncate(t.description),
            f"/topics/{t.slug}",
            _media_url(t.hero_media),
            _tier(term, t.name, t.description),
        )
        for t in rows
    ]


def _search_series(term, filters):
    like = f"%{term}%"
    query = Series.query.filter(Series.status == "published")  # api/v1/taxonomy.py public list
    query = query.filter(or_(Series.name.ilike(like), Series.subtitle.ilike(like), Series.description.ilike(like)))
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "series",
            s.name,
            s.subtitle or _truncate(s.description),
            f"/series/{s.slug}",
            _media_url(s.cover_media),
            _tier(term, s.name, s.subtitle, s.description),
        )
        for s in rows
    ]


def _search_jobs(term, filters):
    like = f"%{term}%"
    today = date.today()
    # Mirrors api/v1/jobs.py:JobListResource's public-visibility filter
    # exactly (published, or scheduled once its publish date has arrived;
    # never past its own expiry).
    query = Job.query.filter(
        or_(Job.status == "published", (Job.status == "scheduled") & (Job.published_date <= today))
    ).filter(or_(Job.expiry_date.is_(None), Job.expiry_date >= today))
    query = apply_country_or_region_filter(query, Job, filters)
    if filters.get("remote") is True:
        query = query.filter(Job.work_mode == "Remote")
    query = query.filter(
        or_(
            Job.title.ilike(like),
            Job.company_name.ilike(like),
            Job.location.ilike(like),
            Job.industry.ilike(like),
            Job.employment_type.ilike(like),
            Job.short_description.ilike(like),
        )
    )
    rows = query.order_by(Job.featured.desc()).limit(CANDIDATE_POOL_PER_TYPE).all()

    results = []
    for j in rows:
        excerpt = " — ".join(filter(None, [j.company_name, j.location or j.work_mode]))
        results.append(
            _result(
                "jobs",
                j.title,
                excerpt or _truncate(j.short_description),
                f"/jobs/{j.slug}",
                _media_url(j.logo),
                _tier(term, j.title, j.company_name, j.location, j.short_description),
                {
                    "organization": j.company_name,
                    "location": j.location,
                    "employmentType": j.employment_type,
                    "remote": j.work_mode == "Remote",
                },
            )
        )
    return results


def _search_opportunities(term, filters):
    like = f"%{term}%"
    today = date.today()
    # Mirrors api/v1/opportunities.py:OpportunityListResource's public filter.
    query = Opportunity.query.filter(Opportunity.status == "published").filter(
        or_(Opportunity.expiry_date.is_(None), Opportunity.expiry_date >= today)
    )
    if filters.get("country"):
        query = query.filter(Opportunity.countries_eligible.any(code=filters["country"].upper()))
    if filters.get("topic"):
        query = query.filter(Opportunity.topics.any(slug=filters["topic"], status="published"))
    query = query.filter(
        or_(
            Opportunity.title.ilike(like),
            Opportunity.organization_name.ilike(like),
            Opportunity.type.ilike(like),
            Opportunity.eligibility.ilike(like),
            Opportunity.short_description.ilike(like),
        )
    )
    rows = query.order_by(Opportunity.featured.desc()).limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "opportunities",
            o.title,
            o.short_description and _truncate(o.short_description) or o.organization_name,
            f"/opportunities/{o.slug}",
            _media_url(o.logo),
            _tier(term, o.title, o.organization_name, o.short_description),
            {"organization": o.organization_name, "type": o.type},
        )
        for o in rows
    ]


def _search_events(term, filters):
    like = f"%{term}%"
    today = date.today()
    # Mirrors api/v1/events.py:EventListResource's public filter — cancelled/
    # postponed events stay publicly visible (clearly marked), per Event's
    # own status docstring.
    query = Event.query.filter(
        or_(
            Event.status.in_(["published", "cancelled", "postponed"]),
            (Event.status == "scheduled") & (Event.published_date.isnot(None)) & (Event.published_date <= today),
        )
    )
    query = apply_country_or_region_filter(query, Event, filters)
    query = query.filter(
        or_(
            Event.title.ilike(like),
            Event.organizer_name.ilike(like),
            Event.location.ilike(like),
            Event.city.ilike(like),
            Event.type.ilike(like),
            Event.short_description.ilike(like),
        )
    )
    rows = query.order_by(Event.date.desc()).limit(CANDIDATE_POOL_PER_TYPE).all()

    results = []
    for e in rows:
        organizer = e.organizer.name if e.organizer else e.organizer_name
        excerpt = " — ".join(filter(None, [e.location, "Virtual" if e.format == "virtual" else None]))
        results.append(
            _result(
                "events",
                e.title,
                excerpt or _truncate(e.short_description),
                f"/events/{e.slug}",
                _media_url(e.cover_media),
                _tier(term, e.title, organizer, e.location, e.short_description),
                {"date": e.date.isoformat() if e.date else None, "location": e.location, "format": e.format},
            )
        )
    return results


def _search_resources(term, filters):
    like = f"%{term}%"
    today = date.today()
    # Mirrors api/v1/resources.py's public-visibility filter.
    query = ResourceModel.query.filter(
        or_(
            ResourceModel.status == "published",
            (ResourceModel.status == "scheduled") & (ResourceModel.published_date <= today),
        )
    )
    if filters.get("topic"):
        query = query.filter(ResourceModel.topics.any(slug=filters["topic"], status="published"))
    query = query.filter(
        or_(
            ResourceModel.name.ilike(like),
            ResourceModel.subtitle.ilike(like),
            ResourceModel.short_description.ilike(like),
            ResourceModel.type.ilike(like),
        )
    )
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "resources",
            r.name,
            r.subtitle or _truncate(r.short_description),
            f"/resources/{r.slug}",
            _media_url(r.cover_media),
            _tier(term, r.name, r.subtitle, r.short_description),
            {"type": r.type},
        )
        for r in rows
    ]


def _search_products(term, filters):
    like = f"%{term}%"
    # Mirrors api/v1/products.py's public-visibility filter — "unavailable"
    # still shows publicly (out of stock, not hidden). Never Orders,
    # inventory, or pricing/internal commerce data (spec section 50).
    query = Product.query.filter(Product.status.in_(["active", "unavailable"]))
    query = query.filter(
        or_(
            Product.name.ilike(like),
            Product.short_description.ilike(like),
            Product.category.has(ProductCategory.name.ilike(like)),
        )
    )
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    return [
        _result(
            "products",
            p.name,
            _truncate(p.short_description),
            f"/shop/{p.slug}",
            _media_url(p.cover_media),
            _tier(term, p.name, p.category.name if p.category else None, p.short_description),
            {"category": p.category.name if p.category else None},
        )
        for p in rows
    ]


def _search_pages(term, filters):
    like = f"%{term}%"
    query = Page.query.filter(
        Page.page_type == "system", Page.status == "published", Page.key.in_(_SEARCHABLE_PAGE_KEYS)
    )
    query = query.filter(or_(Page.title.ilike(like), Page.subtitle.ilike(like)))
    rows = query.limit(CANDIDATE_POOL_PER_TYPE).all()

    results = []
    for p in rows:
        tier = _tier(term, p.title, p.subtitle)
        # Privacy/Terms/Cookies never outrank genuinely relevant content
        # unless the query is an exact/near match (spec section 54) — push
        # anything less than an exact/prefix hit down a tier.
        if p.key in _LOW_PRIORITY_PAGE_KEYS and tier > 1:
            tier = 3
        results.append(
            _result("pages", p.title, _truncate(p.subtitle), f"/{p.slug}", None, tier)
        )
    return results


ResourceModel = Resource  # alias — `Resource` also names this module's own search "resource" concept in prose

_SEARCH_FUNCS = {
    "articles": _search_articles,
    "people": _search_people,
    "authors": _search_authors,
    "organizations": _search_organizations,
    "topics": _search_topics,
    "series": _search_series,
    "jobs": _search_jobs,
    "opportunities": _search_opportunities,
    "events": _search_events,
    "resources": _search_resources,
    "products": _search_products,
    "pages": _search_pages,
}


def search(query, result_type="all", filters=None, page=1, per_page=DEFAULT_PER_PAGE):
    """Runs the search and returns a page of merged, relevance-sorted
    results plus pagination meta. `filters` may include topic/country/
    region/remote — each per-type function ignores whatever doesn't apply
    to it (e.g. `topic` is a no-op for Jobs, which have no Topic relation).
    """
    filters = filters or {}
    per_page = max(1, min(per_page, MAX_PER_PAGE))
    types = [result_type] if result_type in _SEARCH_FUNCS else list(_SEARCH_FUNCS)

    if not query:
        return {"results": [], "page": page, "per_page": per_page, "total": 0, "total_pages": 0}

    candidates = []
    for type_key in types:
        candidates.extend(_SEARCH_FUNCS[type_key](query, filters))

    candidates.sort(key=lambda r: (r["_tier"], r["title"] or ""))
    total = len(candidates)
    total_pages = max(1, -(-total // per_page)) if total else 0
    start = (page - 1) * per_page
    page_items = candidates[start : start + per_page]
    for item in page_items:
        item.pop("_tier", None)

    return {
        "results": page_items,
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
    }
