"""The homepage as one editorial page.

resolve_homepage() walks the enabled modules in Homepage Builder order (the
editorial priority) and resolves each one's data once. Article-producing
modules all draw from ONE EditorialSelection, so the first module to place
an Article keeps it and every later module skips it (first placement wins).
The result (each module's `initial_data`, already de-duplicated) is what
GET /public/homepage returns, what the hard-load bootstrap embeds, what the
server first paint renders and what React renders. React never re-selects.

Also: write-time config validation for the editorial module types, and the
Studio warning for an Article picked in more than one module.
"""
from marshmallow import ValidationError

from app.models.article import Article
from app.services.editorial_selection import EditorialSelection, article_cards, newest_first, public_articles

# --- module type registry ----------------------------------------------------------------

# Article collections with an explicit, single source mode per module.
ARTICLE_COLLECTION_SOURCES = {
    "career_moves": ("manual", "topic"),
    "right_now": ("manual", "series", "topic"),
    "community_stories": ("community", "series", "manual"),
    "expert_guidance": ("expert", "manual"),
    "handpicked": ("editorial",),
}
ARTICLE_COLLECTION_DEFAULT_EYEBROWS = {
    "career_moves": "Career moves",
    "right_now": "Right now",
    "community_stories": "Community stories",
    "expert_guidance": "Expert-backed guidance",
    "handpicked": "Handpicked by WSF",
}
EDITORIAL_TYPES = tuple(ARTICLE_COLLECTION_SOURCES) + ("people_spotlight", "learning", "mission")
COLLECTION_ITEM_BOUNDS = (1, 8)
DEFAULT_ITEMS = {"career_moves": 4, "right_now": 3, "community_stories": 3, "expert_guidance": 3, "handpicked": 4,
                 "people_spotlight": 4, "learning": 3}
LEARNING_SOURCES = ("featured", "newest", "manual")
PEOPLE_SOURCES = ("featured", "manual")
JOB_SORTS = ("featured", "closing_soon")
OPPORTUNITY_SORTS = ("featured", "closing_soon", "upcoming")
MAX_TOPICS = 8
MAX_BENEFITS = 6


def _error(message):
    return ValidationError(message, field_name="config")


def _text(value, label, max_length, required=False):
    from app.services.homepage_collections import _plain_text

    return _plain_text(value, label, max_length, required=required)


def _count(config, module_type, bounds=COLLECTION_ITEM_BOUNDS):
    value = config.get("itemCount") or DEFAULT_ITEMS.get(module_type, 4)
    lo, hi = bounds
    if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
        raise _error(f"Show between {lo} and {hi} items.")
    return value


def _slugs(config, key, label, model, required=True, limit=8):
    raw = config.get(key) or []
    if not isinstance(raw, list) or not all(isinstance(s, str) and s.strip() for s in raw):
        raise _error(f"{label} must be a list.")
    slugs = [s.strip() for s in raw]
    if required and not slugs:
        raise _error(f"Pick at least one {label.lower().rstrip('s')}.")
    if len(slugs) > limit:
        raise _error(f"Pick at most {limit} {label.lower()}.")
    if len(set(slugs)) != len(slugs):
        raise _error(f"Each of the {label.lower()} can only be picked once.")
    existing = {row.slug for row in model.query.filter(model.slug.in_(slugs)).all()} if slugs else set()
    missing = [s for s in slugs if s not in existing]
    if missing:
        raise _error(f"These don't exist: {', '.join(missing)}.")
    return slugs


