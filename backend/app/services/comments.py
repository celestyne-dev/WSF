"""First-party article comments (Step 13): the rules. Tables and the
status lifecycle are in app/models/comment.py; HTTP in app/api/v1/comments.py.

Who: signed-in, active WSF accounts only. Reading is public.
Depth: top-level comments and ONE level of replies. Replying to a reply
  attaches the new comment to that reply's top-level comment.
Publication (decide_status):
  held ("pending") when ANY of
    * the author is not yet trusted: fewer published comments than the
      Studio trustedThreshold (so a first comment is always held);
    * more than MAX_LINKS (2) links (count_links);
    * a Studio blocked word/phrase matches (blocked_word_hits);
  otherwise published at once. The link and blocked-word rules apply to
  trusted members too, and again on every edit.
Spam controls (no third-party CAPTCHA): sign-in required; a honeypot field
  that must stay empty; a signed form token whose server-side issue time
  must be at least minSubmitSeconds old (the client can't forge it); the
  shared Redis/PostgreSQL rate limits (app/services/rate_limits.py
  comment_*); and the same member posting the same text twice within
  DUPLICATE_WINDOW is refused.
Editing: the author only, within EDIT_WINDOW of creation (server time);
  sets edited_at; history keeps the event, not the old text.
Deleting: the author, any time. The body is erased; while published
  replies exist the public thread shows "Comment deleted" in its place.
Reports: one per account per comment; not your own; only published
  comments. Reaching the Studio reportHideThreshold unique reports hides
  the comment automatically (once) and records an "auto_hidden" event.
Restrictions: a comment suspension (until a date) or ban (until lifted)
  blocks posting, replying, editing and reporting; it never deactivates the
  account and never touches existing comments.
IP: only HMAC-SHA256(key, normalized client IP) is stored, for abuse
  review, and cleared after IP_HASH_RETENTION (purge_expired_ip_hashes).
"""
import hashlib
import hmac
import ipaddress
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import func

from app.extensions import db
from app.models.comment import (
    REPORT_REASONS,
    Comment,
    CommentEvent,
    CommentNotificationPreference,
    CommentReport,
    CommentRestriction,
)
from app.services.comment_settings import get_comment_settings

EDIT_WINDOW = timedelta(minutes=15)
MAX_BODY_LENGTH = 5000
MAX_REPORT_DETAILS = 500
MAX_LINKS = 2
IP_HASH_RETENTION = timedelta(days=90)
FORM_TOKEN_MAX_AGE = 6 * 60 * 60  # seconds: a form left open longer must be reloaded
DUPLICATE_WINDOW = timedelta(hours=24)
DELETED_PLACEHOLDER = "Comment deleted"
REMOVED_PLACEHOLDER = "Comment removed"
FORMER_MEMBER = "Former member"
_FORM_SALT = "wsf-comment-form-v1"
_IP_KEY_CONTEXT = b"wsf-comment-ip-hash-v1"


class CommentError(Exception):
    def __init__(self, message, status=400, code="comment_error"):
        super().__init__(message)
        self.status = status
        self.code = code


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def _event(action, comment=None, actor=None, subject_user_id=None, reason=None, meta=None):
    db.session.add(CommentEvent(
        comment_id=comment.id if comment is not None else None,
        subject_user_id=subject_user_id if subject_user_id is not None else (comment.user_id if comment else None),
        actor_id=actor.id if actor is not None else None,
        action=action, reason=reason, meta=meta,
    ))


# --- IP hash -----------------------------------------------------------------------------------


def _ip_key():
    """COMMENT_IP_HASH_KEY when set, otherwise a sub-key derived from
    SECRET_KEY (never the SECRET_KEY itself). Changing either makes old
    hashes unmatchable, which only shortens their usefulness."""
    configured = current_app.config.get("COMMENT_IP_HASH_KEY")
    if configured:
        return configured.encode("utf-8")
    return hmac.new(current_app.config["SECRET_KEY"].encode("utf-8"), _IP_KEY_CONTEXT, hashlib.sha256).digest()


