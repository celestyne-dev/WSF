from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource
from sqlalchemy import func

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.audit import AuditLog
from app.models.geography import Country
from app.models.people import Author, Organization, Person
from app.models.nominations import Nomination, NominationNote
from app.models.taxonomy import Series, Topic
from app.models.user import User
from app.schemas.nominations import (
    ArticleRefSchema,
    NominationAssignInputSchema,
    NominationConvertToArticleInputSchema,
    NominationInputSchema,
    NominationListItemSchema,
    NominationNoteInputSchema,
    NominationRelatedSchema,
    NominationSchema,
    NominationStatusInputSchema,
    NominationUpdateSchema,
)
from app.services.audit import log_action
from app.services.newsletter import upsert_subscriber
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

nominations_bp = Blueprint("nominations", __name__)
api = Api(nominations_bp)

nomination_schema = NominationSchema()
nomination_list_schema = NominationListItemSchema()
note_schema = NominationNoteInputSchema()
article_ref_schema = ArticleRefSchema()
related_nomination_schema = NominationRelatedSchema()

# A nomination may only move into these statuses through the manual
# review workflow. "in_editorial"/"published" are never settable directly
# — see NominationStatusResource.
_MANUALLY_SETTABLE_STATUSES = (
    "submitted", "reviewing", "verification_needed", "shortlisted", "approved",
    "declined", "withdrawn", "archived",
)

# A nomination may only be hard-deleted while it's still an early, inert
# lead — never once it has editorial history, a link into Article, or has
# progressed past initial triage. Prefer Archive otherwise.
_DELETABLE_STATUSES = ("submitted", "reviewing", "declined", "withdrawn")


def _resolve_topics(slugs):
    if not slugs:
        return []
    return Topic.query.filter(Topic.slug.in_(slugs)).all()


def _normalized(name):
    return " ".join((name or "").strip().lower().split())


def _find_recent_duplicate(nominator_email, nominee_name, achievements):
    """Prevent an accidental double submission from repeated button
    clicks — an identical nominee+achievements from the same nominator
    within a short window is treated as the same click, not a second
    legitimate nomination for the same woman.
    """
    window_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    return Nomination.query.filter(
        Nomination.nominator_email == nominator_email,
        Nomination.nominee_name == nominee_name,
        Nomination.achievements == achievements,
        Nomination.submitted_at >= window_start,
    ).first()


def _detect_possible_duplicate(nominee_name, exclude_id=None):
    """A simple, non-destructive signal — never auto-merged. Flags when
    another nomination shares the same normalized nominee name. See
    DUPLICATE NOMINATION HANDLING / DUPLICATE NOMINEE ASSISTANCE.
    """
    normalized = _normalized(nominee_name)
    if not normalized:
        return False
    query = Nomination.query.filter(func.lower(func.trim(Nomination.nominee_name)) == normalized)
    if exclude_id is not None:
        query = query.filter(Nomination.id != exclude_id)
    return query.first() is not None


def _related_nominations(nomination):
    """Other nominations that likely concern the same nominee — by linked
    Person if one is set, otherwise by normalized nominee name. Computed,
    never stored, and never merges or overwrites any record.
    """
    if nomination.person_id:
        query = Nomination.query.filter(
            Nomination.person_id == nomination.person_id, Nomination.id != nomination.id
        )
    else:
        normalized = _normalized(nomination.nominee_name)
        query = Nomination.query.filter(
            func.lower(func.trim(Nomination.nominee_name)) == normalized, Nomination.id != nomination.id
        )
    return query.order_by(Nomination.submitted_at.desc()).all()


def _build_confirmation(nomination):
    return {"reference": nomination.reference}


