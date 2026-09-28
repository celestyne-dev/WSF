from datetime import datetime, timezone

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.extensions import db
from app.models.article import Article, ArticleRevision, Redirect
from app.models.people import Author, Organization, Person
from app.models.taxonomy import Category, Series, Tag, Topic
from app.schemas.article import (
    ArticleInputSchema,
    ArticleRejectInputSchema,
    ArticleScheduleInputSchema,
    ArticleSchema,
    admin_article_summary_schema,
    article_summary_schema,
    public_article_schema,
)
from app.services import articles_workflow
from app.services.audit import log_action
from app.services.notifications import notify_article_approved, notify_article_review_requested
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import create_redirect_for_slug_change, generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response
from app.utils.slugs import slugify

articles_bp = Blueprint("articles", __name__)
api = Api(articles_bp)

article_schema = ArticleSchema()
public_article_schema_instance = public_article_schema()

# An article may only be *created* as a draft, or (for a user with publish
# authority) created already published — every other status in
# ARTICLE_STATUSES is reachable only by walking the workflow afterwards via
# the dedicated action endpoints below (submit-review, approve, schedule,
# ...). This keeps "create" simple while still letting an existing
# integration/superadmin publish something immediately.
_CREATABLE_STATUSES = ("draft", "published")


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


def _require_manage_or_publish():
    """The stronger permission tier for editorial authority actions
    (approve, schedule/reschedule/unschedule, publish, archive, request
    changes) — see PUBLISH_GATED_TRANSITIONS in
    app/services/articles_workflow.py. Deliberately not satisfied by
    articles.edit_own alone: an author who owns a draft can submit it for
    review, but reviewing/approving/publishing is an editor/admin action.
    """
    user = _require_active_user()
    if not user.has_permission("articles.manage", "articles.publish"):
        raise ApiError("You do not have permission to perform this action.", 403, code="forbidden")
    return user


def _get_article_or_404(slug):
    article = Article.query.filter_by(slug=slug).first()
    if article is None:
        raise ApiError("Article not found.", 404, code="not_found")
    return article


def _perform_transition(article, to_status, user, action_name, audit_changes=None, note=None):
    """Shared body for every workflow action endpoint below: validates the
    transition against app/services/articles_workflow.py's rules, saves a
    revision snapshot (existing mechanism — see _snapshot above), and
    writes one Audit Log entry with safe, small metadata (never a full
    Article body — see app/services/audit.py's own redaction note, which
    this doesn't need to rely on since nothing sensitive is ever passed).
    A no-op call (to_status == article.status) is allowed by
    is_valid_transition() but produces no revision/audit entry — nothing
    actually changed.
    """
    from_status = article.status
    if not articles_workflow.is_valid_transition(from_status, to_status):
        raise ApiError(
            f'Cannot move this article from "{from_status}" to "{to_status}".',
            409,
            code="invalid_transition",
        )
    if from_status == to_status:
        return success_response(article_schema.dump(article))

    article.status = to_status
    db.session.flush()
    articles_workflow.snapshot(article, user, note=note)
    db.session.commit()

    changes = {"from_status": from_status, "to_status": to_status}
    if audit_changes:
        changes.update(audit_changes)
    log_action(user, action_name, "Article", article.id, changes)

    # Notification hooks — see app/services/notifications.py. Placed after
    # the transition's own commit so a notification issue can never lose
    # the actual workflow change (see that module's own docstring on
    # failure handling).
    if to_status == "in_review":
        notify_article_review_requested(article, requested_by=user)
    elif to_status == "approved":
        notify_article_approved(article, approved_by=user)

    return success_response(article_schema.dump(article))


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
    # status is deliberately NOT set here — see ArticleListResource.post()
    # (initial status, gated) and ArticleDetailResource.put() (status is
    # immutable via ordinary save; see the dedicated workflow action
    # endpoints below for every real transition).
    article.seo = data.get("seo")
    article.content = sanitize_content_blocks(data.get("content", []))
    article.ai_involvement = data.get("ai_involvement", "none")
    article.human_reviewed = data.get("human_reviewed", False)
    article.ai_disclosure_required = data.get("ai_disclosure_required", False)
    article.ai_disclosure_text = data.get("ai_disclosure_text")
    article.ai_editorial_notes = data.get("ai_editorial_notes")