def normalize_ip(raw):
    """The client IP as resolved by ProxyFix (request.remote_addr), in one
    canonical text form; IPv4-mapped IPv6 becomes plain IPv4. None if absent
    or unparseable."""
    if not raw:
        return None
    try:
        address = ipaddress.ip_address(str(raw).strip())
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
        address = address.ipv4_mapped
    return address.compressed


def hash_ip(raw):
    ip = normalize_ip(raw)
    if ip is None:
        return None
    return hmac.new(_ip_key(), ip.encode("ascii"), hashlib.sha256).hexdigest()


def purge_expired_ip_hashes(now=None):
    """Clears every comment IP hash whose 90 days are up. Idempotent: safe to
    run as often as you like. Returns how many rows were cleared."""
    now = now or _now()
    count = (Comment.query.filter(Comment.ip_hash_expires_at.isnot(None), Comment.ip_hash_expires_at <= now)
             .update({"ip_hash": None, "ip_hash_expires_at": None}, synchronize_session=False))
    db.session.commit()
    return count


# --- content checks ----------------------------------------------------------------------------

# A link is an http(s):// or www. address, or a bare domain with a common
# top-level domain (example.com, example.co.ke/path). Words like "e.g.",
# "Node.js" or "3.5" are not links; the text "http" on its own is not a link.
_TLDS = ("com|org|net|info|biz|io|co|me|ly|app|dev|xyz|site|online|shop|link|click|top|ai|tv|us|uk|ca|au|"
         "de|fr|nl|es|it|in|ng|ke|za|gh|ug|tz|rw|eg|ma|edu|gov|int|eu")
_LINK_RE = re.compile(
    r"(?:\bhttps?://[^\s<>\"']+)"
    r"|(?:\bwww\.[^\s<>\"']+)"
    rf"|(?:\b(?:[a-z0-9](?:[a-z0-9-]{{0,61}}[a-z0-9])?\.)+(?:{_TLDS})\b(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)


def count_links(text):
    return len(_LINK_RE.findall(text or ""))


def _fold(text):
    return unicodedata.normalize("NFKC", text or "").casefold()


def blocked_word_hits(text, words):
    """Which Studio blocked words/phrases occur in `text`.

    Matching: case-insensitive (Unicode case folding, NFKC-normalized), on
    whole words — "ass" matches "ass" and "ASS!" but not "class" or
    "assistant". A phrase matches its words in order with any whitespace
    between them. An entry ending in "*" also matches words that START with
    it ("scam*" matches "scammer"). Nothing is deleted: a hit only holds the
    comment for review."""
    folded = _fold(text)
    hits = []
    for word in words or []:
        entry = _fold(word).strip()
        prefix = entry.endswith("*")
        entry = entry.rstrip("*").strip()
        if not entry:
            continue
        pattern = r"\s+".join(re.escape(part) for part in entry.split())
        tail = r"\w*" if prefix else ""
        if re.search(rf"(?<!\w){pattern}{tail}(?!\w)", folded):
            hits.append(word)
    return hits


def clean_body(body):
    if not isinstance(body, str):
        raise CommentError("Please write a comment.", 422, "comment_empty")
    body = body.replace("\r\n", "\n").replace("\r", "\n").strip()
    body = re.sub(r"\n{3,}", "\n\n", body)
    if not body:
        raise CommentError("Please write a comment.", 422, "comment_empty")
    if len(body) > MAX_BODY_LENGTH:
        raise CommentError(f"Comments are limited to {MAX_BODY_LENGTH} characters.", 422, "comment_too_long")
    return body


def published_count(user_id):
    return Comment.query.filter_by(user_id=user_id, status="published").count()


def is_trusted(user, settings=None):
    """Trust is derived, never stored: enough currently published comments."""
    settings = settings or get_comment_settings()
    return published_count(user.id) >= settings["trustedThreshold"]


def moderation_reasons(user, body, settings, check_trust=True):
    reasons = []
    if check_trust and not is_trusted(user, settings):
        reasons.append("first_comment")
    if count_links(body) > MAX_LINKS:
        reasons.append("links")
    if blocked_word_hits(body, settings["blockedWords"]):
        reasons.append("blocked_words")
    return reasons


# --- article state -----------------------------------------------------------------------------


def comment_state(article, settings=None, now=None):
    """{"open": bool, "state": "open"|"off"|"closed"|"disabled", "closesAt": iso|None}."""
    settings = settings or get_comment_settings()
    now = now or _now()
    if not settings["enabled"]:
        return {"open": False, "state": "disabled", "closesAt": None}
    if article.status != "published":
        return {"open": False, "state": "closed", "closesAt": None}
    mode = article.comments_mode or "on"
    if mode == "off":
        return {"open": False, "state": "off", "closesAt": None}
    if mode == "close_after":
        published = _aware(article.publish_date)
        days = article.comments_close_after_days
        if published is None or not days:
            return {"open": False, "state": "closed", "closesAt": None}  # fail safe
        closes = published + timedelta(days=days)
        return {"open": now < closes, "state": "open" if now < closes else "closed", "closesAt": closes.isoformat()}
    return {"open": True, "state": "open", "closesAt": None}


# --- restrictions ------------------------------------------------------------------------------


def active_restriction(user_id, now=None):
    now = now or _now()
    rows = (CommentRestriction.query
            .filter(CommentRestriction.user_id == user_id, CommentRestriction.lifted_at.is_(None))
            .order_by(CommentRestriction.created_at.desc()).all())
    for row in rows:
        if row.kind == "ban" or (row.ends_at is not None and _aware(row.ends_at) > now):
            return row
    return None


def restriction_payload(row):
    if row is None:
        return None
    return {"kind": row.kind, "endsAt": _aware(row.ends_at).isoformat() if row.ends_at else None}


def _require_participation(user):
    if user is None or not user.is_active:
        raise CommentError("Please sign in to comment.", 401, "authorization_required")
    row = active_restriction(user.id)
    if row is not None:
        if row.kind == "ban":
            raise CommentError("Your account can no longer take part in comments.", 403, "comment_banned")
        raise CommentError("Your commenting is suspended until "
                           f"{_aware(row.ends_at).strftime('%d %B %Y, %H:%M UTC')}.", 403, "comment_suspended")


# --- form token (minimum time-to-submit) -------------------------------------------------------


def _form_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=_FORM_SALT)


