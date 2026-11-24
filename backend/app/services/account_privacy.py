"""Self-service data export, account deletion and privacy requests (Step 16).

FK AUDIT — every foreign key to users.id (SQLAlchemy metadata: 61; the
database has 60 because media.uploaded_by_id was never created there, a
pre-existing drift) is classified in FK_TREATMENT below. A test fails if a
new FK appears without a decision.
  delete  : removed with the account (sessions, tokens, 2FA, saved items,
            registrations, enrolments, certificates, notifications, roles,
            comment restrictions/preferences — ON DELETE CASCADE)
  detach  : kept without the link to the person (SET NULL, or nulled here):
            staff authorship/review references, audit log, analytics events,
            comments ("Former member"), community member link, consent records
  retain  : payment records, kept 6 years and detached (circle/resource
            payments, subscriptions, purchases, orders)
  block   : staff-only NOT NULL references (internal notes). An account with
            staff roles can't be deleted self-service at all (a Super Admin
            removes staff).

Deletion: request -> every session revoked at once (auth_version bump) and
the account can't be used (login only offers cancellation) -> 14-day grace
period, cancellable by signing in or by the emailed link -> purge_due()
(the scheduled maintenance job) deletes/anonymises everything per the table.
"""
from datetime import date, datetime, timedelta, timezone

from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import select, update

from app.extensions import db
from app.models.privacy import PRIVACY_REQUEST_TARGET_DAYS, PrivacyRequest
from app.models.user import User

GRACE_PERIOD = timedelta(days=14)
_CANCEL_SALT = "wsf-account-deletion-cancel-v1"
_LOGIN_CANCEL_SALT = "wsf-account-deletion-login-cancel-v1"
NON_STAFF_ROLES = {"member", "employer"}

