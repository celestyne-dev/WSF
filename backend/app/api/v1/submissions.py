from datetime import datetime, timedelta, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.article import Article
from app.models.audit import AuditLog
from app.models.geography import Country
from app.models.media import Media
from app.models.people import Author, Organization, Person
from app.models.submissions import (
    StorySubmission,
    SubmissionMedia,
    SubmissionNote,
)
from app.models.taxonomy import Topic
from app.models.user import User
from app.schemas.submissions import (
    ArticleRefSchema,
    StorySubmissionInputSchema,
    StorySubmissionSchema,
    SubmissionAssignInputSchema,
    SubmissionConvertToArticleInputSchema,
    SubmissionListItemSchema,
    SubmissionNoteInputSchema,
    SubmissionStatusInputSchema,
    SubmissionUpdateSchema,
)
from app.schemas.media import MediaSchema
from app.services.audit import log_action
from app.services.newsletter import upsert_subscriber
from app.services.media import MediaService
from app.services.slugs import generate_unique_slug
from app.utils.filtering import apply_country_or_region_filter, apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

submissions_bp = Blueprint("submissions", __name__)
api = Api(submissions_bp)

submission_schema = StorySubmissionSchema()
submission_list_schema = SubmissionListItemSchema()
note_schema = SubmissionNoteInputSchema()
media_schema = MediaSchema()
article_ref_schema = ArticleRefSchema()

# Deliberately narrow: a submission may only move into these statuses
# through the manual review workflow. "converted"/"published" are never
# settable directly — see SubmissionStatusResource.
_MANUALLY_SETTABLE_STATUSES = (
    "submitted", "reviewing", "needs_information", "shortlisted", "approved",
    "declined", "withdrawn", "archived",
)

# A submission may only be hard-deleted while it's still an early, inert
# lead — never once it has editorial history, a link into Article, or has
# progressed past initial triage. Prefer Archive otherwise.
_DELETABLE_STATUSES = ("submitted", "reviewing", "declined", "withdrawn")


def _resolve_topics(slugs):
    if not slugs:
        return []
    return Topic.query.filter(Topic.slug.in_(slugs)).all()


def _find_recent_duplicate(email, title, body):
    """Prevent an accidental double submission from repeated button
    clicks — an identical title+body from the same email within a short
    window is treated as the same click, not a second legitimate story.
    Two different stories from the same woman are never blocked.
    """
    window_start = datetime.now(timezone.utc) - timedelta(minutes=5)
    return StorySubmission.query.filter(
        StorySubmission.email == email,
        StorySubmission.title == title,
        StorySubmission.body == body,
        StorySubmission.submitted_at >= window_start,
    ).first()


def _build_confirmation(submission):
    return {"reference": submission.reference}