def issue_form_token(user, article):
    return _form_serializer().dumps({"u": user.id, "a": article.id})


def check_form_token(token, user, article, settings, now=None):
    """The token carries its own signed issue time: a too-fast submission is
    one whose server-issued time is less than minSubmitSeconds ago."""
    try:
        data, issued = _form_serializer().loads(token or "", max_age=FORM_TOKEN_MAX_AGE, return_timestamp=True)
    except SignatureExpired as exc:
        raise CommentError("This form has expired. Please reload the page and try again.", 400,
                           "comment_form_expired") from exc
    except BadSignature as exc:
        raise CommentError("Please reload the page and try again.", 400, "comment_form_invalid") from exc
    if data.get("u") != user.id or data.get("a") != article.id:
        raise CommentError("Please reload the page and try again.", 400, "comment_form_invalid")
    elapsed = ((now or _now()) - _aware(issued)).total_seconds()
    if elapsed < settings["minSubmitSeconds"]:
        raise CommentError("That was quick! Please take a moment and send it again.", 429, "comment_too_fast")


# --- create / edit / delete --------------------------------------------------------------------


def create_comment(user, article, body, *, parent_id=None, form_token=None, honeypot=None, raw_ip=None):
    settings = get_comment_settings()
    _require_participation(user)
    if honeypot:
        # Never filled in by a person (the field is hidden from people and
        # assistive technology). Generic answer: nothing to learn from it.
        raise CommentError("Your comment could not be posted.", 400, "comment_rejected")
    state = comment_state(article, settings)
    if not state["open"]:
        raise CommentError("Comments are closed for this article.", 403, "comments_closed")
    check_form_token(form_token, user, article, settings)
    body = clean_body(body)

    parent = None
    if parent_id is not None:
        parent = db.session.get(Comment, parent_id) if isinstance(parent_id, int) else None
        if parent is None or parent.article_id != article.id:
            raise CommentError("That comment can't be replied to.", 422, "comment_parent_invalid")
        if parent.parent_id is not None:
            parent = db.session.get(Comment, parent.parent_id)  # one level: join the top-level thread
        if parent.status != "published":
            raise CommentError("That comment can't be replied to.", 422, "comment_parent_invalid")

    since = _now() - DUPLICATE_WINDOW
    duplicate = (Comment.query.filter(Comment.user_id == user.id, Comment.created_at >= since,
                                      Comment.status.in_(("pending", "published", "hidden")),
                                      Comment.body == body).first())
    if duplicate is not None:
        raise CommentError("You've already posted this comment.", 409, "comment_duplicate")

    reasons = moderation_reasons(user, body, settings)
    now = _now()
    ip_hash = hash_ip(raw_ip)
    comment = Comment(
        article_id=article.id, user_id=user.id, parent_id=parent.id if parent else None, body=body,
        status="pending" if reasons else "published", held_reasons=reasons,
        published_at=None if reasons else now,
        ip_hash=ip_hash, ip_hash_expires_at=now + IP_HASH_RETENTION if ip_hash else None,
    )
    db.session.add(comment)
    db.session.flush()
    _event("created", comment, actor=user, meta={"status": comment.status, "held_reasons": reasons,
                                                  "reply": parent is not None})
    db.session.commit()
    if comment.status == "published":
        notify_reply(comment)
    return comment