def normalize_editorial_config(data):
    """HomepageModuleInputSchema post_load for the editorial types (and the
    new optional settings of jobs/opportunities/newsletter). Unknown keys
    are dropped; a module's config only ever holds its own mode's fields."""
    from app.models.learning import LearningProgram
    from app.models.people import Person
    from app.models.taxonomy import Series, Topic

    module_type = data.get("type")
    config = data.get("config") or {}
    if not isinstance(config, dict):
        raise _error("Invalid configuration.")

    if module_type in ARTICLE_COLLECTION_SOURCES:
        sources = ARTICLE_COLLECTION_SOURCES[module_type]
        source = config.get("source") or sources[0]
        if source not in sources:
            raise _error(f"This section's source can be: {', '.join(sources)}.")
        out = {"source": source, "eyebrow": _text(config.get("eyebrow"), "Eyebrow", 60),
               "itemCount": _count(config, module_type)}
        if source == "manual":
            out["articleSlugs"] = _slugs(config, "articleSlugs", "Articles", Article)
        elif source == "editorial":
            out["articleSlugs"] = _slugs(config, "articleSlugs", "Articles", Article, required=False)
            out["personalizedHeading"] = _text(config.get("personalizedHeading"), "Signed-in heading", 120)
        elif source == "topic":
            out["topicSlugs"] = _slugs(config, "topicSlugs", "Topics", Topic, limit=MAX_TOPICS)
        elif source == "series":
            series = config.get("seriesSlug")
            if not isinstance(series, str) or Series.query.filter_by(slug=series).first() is None:
                raise _error("Choose an existing series.")
            out["seriesSlug"] = series
        data["config"] = out
    elif module_type == "people_spotlight":
        source = config.get("source") or PEOPLE_SOURCES[0]
        if source not in PEOPLE_SOURCES:
            raise _error(f"People can come from: {', '.join(PEOPLE_SOURCES)}.")
        out = {"source": source, "eyebrow": _text(config.get("eyebrow"), "Eyebrow", 60),
               "itemCount": _count(config, module_type)}
        if source == "manual":
            out["personSlugs"] = _slugs(config, "personSlugs", "People", Person)
        data["config"] = out
    elif module_type == "learning":
        source = config.get("source") or LEARNING_SOURCES[0]
        if source not in LEARNING_SOURCES:
            raise _error(f"Learning can come from: {', '.join(LEARNING_SOURCES)}.")
        out = {"source": source, "eyebrow": _text(config.get("eyebrow"), "Eyebrow", 60),
               "itemCount": _count(config, module_type, (1, 6))}
        if source == "manual":
            out["programSlugs"] = _slugs(config, "programSlugs", "Courses", LearningProgram, limit=6)
        data["config"] = out
    elif module_type == "mission":
        data["config"] = {"eyebrow": _text(config.get("eyebrow"), "Eyebrow", 60),
                          "body": _text(config.get("body"), "Supporting copy", 1200)}
    elif module_type == "jobs" and "sort" in config:
        if config["sort"] not in JOB_SORTS:
            raise _error(f"Jobs can be ordered by: {', '.join(JOB_SORTS)}.")
    elif module_type == "opportunities" and "sort" in config:
        if config["sort"] not in OPPORTUNITY_SORTS:
            raise _error(f"Opportunities can show: {', '.join(OPPORTUNITY_SORTS)}.")
    elif module_type == "newsletter" and "benefits" in config:
        benefits = config.get("benefits") or []
        if not isinstance(benefits, list) or len(benefits) > MAX_BENEFITS:
            raise _error(f"List at most {MAX_BENEFITS} reader benefits.")
        config["benefits"] = [b for b in (_text(b, "Benefit", 90) for b in benefits) if b]
        data["config"] = config
    return data


# --- resolution ----------------------------------------------------------------------------


def _config(module):
    return module.config or {}


def _limit(module, default, hi=12):
    value = _config(module).get("itemCount") or default
    return max(1, min(int(value) if isinstance(value, int) and not isinstance(value, bool) else default, hi))


def _topic_query(topic_ids):
    from app.models.taxonomy import Topic

    return public_articles().filter(Article.topics.any(Topic.id.in_(topic_ids)))


def _published_topics(slugs):
    from app.models.taxonomy import Topic

    if not slugs:
        return []
    rows = Topic.query.filter(Topic.slug.in_(slugs), Topic.status == "published").all()
    by_slug = {t.slug: t for t in rows}
    return [by_slug[s] for s in slugs if s in by_slug]


def _published_series(slug):
    from app.models.taxonomy import Series

    return Series.query.filter_by(slug=slug, status="published").first() if slug else None


