from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.extensions import db
from app.models.article import Article
from app.models.people import Person
from app.models.taxonomy import Series
from app.schemas.people import PersonInputSchema, PersonSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

people_bp = Blueprint("people", __name__)
api = Api(people_bp)
person_schema = PersonSchema()


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _can_edit_or_none():
    """Best-effort permission check that never raises — used to decide
    whether a GET should include drafts/archived profiles, mirroring
    ArticleDetailResource's can_edit pattern so an unpublished Person 404s
    for the public exactly like a nonexistent slug rather than leaking
    existence via a 401/403.
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
        raise ApiError("You do not have permission to manage people.", 403, code="forbidden")
    return user


def _resolve_series(slugs):
    if not slugs:
        return []
    found = Series.query.filter(Series.slug.in_(slugs)).all()
    found_slugs = {s.slug for s in found}
    missing = [s for s in slugs if s not in found_slugs]
    if missing:
        raise ApiError(f'Series "{missing[0]}" not found.', 404, code="not_found")
    return found


def _apply_fields(person, data, series):
    person.name = data["name"]
    person.pronouns = data.get("pronouns")
    person.photo_media_id = data.get("photo_media_id")
    person.title = data.get("title")
    person.organization_id = data.get("organization_id")
    person.location = data.get("location")
    person.country_code = data.get("country_code")
    person.industry = data.get("industry")
    person.profession = data.get("profession")
    person.expertise = data.get("expertise", [])
    person.featured_quote = data.get("featured_quote")
    person.short_bio = data.get("short_bio")
    person.bio = sanitize_content_blocks(data.get("bio", []))
    person.achievements = data.get("achievements", [])
    person.career_timeline = data.get("career_timeline", [])
    person.awards = data.get("awards", [])
    person.website = data.get("website")
    person.social = data.get("social")
    person.series = series
    person.status = data.get("status", "draft")
    person.seo = data.get("seo")
    person.featured = data.get("featured", False)


def _validate_for_publish(person):
    """A draft may stay incomplete indefinitely, but a published profile
    needs enough real public content to be worth showing — name/slug are
    already guaranteed by PersonInputSchema before this runs.
    """
    has_bio = bool(person.short_bio) or bool(person.bio)
    if not has_bio:
        raise ApiError(
            "Add a short introduction or biography before publishing this profile.",
            422,
            code="publish_validation_failed",
        )


def _is_referenced_by_articles(person):
    return Article.query.filter(Article.related_people.any(id=person.id)).first() is not None


class PersonListResource(Resource):
    def get(self):
        editor = _can_edit_or_none()
        query = Person.query.order_by(Person.featured.desc(), Person.name)
        if not editor:
            query = query.filter(Person.status == "published")
        elif request.args.get("status"):
            query = query.filter(Person.status == request.args["status"])
        query = apply_country_or_region_filter(query, Person, request.args)
        query = apply_equality_filters(query, Person, request.args, ["industry"])
        query = apply_search(query, Person, request.args, ["name", "title", "industry"], param="query")
        if request.args.get("organization"):
            query = query.filter(Person.organization.has(slug=request.args["organization"]))
        if request.args.get("series"):
            query = query.filter(Person.series.any(slug=request.args["series"]))
        result = paginate(query, person_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        _require_manage()
        data = PersonInputSchema().load(request.get_json(silent=True) or {})
        series = _resolve_series(data.pop("series_slugs", []))

        person = Person()
        if data.get("slug"):
            person.slug = validate_explicit_slug(Person, data["slug"])
        else:
            person.slug = generate_unique_slug(Person, data["name"])

        _apply_fields(person, data, series)
        if person.status == "published":
            _validate_for_publish(person)
        db.session.add(person)
        db.session.commit()
        return success_response(person_schema.dump(person), status=201)


class PersonDetailResource(Resource):
    def get(self, slug):
        person = Person.query.filter_by(slug=slug).first()
        if person is None:
            raise ApiError("Person not found.", 404, code="not_found")
        if person.status != "published" and not _can_edit_or_none():
            raise ApiError("Person not found.", 404, code="not_found")
        return success_response(person_schema.dump(person))

    def put(self, slug):
        _require_manage()
        person = Person.query.filter_by(slug=slug).first()
        if person is None:
            raise ApiError("Person not found.", 404, code="not_found")

        data = PersonInputSchema().load(request.get_json(silent=True) or {})
        series = _resolve_series(data.pop("series_slugs", []))

        if data.get("slug") and data["slug"] != person.slug:
            person.slug = validate_explicit_slug(Person, data["slug"], current_id=person.id)

        _apply_fields(person, data, series)
        if person.status == "published":
            _validate_for_publish(person)
        db.session.commit()
        return success_response(person_schema.dump(person))

    def delete(self, slug):
        _require_manage()
        person = Person.query.filter_by(slug=slug).first()
        if person is None:
            raise ApiError("Person not found.", 404, code="not_found")

        if _is_referenced_by_articles(person):
            raise ApiError(
                "This person is referenced by one or more articles and can't be deleted. "
                "Remove them from those articles first, or archive this profile instead.",
                409,
                code="reference_conflict",
            )

        db.session.delete(person)
        db.session.commit()
        return success_response({"deleted": True})


api.add_resource(PersonListResource, "")
api.add_resource(PersonDetailResource, "/<string:slug>")