def _own(user, comment):
    if user is None or comment.user_id != user.id:
        raise CommentError("You can only change your own comments.", 403, "comment_not_owner")


def edit_comment(user, comment, body, now=None):
    now = now or _now()
    _own(user, comment)
    _require_participation(user)
    if comment.status not in ("pending", "published"):
        raise CommentError("This comment can no longer be edited.", 409, "comment_not_editable")
    if now > _aware(comment.created_at) + EDIT_WINDOW:
        raise CommentError("Comments can only be edited for 15 minutes after posting.", 403,
                           "comment_edit_window_closed")
    body = clean_body(body)
    if body == comment.body:
        return comment
    settings = get_comment_settings()
    # The trust decision was made when it was posted; links and blocked
    # words are checked again on the new text.
    reasons = moderation_reasons(user, body, settings, check_trust=False)
    previous = comment.status
    comment.body = body
    comment.edited_at = now
    if reasons:
        comment.held_reasons = sorted(set(comment.held_reasons or []) | set(reasons))
        if comment.status == "published":
            comment.status = "pending"
    _event("edited", comment, actor=user, meta={"from_status": previous, "to_status": comment.status,
                                                 "held_reasons": reasons})
    db.session.commit()
    return comment


def delete_comment(user, comment):
    """Author deletion: erase the text, keep the row (thread integrity,
    history). Not a moderator removal."""
    _own(user, comment)
    if comment.status == "deleted":
        return comment
    previous = comment.status
    comment.status = "deleted"
    comment.body = None
    comment.deleted_at = _now()
    _event("deleted_by_author", comment, actor=user, meta={"from_status": previous})
    db.session.commit()
    return comment


# --- reports -----------------------------------------------------------------------------------