class NominationListResource(Resource):
    @permission_required("nominations.manage")
    def get(self):
        query = Nomination.query.order_by(Nomination.submitted_at.desc())
        args = request.args
        query = apply_equality_filters(query, Nomination, args, ["status", "series_id", "verification_state"])
        query = apply_country_or_region_filter(query, Nomination, args)
        if args.get("assigned_reviewer_id"):
            query = query.filter(Nomination.assigned_reviewer_id == args["assigned_reviewer_id"])
        if args.get("topic"):
            query = query.filter(Nomination.topics.any(Topic.slug == args["topic"]))
        if args.get("organization"):
            query = query.filter(Nomination.organization_name.ilike(f"%{args['organization']}%"))
        query = apply_search(
            query, Nomination, args,
            ["reference", "nominee_name", "organization_name", "nominator_name", "nominator_email", "website_url", "linkedin_url"],
        )
        result = paginate(query, nomination_list_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        """The public nomination endpoint — write-only besides a small
        confirmation. Never returns the nomination's id or any stored
        field back to the caller.
        """
        payload = request.get_json(silent=True) or {}
        data = NominationInputSchema().load(payload)

        if not db.session.get(Country, data["country_code"].upper()):
            raise ApiError("Please select a valid country.", 422, code="validation_error")
        if data.get("series_id") is not None and db.session.get(Series, data["series_id"]) is None:
            raise ApiError("Please select a valid series.", 422, code="validation_error")

        nominator_email = data["nominator_email"].strip().lower()
        duplicate = _find_recent_duplicate(nominator_email, data["nominee_name"], data["achievements"])
        if duplicate is not None:
            return success_response(_build_confirmation(duplicate), status=201)

        topic_slugs = data.pop("topic_slugs", [])
        newsletter_opt_in = data.pop("newsletter_opt_in", False)
        data["country_code"] = data["country_code"].upper()
        data["nominator_email"] = nominator_email

        possible_duplicate = _detect_possible_duplicate(data["nominee_name"])

        nomination = Nomination(
            **data, consent_recorded_at=datetime.now(timezone.utc), possible_duplicate=possible_duplicate
        )
        nomination.topics = _resolve_topics(topic_slugs)
        db.session.add(nomination)
        db.session.flush()

        nomination.reference = f"WSF-NOM-{nomination.submitted_at.year}-{nomination.id:05d}"
        db.session.commit()

        if newsletter_opt_in:
            upsert_subscriber(
                nominator_email,
                first_name=nomination.nominator_name.split(" ")[0] if nomination.nominator_name else None,
                country_code=nomination.country_code,
                placement="Nomination",
                acquisition=nomination.acquisition,
            )

        log_action(None, "nomination.received", "nomination", nomination.id, {"reference": nomination.reference})
        return success_response(_build_confirmation(nomination), status=201)


class NominationDetailResource(Resource):
    @permission_required("nominations.manage")
    def get(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")
        nomination.sync_published_state()
        db.session.commit()
        dumped = nomination_schema.dump(nomination)
        dumped["related_nominations"] = related_nomination_schema.dump(_related_nominations(nomination), many=True)
        return success_response(dumped)

    @permission_required("nominations.manage")
    def patch(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        data = NominationUpdateSchema().load(request.get_json(silent=True) or {})
        topic_slugs = data.pop("topic_slugs", None)
        person_id = data.pop("person_id", "unset")
        organization_id = data.pop("organization_id", "unset")

        if data.get("series_id") is not None and db.session.get(Series, data["series_id"]) is None:
            raise ApiError("That Series could not be found.", 422, code="invalid_series")

        if person_id != "unset":
            if person_id is not None and db.session.get(Person, person_id) is None:
                raise ApiError("That Person profile could not be found.", 422, code="invalid_person")
            nomination.person_id = person_id
        if organization_id != "unset":
            if organization_id is not None and db.session.get(Organization, organization_id) is None:
                raise ApiError("That Organization could not be found.", 422, code="invalid_organization")
            nomination.organization_id = organization_id
        if topic_slugs is not None:
            nomination.topics = _resolve_topics(topic_slugs)

        for key, value in data.items():
            setattr(nomination, key, value)

        db.session.commit()
        log_action(current_user, "nomination.updated", "nomination", nomination.id, data)
        return success_response(nomination_schema.dump(nomination))

    @permission_required("nominations.manage")
    def delete(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        if nomination.status not in _DELETABLE_STATUSES or nomination.notes or nomination.resulting_article:
            raise ApiError(
                "This nomination has editorial history and can't be deleted — archive it instead.",
                409,
                code="delete_restricted",
            )

        log_action(current_user, "nomination.deleted", "nomination", nomination.id, {"reference": nomination.reference})
        db.session.delete(nomination)
        db.session.commit()
        return success_response({"deleted": True})


class NominationStatusResource(Resource):
    @permission_required("nominations.manage")
    def patch(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        data = NominationStatusInputSchema().load(request.get_json(silent=True) or {})
        new_status = data["status"]

        if new_status == "published":
            if not nomination.resulting_article or nomination.resulting_article.status != "published":
                raise ApiError(
                    "A nomination can only be marked Published once its linked Article is actually published.",
                    422,
                    code="not_actually_published",
                )
        elif new_status == "in_editorial" and not nomination.resulting_article:
            raise ApiError(
                "A nomination can only be marked In Editorial through the Article-draft handoff.",
                422,
                code="no_linked_article",
            )
        elif new_status not in _MANUALLY_SETTABLE_STATUSES and new_status not in ("in_editorial", "published"):
            raise ApiError("That is not a valid status.", 422, code="validation_error")

        if nomination.status == "submitted" and new_status != "submitted" and nomination.reviewed_at is None:
            nomination.reviewed_at = datetime.now(timezone.utc)

        nomination.status = new_status
        db.session.commit()
        log_action(current_user, "nomination.status_changed", "nomination", nomination.id, {"status": new_status})
        return success_response(nomination_schema.dump(nomination))


class NominationAssignResource(Resource):
    @permission_required("nominations.manage")
    def post(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        data = NominationAssignInputSchema().load(request.get_json(silent=True) or {})
        reviewer_id = data["reviewer_id"]
        if reviewer_id is not None and db.session.get(User, reviewer_id) is None:
            raise ApiError("That reviewer could not be found.", 422, code="invalid_reviewer")

        nomination.assigned_reviewer_id = reviewer_id
        db.session.commit()
        log_action(current_user, "nomination.reviewer_assigned", "nomination", nomination.id, {"reviewer_id": reviewer_id})
        return success_response(nomination_schema.dump(nomination))


class NominationNoteListResource(Resource):
    @permission_required("nominations.manage")
    def post(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        data = note_schema.load(request.get_json(silent=True) or {})
        note = NominationNote(nomination_id=nomination.id, user_id=current_user.id, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "nomination.note_added", "nomination", nomination.id)
        return success_response(nomination_schema.dump(nomination), status=201)


class NominationHistoryResource(Resource):
    @permission_required("nominations.manage")
    def get(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        entries = (
            AuditLog.query.filter_by(entity_type="nomination", entity_id=str(nomination_id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        return success_response(
            [
                {
                    "id": e.id,
                    "action": e.action,
                    "user": e.user.full_name if e.user else None,
                    "createdAt": e.created_at.isoformat() if e.created_at else None,
                }
                for e in entries
            ]
        )


class NominationConvertToArticleResource(Resource):
    """The deliberate, controlled "Create Article Draft" handoff. Never
    reachable except by an editor with nominations.manage — and never
    publishes anything; the resulting Article is always created as a
    draft.
    """

    @permission_required("nominations.manage")
    def post(self, nomination_id):
        nomination = db.session.get(Nomination, nomination_id)
        if nomination is None:
            raise ApiError("Nomination not found.", 404, code="not_found")

        if nomination.status != "approved":
            raise ApiError(
                "Only an Approved nomination can be converted into an Article draft.", 409, code="not_approved"
            )
        if nomination.resulting_article is not None:
            raise ApiError("This nomination already has a linked Article.", 409, code="already_converted")

        data = NominationConvertToArticleInputSchema().load(request.get_json(silent=True) or {})
        author = db.session.get(Author, data["author_id"])
        if author is None:
            raise ApiError("That Author could not be found.", 422, code="invalid_author")

        body_parts = [p for p in (nomination.achievements, nomination.why_significant, nomination.who_impacted) if p]
        article = Article(
            slug=generate_unique_slug(Article, nomination.nominee_name),
            title=nomination.nomination_summary or nomination.nominee_name,
            excerpt=nomination.nomination_summary,
            author_id=author.id,
            status="draft",
            content=[{"type": "paragraph", "text": p} for part in body_parts for p in part.split("\n\n") if p.strip()],
            series_id=nomination.series_id,
            source_nomination_id=nomination.id,
            created_by_id=current_user.id,
        )
        article.topics = list(nomination.topics)
        if nomination.person is not None:
            article.related_people = [nomination.person]
        if nomination.organization is not None:
            article.related_organizations = [nomination.organization]

        db.session.add(article)
        nomination.status = "in_editorial"
        db.session.commit()

        log_action(
            current_user, "nomination.converted_to_article", "nomination", nomination.id, {"article_id": article.id}
        )
        return success_response(
            {"nomination": nomination_schema.dump(nomination), "article": article_ref_schema.dump(article)}, status=201
        )


api.add_resource(NominationListResource, "")
api.add_resource(NominationDetailResource, "/<int:nomination_id>")
api.add_resource(NominationStatusResource, "/<int:nomination_id>/status")
api.add_resource(NominationAssignResource, "/<int:nomination_id>/assign")
api.add_resource(NominationNoteListResource, "/<int:nomination_id>/notes")
api.add_resource(NominationHistoryResource, "/<int:nomination_id>/history")
api.add_resource(NominationConvertToArticleResource, "/<int:nomination_id>/convert-to-article")