def _validate_for_publish(article):
    """Enforced whenever an article's effective status is (becoming)
    "published" — a draft may stay incomplete indefinitely, but publishing
    requires a real body and, if AI was involved, a confirmed human review.
    Title/slug/author are already guaranteed non-empty by ArticleInputSchema
    and _resolve_relations before this runs.
    """
    errors = []
    if not article.content:
        errors.append("Article body is required before publishing.")
    if article.ai_involvement != "none" and not article.human_reviewed:
        errors.append(
            "This article is marked as AI-assisted or AI-generated and must be confirmed as human-reviewed "
            "before it can be published."
        )
    if errors:
        raise ApiError(errors[0], 422, code="publish_validation_failed", errors=errors)


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
        if request.args.get("person"):
            query = query.filter(Article.related_people.any(slug=request.args["person"]))
        if request.args.get("organization"):
            query = query.filter(Article.related_organizations.any(slug=request.args["organization"]))
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

        requested_status = data.get("status", "draft")
        if requested_status not in _CREATABLE_STATUSES:
            raise ApiError(
                f'A new article must be created as "draft" or "published" — use the workflow action endpoints '
                f'to move it to "{requested_status}" afterwards.',
                422,
                code="invalid_status",
            )
        if requested_status == "published" and not user.has_permission("articles.manage", "articles.publish"):
            raise ApiError("You do not have permission to publish articles.", 403, code="forbidden")

        _apply_fields(article, data, relations)
        article.status = requested_status
        if article.status == "published":
            _validate_for_publish(article)
        db.session.add(article)
        db.session.flush()
        _snapshot(article, user, note="Created")
        db.session.commit()

        log_action(user, "article.create", "Article", article.id)
        return success_response(article_schema.dump(article), status=201)


class ArticleDetailResource(Resource):
    def get(self, slug):
        article = Article.query.filter_by(slug=slug).first()
        if article is None and slug.isdigit():
            # Admin Notifications addresses articles by numeric id (see
            # app/services/notifications.py), not slug — this fallback lets
            # the notification's click-through route resolve without
            # requiring the frontend to know the article's slug up front.
            article = db.session.get(Article, int(slug))
        if article is not None:
            # An editor with permission to edit THIS article sees the full
            # schema (including ai_editorial_notes, needed to pre-fill the
            # CMS form when reopening a draft) — this is the same endpoint
            # the admin editor uses to load an article, real or unpublished.
            # Anyone else gets the public schema, and an unpublished article
            # 404s exactly like a nonexistent slug rather than leaking via a
            # 401/403 that it exists.
            can_edit = False
            try:
                _can_edit(article)
                can_edit = True
            except Exception:
                can_edit = False

            if article.status != "published" and not can_edit:
                raise ApiError("Article not found.", 404, code="not_found")

            schema = article_schema if can_edit else public_article_schema_instance
            return success_response(schema.dump(article))

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

        requested_status = data.get("status", "draft")
        if requested_status != article.status:
            raise ApiError(
                f'Cannot change status via an ordinary save (attempted "{article.status}" -> '
                f'"{requested_status}"). Use the dedicated workflow action endpoints '
                f"(submit-review, approve, schedule, publish, archive, ...) instead.",
                409,
                code="invalid_transition",
            )

        old_slug = article.slug
        if data.get("slug") and data["slug"] != old_slug:
            article.slug = validate_explicit_slug(Article, data["slug"], current_id=article.id)

        _apply_fields(article, data, relations)
        if article.status == "published":
            _validate_for_publish(article)
        db.session.flush()
        _snapshot(article, user, note="Updated")

        if article.slug != old_slug:
            create_redirect_for_slug_change(article, old_slug, article.slug)

        db.session.commit()
        log_action(user, "article.update", "Article", article.id)
        return success_response(article_schema.dump(article))


class ArticleSubmitReviewResource(Resource):
    """draft|changes_requested -> in_review. Never publishes anything — the
    author/owner-editor moving their own work into the review queue, so
    this uses the weaker _can_edit() check (see PUBLISH_GATED_TRANSITIONS,
    which deliberately excludes this transition).
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _can_edit(article)
        return _perform_transition(article, "in_review", user, "article.submit_review")


class ArticleRequestChangesResource(Resource):
    """in_review -> changes_requested. A reviewer/editor action, not the
    author's — gated by the stronger manage/publish tier. The optional
    note is recorded only in the Audit Log entry (see
    ArticleRejectInputSchema's own docstring for why no new column/
    comment-thread system was added for this).
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()
        data = ArticleRejectInputSchema().load(request.get_json(silent=True) or {})
        return _perform_transition(
            article,
            "changes_requested",
            user,
            "article.request_changes",
            audit_changes={"note": data.get("note")} if data.get("note") else None,
        )