def report_comment(user, comment, reason, details=None):
    _require_participation(user)
    if comment.status != "published":
        raise CommentError("This comment can't be reported.", 409, "comment_not_reportable")
    if comment.user_id == user.id:
        raise CommentError("You can't report your own comment.", 422, "comment_report_own")
    if reason not in REPORT_REASONS:
        raise CommentError("Please choose a reason.", 422, "comment_report_reason")
    details = (details or "").strip() or None
    if details and reason != "other":
        details = None  # only "other" carries free text
    if details and len(details) > MAX_REPORT_DETAILS:
        raise CommentError(f"Please keep the explanation under {MAX_REPORT_DETAILS} characters.", 422,
                           "comment_report_details")
    if CommentReport.query.filter_by(comment_id=comment.id, reporter_id=user.id).first() is not None:
        raise CommentError("You've already reported this comment.", 409, "comment_already_reported")
    db.session.add(CommentReport(comment_id=comment.id, reporter_id=user.id, reason=reason, details=details))
    _event("reported", comment, actor=user, meta={"reason": reason})
    try:
        db.session.flush()
    except Exception as exc:  # the unique constraint: a concurrent duplicate
        db.session.rollback()
        raise CommentError("You've already reported this comment.", 409, "comment_already_reported") from exc
    settings = get_comment_settings()
    unique_reports = (db.session.query(func.count(func.distinct(CommentReport.reporter_id)))
                      .filter(CommentReport.comment_id == comment.id).scalar())
    hidden = False
    if unique_reports >= settings["reportHideThreshold"] and comment.status == "published":
        comment.status = "hidden"
        comment.hidden_at = _now()
        comment.held_reasons = sorted(set(comment.held_reasons or []) | {"reports"})
        _event("auto_hidden", comment, actor=None,
               meta={"reports": unique_reports, "threshold": settings["reportHideThreshold"]})
        hidden = True
    db.session.commit()
    return {"hidden": hidden}


# --- moderation --------------------------------------------------------------------------------


def _audit(moderator, action, entity_type, entity_id, changes):
    from app.services.audit import log_action

    log_action(moderator, action, entity_type, entity_id, changes)


def approve_comment(moderator, comment):
    """pending/hidden/removed -> published (approve, or restore)."""
    if comment.status == "published":
        return comment
    if comment.status == "deleted":
        raise CommentError("A comment its author deleted can't be restored.", 409, "comment_deleted")
    if comment.status == "removed" and not (comment.body or "").strip():
        # Its text was erased under the 12-month retention rule: nothing to restore.
        raise CommentError("This comment's text was erased under the retention policy and can't be restored.", 409,
                           "comment_body_erased")
    previous = comment.status
    now = _now()
    comment.status = "published"
    comment.published_at = comment.published_at or now
    comment.approved_at = now
    comment.approved_by_id = moderator.id
    comment.hidden_at = None
    comment.removed_at = None
    comment.removed_by_id = None
    comment.removal_reason = None
    action = "approved" if previous == "pending" else "restored"
    _event(action, comment, actor=moderator, meta={"from_status": previous})
    db.session.commit()
    _audit(moderator, f"comment.{'approve' if action == 'approved' else 'restore'}", "Comment", comment.id,
           {"from_status": previous, "to_status": "published"})
    notify_reply(comment)
    return comment


def hide_comment(moderator, comment, reason=None):
    if comment.status not in ("pending", "published"):
        raise CommentError("Only pending or published comments can be hidden.", 409, "comment_not_hideable")
    previous = comment.status
    comment.status = "hidden"
    comment.hidden_at = _now()
    comment.held_reasons = sorted(set(comment.held_reasons or []) | {"moderator"})
    reason = (reason or "").strip()[:500] or None
    _event("hidden", comment, actor=moderator, reason=reason, meta={"from_status": previous})
    db.session.commit()
    _audit(moderator, "comment.hide", "Comment", comment.id, {"from_status": previous, "reason": reason})
    return comment


def remove_comment(moderator, comment, reason):
    reason = (reason or "").strip()
    if not reason:
        raise CommentError("Please give a reason for removing this comment.", 422, "comment_removal_reason")
    if len(reason) > 500:
        raise CommentError("Please keep the reason under 500 characters.", 422, "comment_removal_reason")
    if comment.status in ("removed", "deleted"):
        raise CommentError("This comment is already gone.", 409, "comment_not_removable")
    previous = comment.status
    comment.status = "removed"
    comment.removed_at = _now()
    comment.removed_by_id = moderator.id
    comment.removal_reason = reason
    _event("removed", comment, actor=moderator, reason=reason, meta={"from_status": previous})
    db.session.commit()
    _audit(moderator, "comment.remove", "Comment", comment.id, {"from_status": previous, "reason": reason})
    return comment