D, X, R, B = "delete", "detach", "retain", "block"
FK_TREATMENT = {
    "analytics_events.user_id": (X, "event kept, person unlinked (deleted at 14 months by retention)"),
    "article_revisions.created_by_id": (X, "staff authorship reference"),
    "articles.approved_by_user_id": (X, "staff reference"),
    "articles.created_by_id": (X, "staff reference"),
    "audit_logs.user_id": (X, "audit history kept, identity link removed (SET NULL)"),
    "authors.user_id": (X, "published byline profile kept, account link removed"),
    "circle_payments.user_id": (R, "payment record, 6 years (SET NULL)"),
    "circle_subscriptions.user_id": (R, "billing record, 6 years (SET NULL)"),
    "comment_events.actor_id": (X, "moderation history, person unlinked"),
    "comment_events.subject_user_id": (X, "moderation history, person unlinked"),
    "comment_notification_preferences.user_id": (D, "reply-email choice"),
    "comment_reports.reporter_id": (X, "report kept, reporter unlinked"),
    "comment_restrictions.created_by_id": (X, "moderator reference"),
    "comment_restrictions.lifted_by_id": (X, "moderator reference"),
    "comment_restrictions.user_id": (D, "restriction on the deleted account"),
    "comments.approved_by_id": (X, "moderator reference"),
    "comments.removed_by_id": (X, "moderator reference"),
    "comments.user_id": (X, "comments kept as 'Former member' (or removed on request), IP hash cleared"),
    "consent_records.user_id": (X, "kept 2 years after deletion (account_deleted_at), unlinked"),
    "contact_inquiries.assigned_to_user_id": (X, "staff reference"),
    "contact_inquiries.resolved_by_user_id": (X, "staff reference"),
    "contact_notes.user_id": (B, "staff note author (staff only)"),
    "directory_listings.reviewed_by_user_id": (X, "staff reference"),
    "directory_listings.verified_by_user_id": (X, "staff reference"),
    "directory_submission_notes.user_id": (B, "staff note author (staff only)"),
    "directory_submissions.reviewed_by_user_id": (X, "staff reference"),
    "event_registrations.user_id": (D, "the person's registrations"),
    "jobs.posted_by_id": (X, "listing kept, poster unlinked"),
    "learning_certificates.user_id": (D, "certificates deleted (public verification then shows not found)"),
    "learning_enrollments.user_id": (D, "enrolments + lesson progress"),
    "media.uploaded_by_id": (X, "uploaded media kept, uploader unlinked"),
    "member_notes.user_id": (B, "staff note author (staff only)"),
    "members.user_id": (D, "the linked community member profile is deleted"),
    "mentorship_application_notes.user_id": (B, "staff note author (staff only)"),
    "mentorship_applications.reviewed_by_id": (X, "staff reference"),
    "mentorship_match_notes.user_id": (B, "staff note author (staff only)"),
    "newsletter_send_records.actor_id": (X, "staff reference"),
    "newsletter_subscriber_events.actor_id": (X, "staff reference"),
    "newsletter_suppression_imports.actor_id": (X, "staff reference"),
    "nomination_notes.user_id": (B, "staff note author (staff only)"),
    "nominations.assigned_reviewer_id": (X, "staff reference"),
    "notifications.recipient_user_id": (D, "the person's notifications"),
    "order_notes.user_id": (B, "staff note author (staff only)"),
    "orders.user_id": (R, "payment record, 6 years (SET NULL)"),
    "page_revisions.created_by_id": (X, "staff reference"),
    "pages.last_reviewed_by_id": (X, "staff reference"),
    "pages.updated_by_id": (X, "staff reference"),
    "partnership_inquiries.assigned_to_id": (X, "staff reference"),
    "partnership_notes.user_id": (B, "staff note author (staff only)"),
    "password_reset_tokens.user_id": (D, "reset tokens"),
    "privacy_requests.created_by_id": (X, "staff reference"),
    "privacy_requests.user_id": (X, "the request documents the deletion; name/email cleared"),
    "refresh_sessions.user_id": (D, "sessions"),
    "resource_download_tokens.user_id": (D, "download tokens"),
    "resource_payments.user_id": (R, "payment record, 6 years (SET NULL)"),
    "resource_purchases.user_id": (R, "purchase record, 6 years (SET NULL)"),
    "saved_items.user_id": (D, "saved items"),
    "story_submissions.assigned_editor_id": (X, "staff reference"),
    "submission_notes.user_id": (B, "staff note author (staff only)"),
    "token_blocklist.user_id": (D, "revoked-token entries"),
    "two_factor_recovery_codes.user_id": (D, "2FA recovery codes"),
    "user_roles.user_id": (D, "role assignments"),
    "user_two_factor.user_id": (D, "2FA secret"),
}


class AccountPrivacyError(Exception):
    def __init__(self, message, status=400, code="account_privacy_error"):
        super().__init__(message)
        self.status = status
        self.code = code


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def user_foreign_keys():
    """[(table, column, ondelete, nullable)] for every FK to users.id."""
    rows = []
    for table in db.metadata.sorted_tables:
        for fk in table.foreign_keys:
            if fk.column.table.name == "users":
                rows.append((table, fk.parent, (fk.ondelete or "NO ACTION").upper(), fk.parent.nullable))
    return rows


# --- privacy requests --------------------------------------------------------------------------


def open_privacy_request(*, request_type, user=None, source="studio", details=None, requester_name=None,
                         requester_email=None, status="open", created_by=None):
    now = _now()
    row = PrivacyRequest(user_id=user.id if user else None, request_type=request_type, status=status, source=source,
                         details=details, requester_name=requester_name or (user.full_name if user else None),
                         requester_email=requester_email or (user.email if user else None), opened_at=now,
                         due_at=now + timedelta(days=PRIVACY_REQUEST_TARGET_DAYS),
                         completed_at=now if status == "completed" else None,
                         created_by_id=created_by.id if created_by else None)
    db.session.add(row)
    db.session.flush()
    return row


# --- export ------------------------------------------------------------------------------------