def _expert_cards(articles):
    """Cards for the expert module: the public card plus each Article's
    structured reviewers/experts (only public profiles, one short line)."""
    from app.services.article_experts import public_experts

    cards = article_cards(articles)
    for card, article in zip(cards, articles):
        card["experts"] = public_experts(article, with_credentials=False)
    return cards


def _article_collection(module, selection, label):
    """The article list for one editorial collection, by its source mode."""
    config = _config(module)
    source = config.get("source") or ARTICLE_COLLECTION_SOURCES[module.type][0]
    limit = _limit(module, DEFAULT_ITEMS.get(module.type, 4), 8)
    if source == "manual":
        return selection.pick_manual(config.get("articleSlugs"), limit, label)
    if source == "topic":
        topics = _published_topics(config.get("topicSlugs"))
        return selection.pick_query(newest_first(_topic_query([t.id for t in topics])), limit, label) if topics else []
    if source == "series":
        series = _published_series(config.get("seriesSlug"))
        return selection.pick_query(newest_first(public_articles().filter(Article.series_id == series.id)), limit, label) if series else []
    if source == "community":
        # Community stories are Articles an editor published from a reader's
        # Story Submission (Article.source_submission_id); never raw submissions.
        return selection.pick_query(newest_first(public_articles().filter(Article.source_submission_id.isnot(None))), limit, label)
    if source == "expert":
        return selection.pick_query(newest_first(public_articles().filter(Article.experts.any())), limit, label)
    if source == "editorial":
        # Handpicked by WSF: the editor's picks, then featured/promoted, then
        # the newest; always after every Article placed above.
        backfill = public_articles().order_by(
            Article.featured.desc(), Article.promoted.desc(), Article.publish_date.desc().nullslast(), Article.id.desc())
        return selection.pick_manual_then_query(config.get("articleSlugs"), backfill, limit, label)
    return []


def _collection_items(entity, config, slugs, limit):
    from app.services.homepage_collections import _build_collection_items, _query_collection

    rows = _query_collection(entity, config, slugs, limit)
    return _build_collection_items(entity, rows, limit)


def _upcoming_opportunities(limit):
    from datetime import date

    from sqlalchemy.orm import selectinload

    from app.api.v1.opportunities import build_public_opportunity_payload
    from app.models.opportunity import Opportunity
    from app.services.listing_lifecycle import upcoming_opportunities_clause

    rows = (Opportunity.query.options(selectinload(Opportunity.organization), selectinload(Opportunity.countries_eligible),
                                      selectinload(Opportunity.topics))
            .filter(upcoming_opportunities_clause(Opportunity, date.today()))
            .order_by(Opportunity.opening_date.asc().nullslast(), Opportunity.id.asc()).limit(limit).all())
    return [build_public_opportunity_payload(o, None, detail=False) for o in rows]