def restrict_user(moderator, user, kind, reason, days=None):
    reason = (reason or "").strip()
    if not reason or len(reason) > 500:
        raise CommentError("Please give a reason (up to 500 characters).", 422, "restriction_reason")
    if user.id == moderator.id:
        raise CommentError("You can't restrict your own account.", 422, "restriction_self")
    ends_at = None
    if kind == "suspension":
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= 365:
            raise CommentError("A suspension lasts 1 to 365 days.", 422, "restriction_days")
        ends_at = _now() + timedelta(days=days)
    elif kind != "ban":
        raise CommentError("Unknown restriction.", 422, "restriction_kind")
    # One active restriction at a time: a new one replaces the old.
    for row in CommentRestriction.query.filter_by(user_id=user.id, lifted_at=None).all():
        row.lifted_at = _now()
        row.lifted_by_id = moderator.id
    row = CommentRestriction(user_id=user.id, kind=kind, reason=reason, ends_at=ends_at, created_by_id=moderator.id)
    db.session.add(row)
    _event("user_suspended" if kind == "suspension" else "user_banned", None, actor=moderator,
           subject_user_id=user.id, reason=reason, meta={"days": days} if days else None)
    db.session.commit()
    _audit(moderator, f"comment_user.{'suspend' if kind == 'suspension' else 'ban'}", "User", user.id,
           {"reason": reason, "days": days, "ends_at": ends_at.isoformat() if ends_at else None})
    return row


def lift_restriction(moderator, user):
    rows = CommentRestriction.query.filter_by(user_id=user.id, lifted_at=None).all()
    if not rows:
        raise CommentError("This member has no comment restriction.", 409, "restriction_none")
    for row in rows:
        row.lifted_at = _now()
        row.lifted_by_id = moderator.id
    _event("user_restriction_lifted", None, actor=moderator, subject_user_id=user.id,
           meta={"kinds": sorted({r.kind for r in rows})})
    db.session.commit()
    _audit(moderator, "comment_user.lift", "User", user.id, {"kinds": sorted({r.kind for r in rows})})


# --- reply notifications -----------------------------------------------------------------------


def notification_preference(user, create=False):
    pref = db.session.get(CommentNotificationPreference, user.id)
    if pref is None and create:
        pref = CommentNotificationPreference(user_id=user.id, reply_emails=False,
                                             unsubscribe_token=secrets.token_urlsafe(32))
        db.session.add(pref)
        db.session.flush()
    return pref


def wants_reply_emails(user):
    pref = db.session.get(CommentNotificationPreference, user.id)
    return bool(pref and pref.reply_emails)


def set_reply_emails(user, enabled):
    pref = notification_preference(user, create=True)
    pref.reply_emails = bool(enabled)
    db.session.commit()
    return pref.reply_emails


def unsubscribe_by_token(token):
    """Idempotent; True if the token belongs to someone (already off or not)."""
    if not token or not isinstance(token, str) or len(token) > 100:
        return False
    pref = CommentNotificationPreference.query.filter_by(unsubscribe_token=token).first()
    if pref is None:
        return False
    if pref.reply_emails:
        pref.reply_emails = False
        db.session.commit()
    return True


