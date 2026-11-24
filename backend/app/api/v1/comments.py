"""Article comments API (Step 13). Rules: app/services/comments.py.

Public (/api/v1/comments):
  GET    /article/<slug>                 thread + whether it's open (+ the signed-in
                                         viewer's own pending comments and restriction)
  GET    /article/<slug>/form            signed form token (signed in)
  POST   /article/<slug>                 {body, parentId?, formToken, website(honeypot)}
  PATCH  /<id>                           {body}  own comment, within 15 minutes
  DELETE /<id>                           own comment
  POST   /<id>/report                    {reason, details?}
  GET    /notifications                  {replyEmails}
  PUT    /notifications                  {replyEmails}
  POST   /notifications/unsubscribe      {token}  works signed out
Moderation (/api/v1/admin/comments, permission "comments.moderate"):
  GET    ?queue=pending|reported|hidden|removed|published|all&page=
  GET    /<id>                           comment + reports + history
  POST   /<id>/approve | /<id>/hide {reason?} | /<id>/remove {reason}
  POST   /users/<user_id>/restrict       {kind: suspension|ban, days?, reason}
  POST   /users/<user_id>/lift
Every mutation checks ownership/permission here, never in the UI.
"""
from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import active_user_required, permission_required
from app.extensions import db, limiter
from app.models.article import Article
from app.models.comment import Comment, CommentReport
from app.models.user import User
from app.services import comments as svc
from app.services.comment_settings import get_comment_settings
from app.services.rate_limits import limit
from app.utils.responses import ApiError, success_response

comments_bp = Blueprint("comments", __name__)
api = Api(comments_bp)
admin_comments_bp = Blueprint("admin_comments", __name__)
admin_api = Api(admin_comments_bp)

MODERATE = "comments.moderate"


def _per_account_key():
    """Rate-limit key: the signed-in account (so people sharing an office
    or mobile network don't share a budget), else the client address."""
    from flask_limiter.util import get_remote_address

    try:
        verify_jwt_in_request(optional=True)
        if current_user:
            return f"user:{current_user.id}"
    except Exception:  # an invalid token is rejected by the view itself
        pass
    return get_remote_address()


def _body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _fail(exc):
    raise ApiError(str(exc), exc.status, code=exc.code)


def _article(slug):
    article = Article.query.filter_by(slug=slug, status="published").first()
    if article is None:
        raise ApiError("Article not found.", 404, code="not_found")
    return article


def _comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if comment is None:
        raise ApiError("Comment not found.", 404, code="not_found")
    return comment


def _viewer():
    """The signed-in viewer, or None. A missing token is fine (public read);
    an expired/invalid one is a 401 so the browser refreshes and retries."""
    verify_jwt_in_request(optional=True)
    user = current_user if current_user else None
    return user if user is not None and user.is_active else None


def _viewer_payload(user):
    if user is None:
        return None
    settings = get_comment_settings()
    return {
        "restriction": svc.restriction_payload(svc.active_restriction(user.id)),
        "replyEmails": svc.wants_reply_emails(user),
        "replyNotificationsAvailable": settings["replyNotificationsEnabled"],
        "mustChangePassword": bool(user.must_change_password),
    }


class ArticleCommentsResource(Resource):
    def get(self, slug):
        article = _article(slug)
        viewer = _viewer()
        thread = svc.public_thread(article, viewer)
        return success_response({**thread, **svc.comment_state(article), "viewer": _viewer_payload(viewer)})

    @active_user_required
    @limiter.limit(limit("comment_create"), key_func=_per_account_key)
    def post(self, slug):
        article = _article(slug)
        data = _body()
        parent_id = data.get("parentId")
        try:
            comment = svc.create_comment(
                current_user, article, data.get("body"), parent_id=parent_id,
                form_token=data.get("formToken"), honeypot=data.get("website"), raw_ip=request.remote_addr)
        except svc.CommentError as exc:
            _fail(exc)
        message = ("Thanks! Your comment is published." if comment.status == "published"
                   else "Thanks! Your comment will appear once a moderator approves it.")
        return success_response({"id": comment.id, "status": comment.status}, status=201, message=message)


class CommentFormResource(Resource):
    @active_user_required
    @limiter.limit("60 per minute", key_func=_per_account_key)
    def get(self, slug):
        article = _article(slug)
        return success_response({"formToken": svc.issue_form_token(current_user, article),
                                 "minSubmitSeconds": get_comment_settings()["minSubmitSeconds"]})


class CommentResource(Resource):
    @active_user_required
    @limiter.limit(limit("comment_edit"), key_func=_per_account_key)
    def patch(self, comment_id):
        comment = _comment(comment_id)
        try:
            comment = svc.edit_comment(current_user, comment, _body().get("body"))
        except svc.CommentError as exc:
            _fail(exc)
        return success_response({"id": comment.id, "status": comment.status, "body": comment.body,
                                 "edited": comment.edited_at is not None})

    @active_user_required
    @limiter.limit(limit("comment_edit"), key_func=_per_account_key)
    def delete(self, comment_id):
        comment = _comment(comment_id)
        try:
            svc.delete_comment(current_user, comment)
        except svc.CommentError as exc:
            _fail(exc)
        return success_response({"id": comment.id, "status": "deleted"}, message="Your comment was deleted.")