# Never exported: credentials, token hashes, keyed IP hashes, payment gateway
# internals, staff-only fields.
_NEVER = {"password_hash", "auth_version", "token_hash", "code_hash", "secret_encrypted", "pending_secret_encrypted",
          "ip_hash", "ip_hash_expires_at", "unsubscribe_token", "provider_snapshot", "authorization_url", "dedupe_key",
          "admin_tags", "referral_note", "last_used_step", "jti"}


def _value(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _rows(table_name, where_column, value, exclude=(), limit=None):
    table = db.metadata.tables[table_name]
    stmt = select(table).where(table.c[where_column] == value).order_by(table.c[table.primary_key.columns.keys()[0]])
    if limit:
        stmt = stmt.limit(limit)
    skip = _NEVER | set(exclude)
    return [{k: _value(v) for k, v in row._mapping.items() if k not in skip}
            for row in db.session.execute(stmt).all()]


def build_export(user):
    """Everything WSF holds that is this person's own data, as JSON-able
    dicts. Never other people's data, credentials, token hashes, IP hashes or
    staff-only notes."""
    from app.models.newsletter import NewsletterSubscriber, NewsletterSubscriberEvent
    from app.models.submissions import StorySubmission
    from app.services.comments import comments_for_export
    from app.services.two_factor import is_enabled

    account = {
        "email": user.email, "first_name": user.first_name, "last_name": user.last_name,
        "display_name": user.display_name, "bio": user.bio, "country_code": user.country_code,
        "created_at": _value(user.created_at), "last_login_at": _value(user.last_login_at),
        "email_verified": user.is_verified, "roles": sorted(user.role_names()),
        "career_goals": user.career_goals, "two_factor_enabled": is_enabled(user),
        "avatar_url": user.avatar.public_url if user.avatar else None,
    }
    enrollments = _rows("learning_enrollments", "user_id", user.id)
    for e in enrollments:
        e["lesson_progress"] = _rows("learning_lesson_progress", "enrollment_id", e["id"])
    orders = _rows("orders", "user_id", user.id)
    for o in orders:
        o["items"] = _rows("order_items", "order_id", o["id"])
    subscriber = NewsletterSubscriber.query.filter_by(email=user.email.lower()).first()
    newsletter = None
    if subscriber is not None:
        newsletter = {
            "status": subscriber.status, "consent_at": _value(subscriber.consent_at),
            "consent_version": subscriber.consent_version, "consent_source": subscriber.consent_source,
            "confirmed_at": _value(subscriber.confirmed_at), "subscribed_at": _value(subscriber.subscribed_at),
            "unsubscribed_at": _value(subscriber.unsubscribed_at), "interests": [t.slug for t in subscriber.interests],
            "history": [{"event": e.event, "at": _value(e.created_at)} for e in NewsletterSubscriberEvent.query
                        .filter_by(subscriber_id=subscriber.id).order_by(NewsletterSubscriberEvent.id).all()],
        }
    stories = [{"reference": s.reference, "title": s.title, "summary": s.summary, "body": s.body,
                "status": s.status, "submitted_at": _value(s.created_at) if hasattr(s, "created_at") else None}
               for s in StorySubmission.query.filter_by(email=user.email.lower()).all()]
    return {
        "format": "wsf-account-export-v1",
        "generated_at": _value(_now()),
        "account": account,
        "sign_in_sessions": _rows("refresh_sessions", "user_id", user.id),
        "community_membership": _rows("members", "user_id", user.id),
        "saved_items": _rows("saved_items", "user_id", user.id),
        "event_registrations": _rows("event_registrations", "user_id", user.id),
        "learning_enrollments": enrollments,
        "learning_certificates": _rows("learning_certificates", "user_id", user.id),
        "circle_subscriptions": _rows("circle_subscriptions", "user_id", user.id),
        "circle_payments": _rows("circle_payments", "user_id", user.id),
        "resource_purchases": _rows("resource_purchases", "user_id", user.id),
        "resource_payments": _rows("resource_payments", "user_id", user.id),
        "orders": orders,
        "comments": comments_for_export(user),
        "comment_reply_emails": _rows("comment_notification_preferences", "user_id", user.id),
        "newsletter": newsletter,
        "cookie_consent_records": _rows("consent_records", "user_id", user.id),
        "story_submissions": stories,
        "notifications": _rows("notifications", "recipient_user_id", user.id),
        "analytics_events": _rows("analytics_events", "user_id", user.id, limit=5000),
        "privacy_requests": _rows("privacy_requests", "user_id", user.id, exclude=("admin_notes", "created_by_id")),
    }


# --- deletion ----------------------------------------------------------------------------------


def deletion_blockers(user):
    """Reasons this account can't be deleted self-service (staff accounts)."""
    blockers = []
    if set(user.role_names()) - NON_STAFF_ROLES:
        blockers.append("staff_roles")
    for table, column, ondelete, nullable in user_foreign_keys():
        if FK_TREATMENT.get(f"{table.name}.{column.name}", (None,))[0] == B:
            if db.session.execute(select(column).where(column == user.id).limit(1)).first() is not None:
                blockers.append(f"{table.name}")
    return blockers


def _serializer(salt):
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=salt)


