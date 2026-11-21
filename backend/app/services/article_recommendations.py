"""What an Article page recommends, chosen once on the server.

The Article being read is reserved first: it never appears in any block on
its own page. Stories an editor embedded in the body (relatedBlock) come
next, since the body is read first. Then first placement wins, in this
priority: Up next -> Related reading -> More from the author -> More on WSF
(sidebar). Relevant Learning and Resources come from the Article's own
published Topics (deterministic, no behavioral tracking).

GET /articles/<slug>/recommendations and the hard-load Article bootstrap
both return exactly this, so React never re-selects.
"""
from app.models.article import Article
from app.services.editorial_selection import EditorialSelection, article_cards, newest_first, public_articles

RELATED_COUNT = 3
AUTHOR_COUNT = 3
SIDEBAR_COUNT = 5
LEARNING_COUNT = 1
RESOURCE_COUNT = 2


def _body_slugs(article):
    slugs = []
    for block in article.content or []:
        if isinstance(block, dict) and block.get("type") == "relatedBlock":
            slugs.extend(s for s in block.get("articleSlugs") or [] if isinstance(s, str))
    return list(dict.fromkeys(slugs))


def _topic_ids(article):
    return [t.id for t in article.topics if t.status == "published"]


def _up_next(article, selection):
    """The next story in the Article's Series (by publish order), else the
    newest story sharing its first Topic, else the newest story."""
    from app.models.taxonomy import Topic

    if article.series_id is not None and article.series is not None and article.series.status == "published":
        in_series = public_articles().filter(Article.series_id == article.series_id)
        if article.publish_date is not None:
            later = in_series.filter(Article.publish_date > article.publish_date).order_by(
                Article.publish_date.asc(), Article.id.asc())
            picked = selection.pick_query(later, 1, "up_next")
            if picked:
                return picked
        picked = selection.pick_query(newest_first(in_series), 1, "up_next")
        if picked:
            return picked
    topic_ids = _topic_ids(article)
    if topic_ids:
        picked = selection.pick_query(newest_first(public_articles().filter(Article.topics.any(Topic.id == topic_ids[0]))), 1, "up_next")
        if picked:
            return picked
    return selection.pick_query(newest_first(public_articles()), 1, "up_next")


def _learning(topic_ids):
    from app.services.homepage_collections import _build_collection_items, _query_collection

    if not topic_ids:
        return []
    rows = [p for p in _query_collection("learning", {"sort": "newest"}, [], 20)
            if any(t.id in topic_ids for t in p.topics)]
    rows.sort(key=lambda p: (not p.featured, -sum(1 for t in p.topics if t.id in topic_ids)))
    return _build_collection_items("learning", rows, LEARNING_COUNT)


def _resources(topic_ids):
    from app.models.resource import Resource
    from app.services.homepage_collections import _build_collection_items

    if not topic_ids:
        return []
    from app.models.taxonomy import Topic

    rows = (Resource.query.filter(Resource.status.in_(["published", "scheduled"]), Resource.topics.any(Topic.id.in_(topic_ids)))
            .order_by(Resource.featured.desc(), Resource.published_date.desc().nullslast(), Resource.id.desc())
            .limit(RESOURCE_COUNT * 3).all())
    return _build_collection_items("resources", rows, RESOURCE_COUNT)


def article_recommendations(article, selection=None):
    """{bodyArticles, upNext, related, moreFromAuthor, sidebar, learning,
    resources} for a published Article. Pass `selection` to inspect the
    placements (tests)."""
    from app.models.taxonomy import Topic

    selection = selection or EditorialSelection()
    selection.reserve_ids([article.id], "current")
    body = selection.pick_manual(_body_slugs(article), 9, "body")
    up_next = _up_next(article, selection)

    topic_ids = _topic_ids(article)
    related_manual = [a.slug for a in article.related_articles]
    topic_backfill = newest_first(public_articles().filter(Article.topics.any(Topic.id.in_(topic_ids)))) if topic_ids else None
    related = selection.pick_manual_then_query(related_manual, topic_backfill, RELATED_COUNT, "related")

    by_author = selection.pick_query(newest_first(public_articles().filter(Article.author_id == article.author_id)),
                                     AUTHOR_COUNT, "more_from_author")
    sidebar = selection.pick_query(newest_first(public_articles()), SIDEBAR_COUNT, "sidebar")
    return {
        "bodyArticles": article_cards(body),
        "upNext": article_cards(up_next)[0] if up_next else None,
        "related": article_cards(related),
        "moreFromAuthor": article_cards(by_author),
        "sidebar": article_cards(sidebar),
        "learning": _learning(topic_ids),
        "resources": _resources(topic_ids),
    }