def notify_reply(comment):
    """Email the parent comment's author about a newly PUBLISHED reply, if
    they opted in. Never to yourself; never for a reply that isn't public.

    reply_notified_at means "handed off to the email service" (Step 15):
      * not eligible (no opt-in, notifications off, own reply, ...): nothing
        is sent and nothing is marked;
      * eligible: the reply is CLAIMED with one conditional UPDATE (only one
        of two concurrent approvals can win), then sent;
      * delivery failed: the claim is released (reply_notified_at back to
        NULL), so it is never recorded as sent. Best effort: a failure
        never blocks the moderation action that triggered it.
    Returns True only when an email was handed off."""
    if comment.parent_id is None or comment.status != "published" or comment.reply_notified_at is not None:
        return False
    settings = get_comment_settings()
    parent = db.session.get(Comment, comment.parent_id)
    owner = parent.user if parent is not None else None
    if (not settings["replyNotificationsEnabled"] or owner is None or not owner.is_active
            or owner.id == comment.user_id or parent.status != "published"):
        return False
    pref = db.session.get(CommentNotificationPreference, owner.id)
    if pref is None or not pref.reply_emails:
        return False
    claimed_at = _now()
    claimed = (Comment.query.filter(Comment.id == comment.id, Comment.reply_notified_at.is_(None))
               .update({"reply_notified_at": claimed_at}, synchronize_session=False))
    db.session.commit()
    if claimed != 1:
        return False  # another request is sending (or sent) it
    from app.services.email import OPTIONAL, send_email

    base = current_app.config["FRONTEND_URL"].rstrip("/")
    article = comment.article
    link = f"{base}/{article.slug}#comment-{comment.id}"
    replier = display_name(comment.user)
    text = (f"{replier} replied to your comment on \"{article.title}\".\n\n"
            f"Read the reply: {link}\n\n"
            "You get these emails because you asked to be told about replies to your comments.\n")
    sent = send_email(owner.email, "New reply to your comment on Women Shaping Futures", text, category=OPTIONAL,
                      unsubscribe_url=f"{base}/comments/unsubscribe/{pref.unsubscribe_token}",
                      one_click_url=f"{base}/api/v1/comments/notifications/one-click/{pref.unsubscribe_token}")
    if not sent:
        Comment.query.filter(Comment.id == comment.id, Comment.reply_notified_at == claimed_at).update(
            {"reply_notified_at": None}, synchronize_session=False)
        db.session.commit()
        return False
    return True


# --- payloads ----------------------------------------------------------------------------------


def display_name(user):
    if user is None:
        return FORMER_MEMBER
    return user.full_name or FORMER_MEMBER


def _avatar(user):
    media = getattr(user, "avatar", None) if user is not None else None
    return media.public_url if media is not None and media.public_url else None


def _iso(value):
    return _aware(value).isoformat() if value else None


def _public_item(comment, viewer, reported_ids, now):
    own = viewer is not None and comment.user_id == viewer.id
    if comment.status in ("deleted", "removed"):
        # Placeholder only: no author, no text.
        return {"id": comment.id, "parentId": comment.parent_id, "placeholder": True,
                "body": DELETED_PLACEHOLDER if comment.status == "deleted" else REMOVED_PLACEHOLDER,
                "author": None, "createdAt": _iso(comment.created_at), "edited": False, "replies": []}
    item = {
        "id": comment.id, "parentId": comment.parent_id, "placeholder": False, "body": comment.body,
        "author": {"name": display_name(comment.user), "avatarUrl": _avatar(comment.user),
                   "formerMember": comment.user is None},
        "createdAt": _iso(comment.created_at), "edited": comment.edited_at is not None,
        "status": "published" if comment.status == "published" else ("pending" if own else None),
        "isOwn": own, "replies": [],
    }
    if own:
        item["status"] = comment.status if comment.status in ("pending", "published") else "hidden"
        editable_until = _aware(comment.created_at) + EDIT_WINDOW
        item["editableUntil"] = editable_until.isoformat() if comment.status in ("pending", "published") \
            and now < editable_until else None
    elif viewer is not None:
        item["reportedByMe"] = comment.id in reported_ids
    return item


def public_thread(article, viewer=None, now=None):
    """Published comments (+ the viewer's own pending/hidden ones, marked as
    such) as top-level threads with one level of replies. A deleted/removed
    top-level comment appears only as a placeholder, and only while it still
    has visible replies. Never: emails, IPs, user ids, moderation data."""
    now = now or _now()
    rows = (Comment.query.filter_by(article_id=article.id)
            .order_by(Comment.created_at.asc(), Comment.id.asc()).all())
    reported_ids = set()
    if viewer is not None:
        reported_ids = {r.comment_id for r in CommentReport.query.filter(
            CommentReport.reporter_id == viewer.id,
            CommentReport.comment_id.in_([c.id for c in rows] or [0])).all()}

    def visible(c):
        if c.status == "published":
            return True
        return viewer is not None and c.user_id == viewer.id and c.status in ("pending", "hidden")

    replies = {}
    for c in rows:
        if c.parent_id is not None and visible(c):
            replies.setdefault(c.parent_id, []).append(_public_item(c, viewer, reported_ids, now))
    threads = []
    for c in rows:
        if c.parent_id is not None:
            continue
        kids = replies.get(c.id, [])
        if visible(c):
            item = _public_item(c, viewer, reported_ids, now)
        elif c.status in ("deleted", "removed") and any(k.get("status") == "published" for k in kids):
            item = _public_item(c, viewer, reported_ids, now)
        else:
            continue
        item["replies"] = kids
        threads.append(item)
    count = sum(1 for c in rows if c.status == "published")
    return {"comments": threads, "count": count}