def resolve_module(module, selection):
    """`initial_data` for one module (None when the module's component should
    fall back to its own request, i.e. never for an Article module)."""
    from app.schemas.taxonomy import SeriesDetailSchema, TopicDetailSchema
    from app.services.first_paint import homepage_initial_data

    config = _config(module)
    label = f"{module.type}#{module.id}"
    kind = module.type
    if kind == "hero":
        lead = selection.pick_manual([config.get("leadArticleSlug")], 1, label + ":lead") if config.get("leadArticleSlug") else []
        secondary = selection.pick_manual(config.get("secondaryArticleSlugs"), 4, label + ":secondary")
        return {"lead": article_cards(lead)[0] if lead else None, "secondary": article_cards(secondary)}
    if kind == "featured_stories":
        return {"articles": article_cards(selection.pick_manual(config.get("articleSlugs"), _limit(module, 8, 8), label))}
    if kind == "latest_stories":
        return {"articles": article_cards(selection.pick_query(newest_first(public_articles()), _limit(module, 8), label))}
    if kind == "series_feature":
        series = _published_series(config.get("seriesSlug"))
        if series is None:
            return {"series": None}
        articles = selection.pick_query(newest_first(public_articles().filter(Article.series_id == series.id)),
                                        _limit(module, 3, 6), label)
        return {"series": SeriesDetailSchema().dump(series), "articles": article_cards(articles)}
    if kind == "topic_collection":
        topics = _published_topics([config.get("topicSlug")] if config.get("topicSlug") else [])
        if not topics:
            return {"topic": None}
        articles = selection.pick_query(newest_first(_topic_query([topics[0].id])), _limit(module, 3, 6), label)
        return {"topic": TopicDetailSchema().dump(topics[0]), "articles": article_cards(articles)}
    if kind in ARTICLE_COLLECTION_SOURCES:
        articles = _article_collection(module, selection, label)
        cards = _expert_cards(articles) if kind == "expert_guidance" else article_cards(articles)
        return {"articles": cards}
    if kind == "people_spotlight":
        manual = config.get("source") == "manual"
        slugs = config.get("personSlugs") if manual else []
        return {"items": _collection_items("people", {"sort": "featured"}, slugs, _limit(module, 4, 8))}
    if kind == "learning":
        source = config.get("source") or "featured"
        slugs = config.get("programSlugs") if source == "manual" else []
        return {"items": _collection_items("learning", {"sort": source if source != "manual" else "newest"}, slugs,
                                           _limit(module, 3, 6))}
    if kind == "jobs" and config.get("sort") == "closing_soon":
        return {"items": _collection_items("jobs", {"sort": "closing_soon"}, [], _limit(module, 4, 6))}
    if kind == "opportunities" and config.get("sort") == "closing_soon":
        return {"items": _collection_items("opportunities", {"sort": "closing_soon"}, [], _limit(module, 3, 6))}
    if kind == "opportunities" and config.get("sort") == "upcoming":
        return {"items": _upcoming_opportunities(_limit(module, 3, 6))}
    if kind == "mission":
        return None
    return homepage_initial_data(_module_payload_stub(module))


def _module_payload_stub(module):
    return {"type": module.type, "config": _config(module), "id": module.id}


def _content_collection_articles(module, selection):
    """A content_collection of Articles also takes part in the page selection."""
    config = _config(module)
    label = f"content_collection#{module.id}"
    if module.selection_mode == "manual":
        slugs = config.get("slugs") or []
        articles = selection.pick_manual(slugs, len(slugs), label)
    else:
        from app.models.taxonomy import Series, Topic

        query = public_articles()
        filters = config.get("filters") or {}
        if filters.get("topic"):
            query = query.filter(Article.topics.any(Topic.slug == filters["topic"]))
        if filters.get("series"):
            query = query.filter(Article.series.has(Series.slug == filters["series"]))
        if config.get("sort") == "featured":
            query = query.filter(Article.featured.is_(True))
        articles = selection.pick_query(newest_first(query), _limit(module, 4, 8), label)
    return {"entityType": "articles", "items": article_cards(articles)}


def resolve_homepage(modules, extras=None):
    """({module.id: initial_data}, {module.id: resolved}, selection) for the
    enabled modules in builder order."""
    from app.services.homepage_collections import resolve_homepage_extras

    if extras is None:
        extras = resolve_homepage_extras([m for m in modules if not _is_article_collection(m)])
    selection = EditorialSelection()
    initial, resolved = {}, dict(extras)
    for module in modules:
        if _is_article_collection(module):
            resolved[module.id] = _content_collection_articles(module, selection)
            continue
        if module.type in ("career_pathways", "content_collection"):
            continue
        data = resolve_module(module, selection)
        if data is not None:
            initial[module.id] = data
    return initial, resolved, selection


def _is_article_collection(module):
    return module.type == "content_collection" and _config(module).get("entityType") == "articles"


_PUBLIC_EDITORIAL_KEYS = ("source", "eyebrow", "itemCount", "body", "personalizedHeading")


