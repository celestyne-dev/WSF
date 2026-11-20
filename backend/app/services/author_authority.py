"""Author authority profile — the bounded "what has this contributor
written, built and taught" block shown on /authors/<slug> and in its
server prerender.

Author stays the single contributor identity (byline, Resource author,
Learning instructor); Person stays the separate editorial subject. Nothing
here copies Person data into the Author profile.

Every list is bounded and every collection is loaded in one batched query
with eager loads; counts are COUNT queries, never stored columns. Only
publicly visible content is ever returned: published Articles, publicly
visible Resources (anonymous payload — no file targets) and published
Learning programs (summary shape — no curriculum).
"""
from datetime import date

from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from app.extensions import db

RESOURCE_LIMIT = 3
LEARNING_LIMIT = 3
ARTICLE_LIMIT = 6


def _resource_query(author):
    from app.models.resource import Resource

    today = date.today()
    return Resource.query.filter(
        Resource.author_id == author.id,
        or_(
            Resource.status == "published",
            and_(Resource.status == "scheduled", Resource.published_date.isnot(None), Resource.published_date <= today),
        ),
    )


def _learning_query(author):
    from app.models.learning import LearningProgram
    from app.models.people import Author

    return LearningProgram.query.filter(
        LearningProgram.status == "published",
        or_(LearningProgram.primary_instructor_id == author.id, LearningProgram.co_instructors.any(Author.id == author.id)),
    )


def _article_query(author):
    from app.models.article import Article

    return Article.query.filter(Article.author_id == author.id, Article.status == "published")


def author_counts(author):
    return {
        "articles": _article_query(author).count(),
        "resources": _resource_query(author).count(),
        "courses": _learning_query(author).count(),
    }


def author_resources(author, limit=RESOURCE_LIMIT):
    from app.api.v1.resources import build_public_resource_payload, prefetch_linked_products
    from app.models.media import Media
    from app.models.resource import Resource

    rows = (
        _resource_query(author)
        .options(
            selectinload(Resource.images), selectinload(Resource.topics), selectinload(Resource.tags),
            selectinload(Resource.author), selectinload(Resource.sponsor), selectinload(Resource.prices),
            selectinload(Resource.cover_media).selectinload(Media.variants),
        )
        .order_by(Resource.featured.desc(), Resource.published_date.desc().nullslast(), Resource.id.desc())
        .limit(limit)
        .all()
    )
    products = prefetch_linked_products(rows)
    return [build_public_resource_payload(r, None, linked_products=products, viewer_tier=None) for r in rows]


def author_learning(author, limit=LEARNING_LIMIT):
    from app.models.learning import LearningProgram
    from app.schemas.learning import summary_schema_for
    from app.services.public_visibility import public_learning_dump

    rows = (
        _learning_query(author)
        .options(
            selectinload(LearningProgram.primary_instructor), selectinload(LearningProgram.co_instructors),
            selectinload(LearningProgram.provider_organization), selectinload(LearningProgram.topics),
            selectinload(LearningProgram.event_links), selectinload(LearningProgram.hero_media),
            selectinload(LearningProgram.product),
        )
        .order_by(LearningProgram.featured.desc(), LearningProgram.published_at.desc().nullslast(), LearningProgram.id.desc())
        .limit(limit)
        .all()
    )
    schema = summary_schema_for(rows)
    return [public_learning_dump(schema.dump(p), p) for p in rows]


def author_latest_articles(author, limit=ARTICLE_LIMIT):
    from app.models.article import Article
    from app.schemas.article import article_summary_schema

    rows = (
        _article_query(author)
        .options(selectinload(Article.author), selectinload(Article.topics), selectinload(Article.tags),
                 selectinload(Article.series), selectinload(Article.category), selectinload(Article.hero_media))
        .order_by(Article.publish_date.desc().nullslast(), Article.id.desc())
        .limit(limit)
        .all()
    )
    return article_summary_schema(many=True).dump(rows)


def author_authority(author):
    """The bounded authority block for the public Author detail payload."""
    return {
        "counts": author_counts(author),
        "resources": author_resources(author),
        "learningPrograms": author_learning(author),
    }


# AuthorProfilePage requests its article archive 9 per page
# (fetchArticles({author, page, pageSize: 9})); the hard-load bootstrap
# embeds exactly that first page so the page never refetches it.
AUTHOR_ARTICLE_PAGE_SIZE = 9


def author_article_first_page(author, per_page=AUTHOR_ARTICLE_PAGE_SIZE):
    """Page 1 of GET /api/v1/articles?author=<slug>: the same filter
    (published, this author), order (newest publish_date first) and
    summary schema, eager-loaded, with non-public taxonomy removed.
    Returns (items, meta) in the API's own pagination-meta shape."""
    from app.models.article import Article
    from app.schemas.article import article_summary_schema
    from app.services.public_visibility import public_article_dump

    query = (
        Article.query.filter_by(author_id=author.id, status="published")
        .options(selectinload(Article.author), selectinload(Article.topics), selectinload(Article.tags),
                 selectinload(Article.series), selectinload(Article.category), selectinload(Article.hero_media))
        .order_by(Article.publish_date.desc())
    )
    result = query.paginate(page=1, per_page=per_page, error_out=False)
    items = [public_article_dump(d, a) for d, a in zip(article_summary_schema(many=True).dump(result.items), result.items)]
    meta = {"page": result.page, "per_page": result.per_page, "total": result.total, "total_pages": result.pages,
            "has_next": result.has_next, "has_prev": result.has_prev}
    return items, meta