def moderator_item(comment):
    return {
        "id": comment.id, "status": comment.status, "body": comment.body,
        "heldReasons": list(comment.held_reasons or []),
        "parentId": comment.parent_id,
        "article": {"id": comment.article.id, "title": comment.article.title, "slug": comment.article.slug},
        "author": {"userId": comment.user_id, "name": display_name(comment.user),
                   "restriction": restriction_payload(active_restriction(comment.user_id)) if comment.user_id
                   else None},
        "reportCount": len(comment.reports),
        "createdAt": _iso(comment.created_at), "editedAt": _iso(comment.edited_at),
        "publishedAt": _iso(comment.published_at), "hiddenAt": _iso(comment.hidden_at),
        "removedAt": _iso(comment.removed_at), "removalReason": comment.removal_reason,
        "deletedAt": _iso(comment.deleted_at),
    }


def moderator_history(comment):
    events = (CommentEvent.query.filter(
        (CommentEvent.comment_id == comment.id)
        | ((CommentEvent.comment_id.is_(None)) & (CommentEvent.subject_user_id == comment.user_id)
           & (CommentEvent.subject_user_id.isnot(None))))
        .order_by(CommentEvent.created_at.asc(), CommentEvent.id.asc()).all())
    return [{"action": e.action, "actor": display_name(e.actor) if e.actor_id else "System",
             "reason": e.reason, "meta": e.meta, "createdAt": _iso(e.created_at),
             "scope": "member" if e.comment_id is None else "comment"} for e in events]


def moderator_reports(comment):
    return [{"reason": r.reason, "details": r.details, "reporter": display_name(r.reporter),
             "createdAt": _iso(r.created_at)} for r in sorted(comment.reports, key=lambda r: r.id)]


# --- account deletion / export readiness (Batch 4) ---------------------------------------------


def detach_user_comments(user_id, remove=False):
    """For account deletion: detach every comment from the account so it
    shows "Former member", clear its IP hash; with remove=True ("Also remove
    my comments") erase the text too (placeholders keep reply threads
    intact). Reports and history lose the account link the same way.
    Caller commits; then the users row can be deleted."""
    values = {"user_id": None, "ip_hash": None, "ip_hash_expires_at": None}
    if remove:
        Comment.query.filter(Comment.user_id == user_id, Comment.status != "deleted").update(
            {"status": "deleted", "body": None, "deleted_at": _now()}, synchronize_session=False)
    Comment.query.filter(Comment.user_id == user_id).update(values, synchronize_session=False)
    CommentReport.query.filter(CommentReport.reporter_id == user_id).update(
        {"reporter_id": None}, synchronize_session=False)
    CommentEvent.query.filter(CommentEvent.actor_id == user_id).update({"actor_id": None}, synchronize_session=False)
    CommentEvent.query.filter(CommentEvent.subject_user_id == user_id).update(
        {"subject_user_id": None}, synchronize_session=False)


def comments_for_export(user):
    """The member's own comments for the self-service data export (Batch 4):
    their text and its state, never other people's data or moderation
    internals."""
    rows = Comment.query.filter_by(user_id=user.id).order_by(Comment.created_at.asc()).all()
    return [{"article": {"title": c.article.title, "slug": c.article.slug},
             "isReply": c.parent_id is not None, "status": c.status, "body": c.body,
             "createdAt": _iso(c.created_at), "editedAt": _iso(c.edited_at), "deletedAt": _iso(c.deleted_at)}
            for c in rows]
