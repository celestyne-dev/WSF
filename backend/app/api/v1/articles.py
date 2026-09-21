from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.extensions import db
from app.models.article import Article, ArticleRevision, Redirect
from app.models.people import Author, Organization, Person
from app.models.taxonomy import Category, Series, Tag, Topic
from app.schemas.article import ArticleInputSchema, ArticleSchema, article_summary_schema
from app.services.audit import log_action
from app.services.slugs import create_redirect_for_slug_change, generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, error_response, success_response
from app.utils.slugs import slugify

articles_bp = Blueprint("articles", __name__)
api = Api(articles_bp)

article_schema = ArticleSchema()


def _require_active_user():
    verify_jwt_in_request()
    # current_user is a LocalProxy — `is None` is always False even when it
    # wraps None, so check truthiness instead (correctly delegated to the
    # wrapped object by the proxy).
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _can_create():
    user = _require_active_user()
    if not user.has_permission("articles.create", "articles.manage"):
        raise ApiError("You do not have permission to create articles.", 403, code="forbidden")
    return user


def _can_edit(article):
    user = _require_active_user()
    if user.has_permission("articles.manage"):
        return user
    if user.has_permission("articles.edit_own"):
        owns_by_creator = article.created_by_id == user.id
        owns_by_byline = article.author is not None and article.author.user_id == user.id
        if owns_by_creator or owns_by_byline:
            return user
    raise ApiError("You do not have permission to edit this article.", 403, code="forbidden")


def _resolve_relations(data):
    """Turn the input schema's slug lists into ORM objects/ids. Raises a
    404-flavoured ApiError naming the first slug that doesn't exist, so a
    client sees exactly what's wrong rather than a silent partial save.
    """
    resolved = {}

    author = Author.query.filter_by(slug=data["author_slug"]).first()
    if author is None:
        raise ApiError(f"Author \"{data['author_slug']}\" not found.", 404, code="not_found")
    resolved["author"] = author

    resolved["co_authors"] = _lookup_all(Author, data.get("co_author_slugs", []), "co-author")

    resolved["category"] = None
    if data.get("category_slug"):
        resolved["category"] = Category.query.filter_by(slug=data["category_slug"]).first()
        if resolved["category"] is None:
            raise ApiError(f"Category \"{data['category_slug']}\" not found.", 404, code="not_found")

    resolved["series"] = None
    if data.get("series_slug"):
        resolved["series"] = Series.query.filter_by(slug=data["series_slug"]).first()
        if resolved["series"] is None:
            raise ApiError(f"Series \"{data['series_slug']}\" not found.", 404, code="not_found")

    resolved["topics"] = _lookup_all(Topic, data.get("topic_slugs", []), "topic")
    resolved["related_people"] = _lookup_all(Person, data.get("related_person_slugs", []), "person")
    resolved["related_organizations"] = _lookup_all(
        Organization, data.get("related_organization_slugs", []), "organization"
    )
    resolved["related_articles"] = _lookup_all(Article, data.get("related_article_slugs", []), "article")

    # Tags are freeform — get-or-create by slug rather than a hard 404.
    tags = []
    for raw in data.get("tag_slugs", []):
        slug = slugify(raw)
        tag = Tag.query.filter_by(slug=slug).first()
        if tag is None:
            tag = Tag(slug=slug, name=raw.replace("-", " ").replace("_", " ").title())
            db.session.add(tag)
        tags.append(tag)
    resolved["tags"] = tags

    return resolved


def _lookup_all(model, slugs, label):
    if not slugs:
        return []
    found = model.query.filter(model.slug.in_(slugs)).all()
    found_slugs = {item.slug for item in found}
    missing = [s for s in slugs if s not in found_slugs]
    if missing:
        raise ApiError(f'{label.capitalize()} "{missing[0]}" not found.', 404, code="not_found")
    return found


def _apply_fields(article, data, relations):
    article.title = data["title"]
    article.subtitle = data.get("subtitle")
    article.excerpt = data.get("excerpt")
    article.hero_media_id = data.get("hero_media_id")
    article.hero_image_caption = data.get("hero_image_caption")
    article.hero_image_credit = data.get("hero_image_credit")
    article.author = relations["author"]
    article.co_authors = relations["co_authors"]
    article.publish_date = data.get("publish_date")
    article.reading_time = data.get("reading_time")
    article.category = relations["category"]
    article.series = relations["series"]
    article.topics = relations["topics"]
    article.tags = relations["tags"]
    article.related_people = relations["related_people"]
    article.related_organizations = relations["related_organizations"]
    article.related_articles = relations["related_articles"]
    article.featured = data.get("featured", False)
    article.promoted = data.get("promoted", False)
    article.is_sponsored = data.get("is_sponsored", False)
    article.sponsor = data.get("sponsor")
    article.status = data.get("status", "draft")
    article.seo = data.get("seo")
    article.content = data.get("content", [])


def _snapshot(article, user, note=None):
    db.session.add(
        ArticleRevision(
            article_id=article.id,
            data=article_schema.dump(article),
            note=note,
            created_by_id=user.id if user else None,
        )
    )