class SubmissionListResource(Resource):
    @permission_required("submissions.manage")
    def get(self):
        query = StorySubmission.query.order_by(StorySubmission.submitted_at.desc())
        args = request.args
        query = apply_equality_filters(query, StorySubmission, args, ["status", "story_type", "series_id"])
        query = apply_country_or_region_filter(query, StorySubmission, args)
        if args.get("assigned_editor_id"):
            query = query.filter(StorySubmission.assigned_editor_id == args["assigned_editor_id"])
        if args.get("topic"):
            query = query.filter(StorySubmission.topics.any(Topic.slug == args["topic"]))
        query = apply_search(
            query, StorySubmission, args, ["reference", "title", "first_name", "last_name", "email", "subject_name"]
        )
        result = paginate(query, submission_list_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        """The public submission endpoint — write-only besides a small
        confirmation. Never returns the submission's id or any stored
        field back to the caller (see STORY SUBMISSION VS ARTICLE / SUCCESS
        CONFIRMATION in the task spec).
        """
        payload = request.get_json(silent=True) or {}
        data = StorySubmissionInputSchema().load(payload)

        if not db.session.get(Country, data["country_code"].upper()):
            raise ApiError("Please select a valid country.", 422, code="validation_error")

        email = data["email"].strip().lower()
        duplicate = _find_recent_duplicate(email, data["title"], data["body"])
        if duplicate is not None:
            return success_response(_build_confirmation(duplicate), status=201)

        topic_slugs = data.pop("topic_slugs", [])
        media_items = data.pop("media", [])
        newsletter_opt_in = data.pop("newsletter_opt_in", False)
        data["country_code"] = data["country_code"].upper()
        data["email"] = email

        submission = StorySubmission(**data, consent_recorded_at=datetime.now(timezone.utc))
        submission.topics = _resolve_topics(topic_slugs)
        db.session.add(submission)
        db.session.flush()

        submission.reference = f"WSF-STORY-{submission.submitted_at.year}-{submission.id:05d}"

        for item in media_items:
            media = db.session.get(Media, item["media_id"])
            if media is None:
                raise ApiError("One of the attached images could not be found.", 422, code="invalid_media")
            db.session.add(
                SubmissionMedia(
                    submission_id=submission.id,
                    media_id=media.id,
                    caption=item.get("caption"),
                    credit=item.get("credit"),
                    rights_confirmed=item["rights_confirmed"],
                )
            )

        db.session.commit()

        if newsletter_opt_in:
            upsert_subscriber(
                email,
                first_name=submission.first_name,
                last_name=submission.last_name,
                country_code=submission.country_code,
                placement="Story submission",
                acquisition=submission.acquisition,
            )

        log_action(None, "submission.received", "story_submission", submission.id, {"reference": submission.reference})
        return success_response(_build_confirmation(submission), status=201)


class SubmissionMediaUploadResource(Resource):
    """A narrow, public, image-only upload used solely to attach an
    optional photo to a story submission — reuses MediaService (the same
    validation/storage as the admin media library) rather than a second
    file-storage system, but is a separate endpoint from the admin
    MediaUploadResource: no permission is required, since a submitter is
    never authenticated, and the resulting Media row is not surfaced in
    the CMS media library listing until an editor deliberately reuses it.
    """

    def post(self):
        service = MediaService()
        media = service.save(
            request.files.get("file"),
            uploaded_by=None,
            caption=request.form.get("caption"),
            credit=request.form.get("credit"),
        )
        return success_response({"id": media.id, "publicUrl": media.public_url}, status=201)


class SubmissionDetailResource(Resource):
    @permission_required("submissions.manage")
    def get(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")
        submission.sync_published_state()
        db.session.commit()
        return success_response(submission_schema.dump(submission))

    @permission_required("submissions.manage")
    def patch(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = SubmissionUpdateSchema().load(request.get_json(silent=True) or {})
        topic_slugs = data.pop("topic_slugs", None)
        person_id = data.pop("person_id", "unset")
        organization_id = data.pop("organization_id", "unset")

        if person_id != "unset":
            if person_id is not None and db.session.get(Person, person_id) is None:
                raise ApiError("That Person profile could not be found.", 422, code="invalid_person")
            submission.person_id = person_id
        if organization_id != "unset":
            if organization_id is not None and db.session.get(Organization, organization_id) is None:
                raise ApiError("That Organization could not be found.", 422, code="invalid_organization")
            submission.organization_id = organization_id
        if topic_slugs is not None:
            submission.topics = _resolve_topics(topic_slugs)

        for key, value in data.items():
            setattr(submission, key, value)

        db.session.commit()
        log_action(current_user, "submission.updated", "story_submission", submission.id, data)
        return success_response(submission_schema.dump(submission))

    @permission_required("submissions.manage")
    def delete(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        if submission.status not in _DELETABLE_STATUSES or submission.notes or submission.resulting_article:
            raise ApiError(
                "This submission has editorial history and can't be deleted — archive it instead.",
                409,
                code="delete_restricted",
            )

        log_action(current_user, "submission.deleted", "story_submission", submission.id, {"reference": submission.reference})
        db.session.delete(submission)
        db.session.commit()
        return success_response({"deleted": True})


class SubmissionStatusResource(Resource):
    @permission_required("submissions.manage")
    def patch(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = SubmissionStatusInputSchema().load(request.get_json(silent=True) or {})
        new_status = data["status"]

        if new_status == "published":
            if not submission.resulting_article or submission.resulting_article.status != "published":
                raise ApiError(
                    "A submission can only be marked Published once its linked Article is actually published.",
                    422,
                    code="not_actually_published",
                )
        elif new_status == "converted" and not submission.resulting_article:
            raise ApiError(
                "A submission can only be marked Converted through the Article-draft handoff.",
                422,
                code="no_linked_article",
            )
        elif new_status not in _MANUALLY_SETTABLE_STATUSES and new_status not in ("converted", "published"):
            raise ApiError("That is not a valid status.", 422, code="validation_error")

        if submission.status == "submitted" and new_status != "submitted" and submission.reviewed_at is None:
            submission.reviewed_at = datetime.now(timezone.utc)

        submission.status = new_status
        db.session.commit()
        log_action(current_user, "submission.status_changed", "story_submission", submission.id, {"status": new_status})
        return success_response(submission_schema.dump(submission))


class SubmissionAssignResource(Resource):
    @permission_required("submissions.manage")
    def post(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = SubmissionAssignInputSchema().load(request.get_json(silent=True) or {})
        editor_id = data["editor_id"]
        if editor_id is not None and db.session.get(User, editor_id) is None:
            raise ApiError("That editor could not be found.", 422, code="invalid_editor")

        submission.assigned_editor_id = editor_id
        db.session.commit()
        log_action(current_user, "submission.editor_assigned", "story_submission", submission.id, {"editor_id": editor_id})
        return success_response(submission_schema.dump(submission))


class SubmissionNoteListResource(Resource):
    @permission_required("submissions.manage")
    def post(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = note_schema.load(request.get_json(silent=True) or {})
        note = SubmissionNote(submission_id=submission.id, user_id=current_user.id, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "submission.note_added", "story_submission", submission.id)
        return success_response(submission_schema.dump(submission), status=201)


class SubmissionHistoryResource(Resource):
    @permission_required("submissions.manage")
    def get(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        entries = (
            AuditLog.query.filter_by(entity_type="story_submission", entity_id=str(submission_id))
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


class SubmissionConvertToArticleResource(Resource):
    """The deliberate, controlled "Create Article Draft" handoff. Never
    reachable except by an editor with submissions.manage — and never
    publishes anything; the resulting Article is always created as a
    draft.
    """

    @permission_required("submissions.manage")
    def post(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        if submission.status != "approved":
            raise ApiError(
                "Only an Approved submission can be converted into an Article draft.", 409, code="not_approved"
            )
        if submission.resulting_article is not None:
            raise ApiError("This submission already has a linked Article.", 409, code="already_converted")

        data = SubmissionConvertToArticleInputSchema().load(request.get_json(silent=True) or {})
        author = db.session.get(Author, data["author_id"])
        if author is None:
            raise ApiError("That Author could not be found.", 422, code="invalid_author")

        article = Article(
            slug=generate_unique_slug(Article, submission.title),
            title=submission.title,
            excerpt=submission.summary,
            author_id=author.id,
            status="draft",
            content=[{"type": "paragraph", "text": p} for p in submission.body.split("\n\n") if p.strip()],
            series_id=submission.series_id,
            ai_involvement=submission.ai_involvement,
            source_submission_id=submission.id,
            created_by_id=current_user.id,
        )
        article.topics = list(submission.topics)
        if submission.person is not None:
            article.related_people = [submission.person]
        if submission.organization is not None:
            article.related_organizations = [submission.organization]
        if data["include_media"] and submission.media_items:
            first = submission.media_items[0]
            article.hero_media_id = first.media_id
            article.hero_image_caption = first.caption
            article.hero_image_credit = first.credit

        db.session.add(article)
        submission.status = "converted"
        db.session.commit()

        log_action(
            current_user, "submission.converted_to_article", "story_submission", submission.id, {"article_id": article.id}
        )
        return success_response(
            {"submission": submission_schema.dump(submission), "article": article_ref_schema.dump(article)}, status=201
        )


api.add_resource(SubmissionListResource, "")
api.add_resource(SubmissionMediaUploadResource, "/media")
api.add_resource(SubmissionDetailResource, "/<int:submission_id>")
api.add_resource(SubmissionStatusResource, "/<int:submission_id>/status")
api.add_resource(SubmissionAssignResource, "/<int:submission_id>/assign")
api.add_resource(SubmissionNoteListResource, "/<int:submission_id>/notes")
api.add_resource(SubmissionHistoryResource, "/<int:submission_id>/history")
api.add_resource(SubmissionConvertToArticleResource, "/<int:submission_id>/convert-to-article")