class ArticleMoveToDraftResource(Resource):
    """changes_requested -> draft — the literal "return to draft" step the
    spec asks for (see WORKFLOW_TRANSITIONS's own comment on why this is a
    second hop rather than a direct in_review -> draft transition). Owner-
    level access is enough, same reasoning as submit-review.
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _can_edit(article)
        return _perform_transition(article, "draft", user, "article.move_to_draft")


class ArticleApproveResource(Resource):
    """in_review -> approved. Records approved_at/approved_by_user_id.
    Approval does NOT make the article public — see Article model's own
    comment on approved_at/approved_by, and articles_workflow.py's
    docstring on why editing an approved article afterwards doesn't clear
    these or force re-approval.
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()
        if not articles_workflow.is_valid_transition(article.status, "approved"):
            raise ApiError(
                f'Cannot approve an article from "{article.status}".', 409, code="invalid_transition"
            )
        article.approved_at = datetime.now(timezone.utc)
        article.approved_by_user_id = user.id
        return _perform_transition(article, "approved", user, "article.approve")


class ArticleScheduleResource(Resource):
    """approved -> scheduled. Stores scheduled_at as the future UTC
    publication timestamp; validated by articles_workflow.
    validate_schedule_datetime (timezone-aware, strictly in the future —
    see that function's own docstring for why naive datetimes are
    rejected rather than guessed at).
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()
        # Deliberately requires "approved" exactly, rather than letting
        # is_valid_transition's same-status short-circuit treat
        # scheduled -> scheduled as a free no-op here — that would skip
        # _perform_transition's commit and silently drop the new
        # scheduled_at. Re-scheduling an already-scheduled article goes
        # through ArticleRescheduleResource below instead.
        if article.status != "approved":
            raise ApiError(
                f'Cannot schedule an article from "{article.status}". It must be "approved" first.',
                409,
                code="invalid_transition",
            )
        data = ArticleScheduleInputSchema().load(request.get_json(silent=True) or {})
        try:
            scheduled_at = articles_workflow.validate_schedule_datetime(data["scheduled_at"])
        except ValueError as exc:
            raise ApiError(str(exc), 422, code="invalid_schedule")
        article.scheduled_at = scheduled_at
        return _perform_transition(
            article, "scheduled", user, "article.schedule", audit_changes={"scheduled_at": scheduled_at.isoformat()}
        )


class ArticleRescheduleResource(Resource):
    """scheduled -> scheduled, with a new scheduled_at. A distinct endpoint
    from Schedule (which only accepts approved -> scheduled) for a clearer
    audit trail/action name. Implemented directly rather than via
    _perform_transition, since that helper's no-op short-circuit
    (from_status == to_status) would skip the commit entirely here — and
    a reschedule always has a real field change worth persisting/logging.
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()
        if article.status != "scheduled":
            raise ApiError('Only a "scheduled" article can be rescheduled.', 409, code="invalid_transition")
        data = ArticleScheduleInputSchema().load(request.get_json(silent=True) or {})
        try:
            scheduled_at = articles_workflow.validate_schedule_datetime(data["scheduled_at"])
        except ValueError as exc:
            raise ApiError(str(exc), 422, code="invalid_schedule")

        previous = article.scheduled_at
        article.scheduled_at = scheduled_at
        db.session.flush()
        articles_workflow.snapshot(article, user, note="Rescheduled")
        db.session.commit()
        log_action(
            user,
            "article.reschedule",
            "Article",
            article.id,
            {
                "from_status": "scheduled",
                "to_status": "scheduled",
                "previous_scheduled_at": previous.isoformat() if previous else None,
                "scheduled_at": scheduled_at.isoformat(),
            },
        )
        return success_response(article_schema.dump(article))


class ArticleUnscheduleResource(Resource):
    """scheduled -> approved. Clears scheduled_at so no stale scheduling
    metadata is left controlling publication eligibility (see
    publish_due_articles()'s own re-check under lock, which would already
    catch this, but clearing it here keeps the row itself unambiguous).
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()
        if not articles_workflow.is_valid_transition(article.status, "approved"):
            raise ApiError(
                f'Cannot unschedule an article from "{article.status}".', 409, code="invalid_transition"
            )
        article.scheduled_at = None
        return _perform_transition(article, "approved", user, "article.unschedule")


class ArticlePublishResource(Resource):
    """approved|scheduled -> published ("Publish now"). Idempotent: calling
    this on an already-published article is a no-op success (see spec:
    "publishing already-published -> no duplicate transition"), never a
    409 — a client retrying a slow request shouldn't see an error for a
    publish that already succeeded. publish_date is always set to *now*
    here (manual publish) — the scheduler (publish_due_articles) is the
    only path that back-dates it to the original scheduled_at; see that
    function's own docstring for that split.
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()

        if article.status == "published":
            return success_response(article_schema.dump(article))

        if not articles_workflow.is_valid_transition(article.status, "published"):
            raise ApiError(
                f'Cannot publish an article from "{article.status}". It must be "approved" or "scheduled" first.',
                409,
                code="invalid_transition",
            )

        from_status = article.status
        _validate_for_publish(article)
        article.status = "published"
        article.publish_date = datetime.now(timezone.utc)
        db.session.flush()
        _snapshot(article, user, note="Published")
        db.session.commit()

        log_action(user, "article.publish", "Article", article.id, {"from_status": from_status, "to_status": "published"})
        return success_response(article_schema.dump(article))