def request_deletion(user, password, remove_comments=False):
    from app.services.audit import log_action
    from app.services.email import TRANSACTIONAL, send_email
    from app.services.refresh_sessions import invalidate_user_sessions

    if not password or not user.check_password(password):
        raise AccountPrivacyError("Your password isn't right.", 422, "invalid_credentials")
    if user.deletion_scheduled_for is not None:
        raise AccountPrivacyError("Deletion is already scheduled.", 409, "deletion_already_scheduled")
    if deletion_blockers(user):
        raise AccountPrivacyError("Staff accounts can't be deleted here. Ask a Super Admin.", 409, "deletion_blocked")
    now = _now()
    user.deletion_requested_at = now
    user.deletion_scheduled_for = now + GRACE_PERIOD
    user.deletion_remove_comments = bool(remove_comments)
    # Every session ends now; nothing issued before this works any more.
    invalidate_user_sessions(user, "deletion_requested")
    open_privacy_request(request_type="deletion", user=user, source="self_service", status="in_progress",
                         details=f"Self-service deletion scheduled for {user.deletion_scheduled_for.date().isoformat()}"
                                 f"{'; also remove comments' if remove_comments else ''}.")
    db.session.commit()
    log_action(user, "account.deletion_requested", "User", user.id, {"remove_comments": bool(remove_comments)})
    token = _serializer(_CANCEL_SALT).dumps({"u": user.id, "r": int(now.timestamp())})
    base = current_app.config["FRONTEND_URL"].rstrip("/")
    when = user.deletion_scheduled_for.strftime("%d %B %Y")
    send_email(user.email, "Your Women Shaping Futures account is scheduled for deletion",
               f"You asked us to delete your Women Shaping Futures account. It will be permanently deleted on {when}.\n\n"
               "Until then you can change your mind: sign in, or use this link to cancel the deletion:\n"
               f"{base}/account/deletion/cancel/{token}\n\n"
               "If you didn't ask for this, use the link above and change your password.\n",
               category=TRANSACTIONAL)
    return user


def _cancel(user, how):
    from app.services.audit import log_action

    if user.deletion_scheduled_for is None:
        return False
    user.deletion_requested_at = None
    user.deletion_scheduled_for = None
    user.deletion_remove_comments = False
    for row in PrivacyRequest.query.filter_by(user_id=user.id, request_type="deletion", status="in_progress").all():
        row.status = "declined"
        row.completed_at = _now()
        row.admin_notes = ((row.admin_notes or "") + f"\nCancelled by the member ({how}).").strip()
    db.session.commit()
    log_action(user, "account.deletion_cancelled", "User", user.id, {"via": how})
    return True


def cancel_with_email_token(token):
    try:
        data = _serializer(_CANCEL_SALT).loads(token or "", max_age=int(GRACE_PERIOD.total_seconds()) + 86400)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get("u"))
    if user is None or user.deletion_requested_at is None or \
            int(_aware(user.deletion_requested_at).timestamp()) != data.get("r"):
        return None
    _cancel(user, "email link")
    return user


