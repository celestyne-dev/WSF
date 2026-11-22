"""A Topic page as a destination: one page-level selection, in page order.

Start here (the editor's cornerstone plus curated picks) -> Latest ->
Editor's picks, all through ONE EditorialSelection, so no Article appears
twice on the page. Learning, career tools (Resources) and Opportunities come
from the Topic's own relationships. Related topics are the editor-configured
links (topics.related_topics), never inferred from names. Every section is
omitted when empty.

GET /topics/<slug>/hub and the hard-load Topic bootstrap both return this,
and the server prerender renders it, so React never re-selects.
"""
from app.models.article import Article
from app.services.editorial_selection import EditorialSelection, article_cards, newest_first, public_articles

START_HERE_COUNT = 3
LATEST_COUNT = 6
PICKS_COUNT = 4
SHELF_COUNT = 3


def _hub_config(topic):
    hub = topic.hub if isinstance(topic.hub, dict) else {}
    return {
        "startHereSlugs": [s for s in hub.get("startHereSlugs") or [] if isinstance(s, str)],
        "editorsPicksSlugs": [s for s in hub.get("editorsPicksSlugs") or [] if isinstance(s, str)],
    }


def _related_topics(topic):
    return [{"slug": t.slug, "name": t.name, "description": t.description}
            for t in topic.related_topics if t.status == "published"]


def _shelf(entity, topic, limit):
    from app.services.homepage_collections import _build_collection_items, _query_collection

    rows = [r for r in _query_collection(entity, {"sort": "newest"}, [], 30) if any(t.id == topic.id for t in r.topics)]
    if entity in ("learning", "resources"):
        rows.sort(key=lambda r: not getattr(r, "featured", False))
    return _build_collection_items(entity, rows, limit)


def _topic_resources(topic):
    from app.services.article_recommendations import public_topic_resources

    return public_topic_resources([topic.id], SHELF_COUNT)


def topic_hub(topic, selection=None):
    selection = selection or EditorialSelection()
    config = _hub_config(topic)
    topic_articles = public_articles().filter(Article.topics.any(id=topic.id))

    start_slugs = ([topic.featured_article.slug] if topic.featured_article is not None else []) + config["startHereSlugs"]
    start_here = selection.pick_manual(start_slugs, START_HERE_COUNT, "start_here")
    latest = selection.pick_query(newest_first(topic_articles), LATEST_COUNT, "latest")
    picks = selection.pick_manual(config["editorsPicksSlugs"], PICKS_COUNT, "editors_picks")
    return {
        "relatedTopics": _related_topics(topic),
        "startHere": article_cards(start_here),
        "latest": article_cards(latest),
        "editorsPicks": article_cards(picks),
        "learning": _shelf("learning", topic, SHELF_COUNT),
        "resources": _topic_resources(topic),
        "opportunities": _shelf("opportunities", topic, SHELF_COUNT),
    }


def admin_hub(topic):
    config = _hub_config(topic)
    return {**config, "relatedTopicSlugs": [t.slug for t in topic.related_topics]}


def save_hub(topic, data):
    """Studio input {startHereSlugs, editorsPicksSlugs, relatedTopicSlugs}.
    Validates every slug before changing anything."""
    from marshmallow import ValidationError

    from app.extensions import db
    from app.models.taxonomy import Topic, topic_related_topics

    if not isinstance(data, dict):
        raise ValidationError("Invalid hub settings.", field_name="hub")

    def slugs(key, limit):
        value = data.get(key) or []
        if not isinstance(value, list) or not all(isinstance(s, str) and s.strip() for s in value):
            raise ValidationError(f"{key} must be a list of slugs.", field_name=key)
        value = list(dict.fromkeys(s.strip() for s in value))
        if len(value) > limit:
            raise ValidationError(f"Pick at most {limit}.", field_name=key)
        return value

    start, picks = slugs("startHereSlugs", 6), slugs("editorsPicksSlugs", 8)
    related = slugs("relatedTopicSlugs", 12)
    articles = {a.slug for a in Article.query.filter(Article.slug.in_(start + picks)).all()} if start + picks else set()
    missing = [s for s in start + picks if s not in articles]
    if missing:
        raise ValidationError(f"These articles don't exist: {', '.join(missing)}.", field_name="hub")
    if topic.slug in related:
        raise ValidationError("A topic can't be related to itself.", field_name="relatedTopicSlugs")
    rows = Topic.query.filter(Topic.slug.in_(related)).all() if related else []
    by_slug = {t.slug: t for t in rows}
    missing = [s for s in related if s not in by_slug]
    if missing:
        raise ValidationError(f"These topics don't exist: {', '.join(missing)}.", field_name="relatedTopicSlugs")

    topic.hub = {"startHereSlugs": start, "editorsPicksSlugs": picks}
    db.session.execute(topic_related_topics.delete().where(topic_related_topics.c.topic_id == topic.id))
    for position, slug in enumerate(related):
        db.session.execute(topic_related_topics.insert().values(
            topic_id=topic.id, related_topic_id=by_slug[slug].id, position=position))
    db.session.expire(topic, ["related_topics"])