class CommentReportResource(Resource):
    @active_user_required
    @limiter.limit(limit("comment_report"), key_func=_per_account_key)
    def post(self, comment_id):
        comment = _comment(comment_id)
        data = _body()
        try:
            svc.report_comment(current_user, comment, data.get("reason"), data.get("details"))
        except svc.CommentError as exc:
            _fail(exc)
        # Never tells the reporter whether the comment was hidden.
        return success_response(None, message="Thanks for letting us know. A moderator will take a look.")


class CommentNotificationsResource(Resource):
    @active_user_required
    def get(self):
        return success_response({"replyEmails": svc.wants_reply_emails(current_user),
                                 "available": get_comment_settings()["replyNotificationsEnabled"]})

    @active_user_required
    @limiter.limit(limit("comment_edit"), key_func=_per_account_key)
    def put(self):
        value = _body().get("replyEmails")
        if not isinstance(value, bool):
            raise ApiError("replyEmails must be true or false.", 422, code="validation_error")
        if value and not get_comment_settings()["replyNotificationsEnabled"]:
            raise ApiError("Reply emails aren't available right now.", 409, code="reply_notifications_off")
        return success_response({"replyEmails": svc.set_reply_emails(current_user, value)})


class CommentUnsubscribeResource(Resource):
    @limiter.limit(limit("newsletter_unsubscribe_link"))
    def post(self):
        if not svc.unsubscribe_by_token(_body().get("token")):
            raise ApiError("This unsubscribe link isn't valid.", 404, code="not_found")
        return success_response(None, message="You won't get emails about replies to your comments any more.")


api.add_resource(ArticleCommentsResource, "/article/<string:slug>")
api.add_resource(CommentFormResource, "/article/<string:slug>/form")
api.add_resource(CommentResource, "/<int:comment_id>")
api.add_resource(CommentReportResource, "/<int:comment_id>/report")
api.add_resource(CommentNotificationsResource, "/notifications")
api.add_resource(CommentUnsubscribeResource, "/notifications/unsubscribe")


# --- moderation --------------------------------------------------------------------------------

QUEUES = ("pending", "reported", "hidden", "removed", "published", "all")
PAGE_SIZE = 25


class AdminCommentListResource(Resource):
    @permission_required(MODERATE)
    def get(self):
        queue = request.args.get("queue", "pending")
        if queue not in QUEUES:
            raise ApiError("Unknown queue.", 422, code="validation_error")
        try:
            page = max(1, int(request.args.get("page", 1)))
        except ValueError:
            page = 1
        query = Comment.query
        if queue == "reported":
            query = query.filter(Comment.id.in_(db.session.query(CommentReport.comment_id)),
                                 Comment.status.in_(("published", "hidden")))
        elif queue != "all":
            query = query.filter(Comment.status == queue)
        total = query.count()
        rows = (query.order_by(Comment.created_at.desc(), Comment.id.desc())
                .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all())
        counts = {q: Comment.query.filter(Comment.status == q).count() for q in ("pending", "hidden")}
        counts["reported"] = (Comment.query.filter(Comment.id.in_(db.session.query(CommentReport.comment_id)),
                                                   Comment.status.in_(("published", "hidden"))).count())
        # A plain object (not a list + meta): the queue counts travel with it.
        return success_response({"items": [svc.moderator_item(c) for c in rows], "counts": counts,
                                 "page": page, "pageSize": PAGE_SIZE, "total": total,
                                 "totalPages": max(1, -(-total // PAGE_SIZE))})


class AdminCommentDetailResource(Resource):
    @permission_required(MODERATE)
    def get(self, comment_id):
        comment = _comment(comment_id)
        return success_response({**svc.moderator_item(comment), "reports": svc.moderator_reports(comment),
                                 "history": svc.moderator_history(comment)})


def _action(name):
    class _Action(Resource):
        @permission_required(MODERATE)
        def post(self, comment_id):
            comment = _comment(comment_id)
            data = _body()
            try:
                if name == "approve":
                    svc.approve_comment(current_user, comment)
                elif name == "hide":
                    svc.hide_comment(current_user, comment, data.get("reason"))
                else:
                    svc.remove_comment(current_user, comment, data.get("reason"))
            except svc.CommentError as exc:
                _fail(exc)
            return success_response(svc.moderator_item(comment))

    _Action.__name__ = f"AdminComment{name.title()}Resource"
    return _Action


def _member(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        raise ApiError("Member not found.", 404, code="not_found")
    return user


class AdminCommentRestrictResource(Resource):
    @permission_required(MODERATE)
    def post(self, user_id):
        user = _member(user_id)
        data = _body()
        try:
            row = svc.restrict_user(current_user, user, data.get("kind"), data.get("reason"), data.get("days"))
        except svc.CommentError as exc:
            _fail(exc)
        return success_response({"restriction": svc.restriction_payload(row)})


class AdminCommentLiftResource(Resource):
    @permission_required(MODERATE)
    def post(self, user_id):
        user = _member(user_id)
        try:
            svc.lift_restriction(current_user, user)
        except svc.CommentError as exc:
            _fail(exc)
        return success_response({"restriction": None})


admin_api.add_resource(AdminCommentListResource, "/comments")
admin_api.add_resource(AdminCommentDetailResource, "/comments/<int:comment_id>")
for _name in ("approve", "hide", "remove"):
    admin_api.add_resource(_action(_name), f"/comments/<int:comment_id>/{_name}", endpoint=f"comment_{_name}")
admin_api.add_resource(AdminCommentRestrictResource, "/comments/users/<int:user_id>/restrict")
admin_api.add_resource(AdminCommentLiftResource, "/comments/users/<int:user_id>/lift")