class ArticleArchiveResource(Resource):
    """published -> archived. Removes the article from public eligibility
    (every public query already filters on status == "published" — see
    the audit in app/services/search.py, api/v1/taxonomy.py, api/v1/
    authors.py, and ArticleRelatedResource below) without deleting the DB
    record, its revisions, or its Audit Log history. Terminal in this
    task — no restore/republish action; see the final report for why.
    """

    def post(self, slug):
        article = _get_article_or_404(slug)
        user = _require_manage_or_publish()
        return _perform_transition(article, "archived", user, "article.archive")


class ArticleCalendarResource(Resource):
    """Bounded date-range feed for the Editorial Calendar — GET
    /articles/calendar?start=ISO&end=ISO. Never loads every article: start
    and end are required, and results are capped. An article appears if
    its scheduled_at OR publish_date falls in [start, end). Same own-vs-
    all visibility split as AdminArticleListResource in api/v1/admin.py —
    a user with only articles.edit_own sees just their own work.
    """

    def get(self):
        user = _require_active_user()
        if not user.has_permission("articles.create", "articles.edit_own", "articles.manage", "articles.publish"):
            raise ApiError("You do not have permission to view the editorial calendar.", 403, code="forbidden")

        start_raw = request.args.get("start")
        end_raw = request.args.get("end")
        if not start_raw or not end_raw:
            raise ApiError("start and end query parameters are required.", 422, code="validation_error")
        try:
            start = datetime.fromisoformat(start_raw.replace("Z", "+00:00"))
            end = datetime.fromisoformat(end_raw.replace("Z", "+00:00"))
        except ValueError:
            raise ApiError("start and end must be ISO-8601 dates.", 422, code="validation_error")
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end <= start:
            raise ApiError("end must be after start.", 422, code="validation_error")

        query = Article.query.filter(
            db.or_(
                db.and_(Article.scheduled_at.isnot(None), Article.scheduled_at >= start, Article.scheduled_at < end),
                db.and_(Article.publish_date.isnot(None), Article.publish_date >= start, Article.publish_date < end),
            )
        )
        if not user.has_permission("articles.manage"):
            query = query.filter(
                db.or_(Article.created_by_id == user.id, Article.author.has(user_id=user.id))
            )
        if request.args.get("status"):
            query = query.filter(Article.status == request.args["status"])
        if request.args.get("author"):
            query = query.join(Author).filter(Author.slug == request.args["author"])
        if request.args.get("topic"):
            query = query.filter(Article.topics.any(slug=request.args["topic"]))
        if request.args.get("series"):
            query = query.join(Series).filter(Series.slug == request.args["series"])
        query = query.order_by(db.func.coalesce(Article.scheduled_at, Article.publish_date)).limit(500)

        return success_response(admin_article_summary_schema(many=True).dump(query.all()))


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
api.add_resource(ArticleCalendarResource, "/calendar")
api.add_resource(ArticleDetailResource, "/<string:slug>")
api.add_resource(ArticlePublishResource, "/<string:slug>/publish")
api.add_resource(ArticleRevisionsResource, "/<string:slug>/revisions")
api.add_resource(ArticleSubmitReviewResource, "/<string:slug>/submit-review")
api.add_resource(ArticleRequestChangesResource, "/<string:slug>/request-changes")
api.add_resource(ArticleMoveToDraftResource, "/<string:slug>/move-to-draft")
api.add_resource(ArticleApproveResource, "/<string:slug>/approve")
api.add_resource(ArticleScheduleResource, "/<string:slug>/schedule")
api.add_resource(ArticleRescheduleResource, "/<string:slug>/reschedule")
api.add_resource(ArticleUnscheduleResource, "/<string:slug>/unschedule")
api.add_resource(ArticleArchiveResource, "/<string:slug>/archive")