class ArticleListResource(Resource):
    def get(self):
        query = Article.query.filter_by(status="published")
        topic_slug = request.args.get("topic")
        if topic_slug:
            query = query.filter(Article.topics.any(slug=topic_slug))
        if request.args.get("series"):
            query = query.join(Series).filter(Series.slug == request.args["series"])
        if request.args.get("author"):
            query = query.join(Author).filter(Author.slug == request.args["author"])
        if request.args.get("category"):
            query = query.join(Category).filter(Category.slug == request.args["category"])
        query = apply_search(query, Article, request.args, ["title", "excerpt"], param="query")
        query = query.order_by(Article.publish_date.desc())

        result = paginate(query, None)
        items = article_summary_schema(many=True).dump(result["items"])
        return success_response(items, meta=result["meta"])

    def post(self):
        user = _can_create()
        data = ArticleInputSchema().load(request.get_json(silent=True) or {})
        relations = _resolve_relations(data)

        article = Article(created_by_id=user.id)
        if data.get("slug"):
            article.slug = validate_explicit_slug(Article, data["slug"])
        else:
            article.slug = generate_unique_slug(Article, data["title"])

        _apply_fields(article, data, relations)
        db.session.add(article)
        db.session.flush()
        _snapshot(article, user, note="Created")
        db.session.commit()

        log_action(user, "article.create", "Article", article.id)
        return success_response(article_schema.dump(article), status=201)


class ArticleDetailResource(Resource):
    def get(self, slug):
        article = Article.query.filter_by(slug=slug).first()
        if article is not None:
            if article.status != "published":
                # Only someone who can edit it may preview an unpublished
                # article — an anonymous request or a bad/missing token
                # should 404 exactly like a nonexistent slug, not leak that
                # a draft exists via a 401/403.
                try:
                    _can_edit(article)
                except Exception:
                    raise ApiError("Article not found.", 404, code="not_found")
            return success_response(article_schema.dump(article))

        redirect = Redirect.query.filter_by(from_slug=slug).first()
        if redirect:
            body, _status = success_response({"redirect": redirect.to_slug})
            return body, 301, {"Location": f"/api/v1/articles/{redirect.to_slug}"}

        raise ApiError("Article not found.", 404, code="not_found")

    def put(self, slug):
        article = Article.query.filter_by(slug=slug).first()
        if article is None:
            raise ApiError("Article not found.", 404, code="not_found")
        user = _can_edit(article)

        data = ArticleInputSchema().load(request.get_json(silent=True) or {})
        relations = _resolve_relations(data)

        old_slug = article.slug
        if data.get("slug") and data["slug"] != old_slug:
            article.slug = validate_explicit_slug(Article, data["slug"], current_id=article.id)

        _apply_fields(article, data, relations)
        db.session.flush()
        _snapshot(article, user, note="Updated")

        if article.slug != old_slug:
            create_redirect_for_slug_change(article, old_slug, article.slug)

        db.session.commit()
        log_action(user, "article.update", "Article", article.id)
        return success_response(article_schema.dump(article))


class ArticlePublishResource(Resource):
    def post(self, slug):
        article = Article.query.filter_by(slug=slug).first()
        if article is None:
            raise ApiError("Article not found.", 404, code="not_found")

        user = _require_active_user()
        if not user.has_permission("articles.publish", "articles.manage"):
            return error_response("You do not have permission to publish articles.", 403, code="forbidden")

        article.status = "published"
        if article.publish_date is None:
            article.publish_date = datetime.now(timezone.utc)
        db.session.flush()
        _snapshot(article, user, note="Published")
        db.session.commit()

        log_action(user, "article.publish", "Article", article.id)
        return success_response(article_schema.dump(article))


class ArticleRevisionsResource(Resource):
    def get(self, slug):
        article = Article.query.filter_by(slug=slug).first()
        if article is None:
            raise ApiError("Article not found.", 404, code="not_found")
        _can_edit(article)

        revisions = [
            {
                "id": revision.id,
                "note": revision.note,
                "createdAt": revision.created_at.isoformat(),
                "createdBy": revision.created_by.full_name if revision.created_by else None,
            }
            for revision in article.revisions
        ]
        return success_response(revisions)


class ArticleRelatedResource(Resource):
    """POST body {"slugs": [...]} -> the matching published articles, in
    the same summary shape as the list endpoint. Matches
    frontend/src/api/articles.js:fetchRelatedArticles exactly.
    """

    def post(self):
        slugs = (request.get_json(silent=True) or {}).get("slugs", [])
        if not slugs:
            return success_response([])

        found = {
            a.slug: a
            for a in Article.query.filter(Article.slug.in_(slugs), Article.status == "published").all()
        }
        ordered = [found[slug] for slug in slugs if slug in found]
        return success_response(article_summary_schema(many=True).dump(ordered))


api.add_resource(ArticleListResource, "")
api.add_resource(ArticleRelatedResource, "/related")
api.add_resource(ArticleDetailResource, "/<string:slug>")
api.add_resource(ArticlePublishResource, "/<string:slug>/publish")
api.add_resource(ArticleRevisionsResource, "/<string:slug>/revisions")
