from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.people import Author, Person
from app.models.taxonomy import Topic
from app.schemas.article import article_summary_schema
from app.schemas.people import AuthorInputSchema, AuthorSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

authors_bp = Blueprint("authors", __name__)
api = Api(authors_bp)
author_schema = AuthorSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _can_edit_or_none():
    """Mirrors PersonListResource's pattern: best-effort permission check
    that never raises, used to decide whether a GET should include
    draft/archived Authors and, for detail, whether an inactive Author
    404s for the public exactly like a nonexistent slug.
    """
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    if current_user.has_permission("people.manage"):
        return current_user
    return None


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("people.manage"):
        raise ApiError("You do not have permission to manage authors.", 403, code="forbidden")
    return user


def _resolve_topics(slugs):
    if not slugs:
        return []
    found = Topic.query.filter(Topic.slug.in_(slugs)).all()
    found_slugs = {t.slug for t in found}
    missing = [s for s in slugs if s not in found_slugs]
    if missing:
        raise ApiError(f'Topic "{missing[0]}" not found.', 404, code="not_found")
    return found


def _resolve_person(person_id):
    if not person_id:
        return None
    person = db.session.get(Person, person_id)
    if person is None:
        raise ApiError("Linked person not found.", 404, code="not_found")
    return person


def _apply_fields(author, data, topics, person):
    author.name = data["name"]
    author.role = data.get("role")
    author.photo_media_id = data.get("photo_media_id")
    author.bio = sanitize_content_blocks(data.get("bio", []))
    author.short_bio = data.get("short_bio")
    author.expertise = data.get("expertise", [])
    author.topics = topics
    author.location = data.get("location")
    author.country_code = data.get("country_code")
    author.social = data.get("social")
    author.website = data.get("website")
    author.person = person
    author.status = data.get("status", "draft")
    author.seo = data.get("seo")


def _validate_for_publish(author):
    """An active/published Author needs enough real public information to
    be worth showing; a draft may stay incomplete indefinitely.
    """
    has_bio = bool(author.short_bio) or bool(author.bio)
    if not has_bio:
        raise ApiError(
            "Add a short bio or biography before activating this author.",
            422,
            code="publish_validation_failed",
        )


def _is_referenced_by_articles(author):
    return Article.query.filter(
        or_(Article.author_id == author.id, Article.co_authors.any(id=author.id))
    ).first() is not None


class AuthorListResource(Resource):
    def get(self):
        editor = _can_edit_or_none()
        query = Author.query.order_by(Author.name)
        if not editor:
            query = query.filter(Author.status == "active")
        elif request.args.get("status"):
            query = query.filter(Author.status == request.args["status"])
        query = apply_country_or_region_filter(query, Author, request.args)
        query = apply_search(query, Author, request.args, ["name", "role"], param="query")
        if request.args.get("topic"):
            query = query.filter(Author.topics.any(slug=request.args["topic"]))
        result = paginate(query, author_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("people.manage")
    def post(self):
        data = AuthorInputSchema().load(request.get_json(silent=True) or {})
        topics = _resolve_topics(data.pop("topic_slugs", []))
        person = _resolve_person(data.get("person_id"))

        author = Author()
        if data.get("slug"):
            author.slug = validate_explicit_slug(Author, data["slug"])
        else:
            author.slug = generate_unique_slug(Author, data["name"])

        _apply_fields(author, data, topics, person)
        if author.status == "active":
            _validate_for_publish(author)
        db.session.add(author)
        db.session.commit()
        return success_response(author_schema.dump(author), status=201)


class AuthorDetailResource(Resource):
    def get(self, slug):
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            raise ApiError("Author not found.", 404, code="not_found")
        if author.status != "active" and not _can_edit_or_none():
            raise ApiError("Author not found.", 404, code="not_found")

        query = Article.query.filter_by(author_id=author.id, status="published").order_by(
            Article.publish_date.desc()
        )
        result = paginate(query, None)
        articles = article_summary_schema(many=True).dump(result["items"])
        return success_response(
            {"author": author_schema.dump(author), "articles": articles}, meta=result["meta"]
        )

    def put(self, slug):
        _require_manage()
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            raise ApiError("Author not found.", 404, code="not_found")

        data = AuthorInputSchema().load(request.get_json(silent=True) or {})
        topics = _resolve_topics(data.pop("topic_slugs", []))
        person = _resolve_person(data.get("person_id"))

        if data.get("slug") and data["slug"] != author.slug:
            author.slug = validate_explicit_slug(Author, data["slug"], current_id=author.id)

        _apply_fields(author, data, topics, person)
        if author.status == "active":
            _validate_for_publish(author)
        db.session.commit()
        return success_response(author_schema.dump(author))

    def delete(self, slug):
        _require_manage()
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            raise ApiError("Author not found.", 404, code="not_found")

        if _is_referenced_by_articles(author):
            raise ApiError(
                "This author is credited on one or more articles and can't be deleted. "
                "Reassign those articles first, or archive this author instead.",
                409,
                code="reference_conflict",
            )

        db.session.delete(author)
        db.session.commit()
        return success_response({"deleted": True})


api.add_resource(AuthorListResource, "")
api.add_resource(AuthorDetailResource, "/<string:slug>")