def issue_login_cancel_token(user):
    """Login of an account scheduled for deletion: no session, only the
    option to cancel (10 minutes, after a correct password)."""
    return _serializer(_LOGIN_CANCEL_SALT).dumps({"u": user.id, "av": user.auth_version})


def cancel_with_login_token(token):
    try:
        data = _serializer(_LOGIN_CANCEL_SALT).loads(token or "", max_age=600)
    except (BadSignature, SignatureExpired):
        return None
    user = db.session.get(User, data.get("u"))
    if user is None or user.auth_version != data.get("av") or user.deletion_scheduled_for is None:
        return None
    _cancel(user, "sign-in")
    return user


def purge_user(user):
    """Permanently delete one account per FK_TREATMENT. Caller commits."""
    from app.models.comment import Comment  # noqa: F401  (detach helper below)
    from app.models.community import Member
    from app.models.consent import ConsentRecord
    from app.models.submissions import StorySubmission
    from app.models.token_blocklist import TokenBlocklist
    from app.services.comments import detach_user_comments

    uid, email, now = user.id, user.email.lower(), _now()
    summary = {"comments_removed": bool(user.deletion_remove_comments)}
    detach_user_comments(uid, remove=bool(user.deletion_remove_comments))

    # Story submissions sent from this account's address: anonymised when an
    # article was made from them (the published work stays), else deleted.
    from app.models.article import Article

    anonymised = deleted = 0
    for sub in StorySubmission.query.filter_by(email=email).all():
        if Article.query.filter_by(source_submission_id=sub.id).first() is not None:
            sub.first_name, sub.last_name = "Former", "member"
            sub.email = f"deleted-submitter-{sub.id}@invalid.invalid"
            for field in ("city", "professional_title", "organization_name", "linkedin_url", "website_url"):
                setattr(sub, field, None)
            if hasattr(sub, "phone"):
                sub.phone = None
            sub.anonymised_at = now
            anonymised += 1
        else:
            db.session.delete(sub)
            deleted += 1
    summary.update(stories_anonymised=anonymised, stories_deleted=deleted)

    # The linked community member profile is the person's own data.
    from app.models.mentorship import MentorshipApplication

    for member in Member.query.filter_by(user_id=uid).all():
        MentorshipApplication.query.filter_by(member_id=member.id).update({"member_id": None},
                                                                            synchronize_session=False)
        db.session.delete(member)

    ConsentRecord.query.filter_by(user_id=uid).update({"account_deleted_at": now}, synchronize_session=False)
    TokenBlocklist.query.filter_by(user_id=uid).delete(synchronize_session=False)
    for row in PrivacyRequest.query.filter_by(user_id=uid).all():
        row.requester_name = None
        row.requester_email = None
        if row.request_type == "deletion" and row.status != "completed":
            row.status = "completed"
            row.completed_at = now
    # Every other nullable reference with no ON DELETE rule is nulled here.
    for table, column, ondelete, nullable in user_foreign_keys():
        if ondelete == "NO ACTION" and nullable and table.name != "token_blocklist":
            db.session.execute(update(table).where(column == uid).values({column.name: None}))
    db.session.flush()
    db.session.delete(user)
    db.session.flush()
    return summary


def purge_due(now=None):
    """Purge every account whose grace period has ended. Idempotent; logs
    counts only. Returns {"purged": n, "skipped": n}."""
    from app.services.audit import log_action

    now = now or _now()
    purged = skipped = 0
    for user in User.query.filter(User.deletion_scheduled_for.isnot(None), User.deletion_scheduled_for <= now).all():
        if deletion_blockers(user):
            skipped += 1
            continue
        uid = user.id
        summary = purge_user(user)
        db.session.commit()
        log_action(None, "account.purged", "User", uid, summary)
        purged += 1
    return {"purged": purged, "skipped": skipped}