def public_homepage_payload(modules):
    """GET /public/homepage and the hard-load bootstrap: the module dump with
    each module's de-duplicated `initial_data`. Editorial types expose only
    their display settings, never the raw picked slugs."""
    from app.schemas.cms import HomepageModuleSchema
    from app.services.homepage_collections import attach_public_extras
    from app.services.spa_shell import _redact_internal_media_fields

    initial, resolved, selection = resolve_homepage(modules)
    dumped = attach_public_extras(HomepageModuleSchema(many=True).dump(modules), modules, resolved)
    by_id = {m.id: m for m in modules}
    for entry in dumped:
        module = by_id.get(entry.get("id"))
        if module is None:
            continue
        if module.type in EDITORIAL_TYPES:
            entry["config"] = {k: v for k, v in _config(module).items() if k in _PUBLIC_EDITORIAL_KEYS}
        if module.id in initial:
            entry["initial_data"] = initial[module.id]
    return _redact_internal_media_fields(dumped), selection


# --- personalized Handpicked ------------------------------------------------------------------


def personalized_handpicked(user, module_id=None):
    """Handpicked for a signed-in reader with Career Goals: Articles whose
    Topics map to those goals (Topic.career_goal), scored by how many goal
    Topics they carry plus featured, newest first on ties. It excludes every
    Article placed anywhere else on the homepage, so personalizing can never
    repeat a story shown above or below. Returns None when there is nothing
    personal to offer (anonymous, or no goals)."""
    from app.models.taxonomy import Topic
    from app.services.homepage import get_enabled_homepage_modules

    goals = [g for g in (getattr(user, "career_goals", None) or []) if isinstance(g, str)]
    if not goals:
        return None
    modules = get_enabled_homepage_modules()
    target = next((m for m in modules if m.type == "handpicked" and (module_id is None or m.id == module_id)), None)
    if target is None:
        return None
    _initial, _resolved, page = resolve_homepage(modules)
    own = {i for label, ids in page.placements if label == f"handpicked#{target.id}" for i in ids}
    selection = EditorialSelection(reserved_ids=page.used - own)
    topic_ids = {t.id for t in Topic.query.filter(Topic.career_goal.in_(goals), Topic.status == "published").all()}
    if not topic_ids:
        return {"moduleId": target.id, "articles": []}

    def score(article):
        matches = sum(1 for t in article.topics if t.id in topic_ids)
        return matches * 10 + (3 if article.featured else 0) if matches else 0

    picked = selection.pick_ranked(_topic_query(topic_ids), score, _limit(target, 4, 8), f"handpicked#{target.id}")
    return {"moduleId": target.id, "articles": article_cards(picked)}


# --- Studio: duplicate selection warnings -----------------------------------------------------

_MODULE_LABELS = {
    "hero": "Hero", "featured_stories": "Featured Stories", "latest_stories": "Latest Stories",
    "series_feature": "Series", "topic_collection": "Topic Collection", "content_collection": "Content Collection",
    "career_moves": "Career Moves", "right_now": "Right Now", "community_stories": "Community Stories",
    "expert_guidance": "Expert-Backed Guidance", "handpicked": "Handpicked",
}


def _explicit_article_slugs(module):
    config = _config(module)
    if module.type == "hero":
        return [config.get("leadArticleSlug")] + list(config.get("secondaryArticleSlugs") or [])
    if module.type == "featured_stories":
        return list(config.get("articleSlugs") or [])
    if module.type in ARTICLE_COLLECTION_SOURCES and config.get("source") in ("manual", "editorial"):
        return list(config.get("articleSlugs") or [])
    if module.type == "content_collection" and config.get("entityType") == "articles" and module.selection_mode == "manual":
        return list(config.get("slugs") or [])
    return []


def duplicate_selection_warnings(modules):
    """{module.id: [warning]} for Articles an editor explicitly picked in more
    than one ENABLED module. Never blocks saving; says what the public page
    will do (the later pick is skipped)."""
    first_seen, warnings = {}, {}
    for module in modules:
        if not module.enabled:
            continue
        for slug in _explicit_article_slugs(module):
            if not slug:
                continue
            if slug in first_seen and first_seen[slug][0] != module.id:
                where = _MODULE_LABELS.get(first_seen[slug][1], first_seen[slug][1])
                warnings.setdefault(module.id, []).append(
                    f'"{slug}" is already used earlier in {where}. It will be skipped here on the public homepage.')
            else:
                first_seen.setdefault(slug, (module.id, module.type))
    return warnings
