"""Retention engine (Step 17): one scheduled, idempotent run that removes or
reduces personal data once its period is over. Logs counts only, never
personal data. Runs inside the existing maintenance command
(`flask publish-due-content`, every few minutes) and on its own as
`flask retention-run [--dry-run]`.

Periods are Studio settings (SiteSetting "retention", app/services/
retention.py RETENTION_RULES), bounded so nothing can be set to zero, a
negative number or (for payments) below the approved 6 years. Defaults are
the approved product defaults:

  analytics events ............... 14 months  delete
  sign-in/sign-up IP + browser ... 12 months  cleared from audit entries
                                               (the entries themselves stay)
  contact inquiries .............. 2 years    delete (notes cascade)
  unverified accounts ............ 30 days    INACTIVE: WSF has no email
                                               verification flow, so every
                                               member is unverified (would
                                               delete everyone). Not run.
  inactive accounts .............. 3 years    warning email 30 days before,
                                               then deleted like a self-
                                               service deletion
  declined story submissions ..... 12 months  delete
  comment IP hashes .............. 90 days    cleared (set at creation)
  password-reset tokens .......... 24 hours   delete
  payment records ................ 6 years    delete (circle/resource payments,
                                               orders)
  consent records ................ account lifetime + 2 years (after deletion)
  moderator-removed comment text . 12 months  body erased; status, reason
                                               and history kept
  server/error logs .............. 90 days    NOT application-controlled:
                                               stdout -> journald, plus the cron
                                               log file; deploy config sets it
                                               (DEPLOYMENT.md, deploy/logrotate)
"""
from datetime import datetime, timedelta, timezone

from flask import current_app
from sqlalchemy import func, or_

from app.extensions import db
from app.models.cms import SiteSetting

RETENTION_KEY = "retention"

# key: (default, minimum, maximum, unit, label)
RETENTION_RULES = {
    "analyticsEventsMonths": (14, 1, 60, "months", "Analytics events"),
    "authIpMonths": (12, 1, 60, "months", "Sign-in/sign-up IP address and browser"),
    "contactInquiriesMonths": (24, 1, 120, "months", "Contact inquiries"),
    "unverifiedAccountDays": (30, 7, 365, "days", "Unverified new accounts (email never confirmed)"),
    "inactiveAccountYears": (3, 1, 10, "years", "Inactive accounts"),
    "inactiveWarningDays": (30, 7, 90, "days", "Warning before inactive-account deletion"),
    "declinedStoryMonths": (12, 1, 60, "months", "Declined story submissions"),
    "passwordResetTokenHours": (24, 1, 168, "hours", "Password-reset tokens"),
    "paymentRecordYears": (6, 6, 20, "years", "Payment records"),
    "consentRecordYearsAfterAccount": (2, 1, 10, "years", "Consent records after account deletion"),
    "removedCommentTextMonths": (12, 1, 60, "months", "Moderator-removed comment text"),
}
# Fixed (shown, not editable): set where the data is created / by deployment.
FIXED_RULES = {
    "commentIpHashDays": (90, "Comment IP hashes (set when each comment is posted)"),
    "serverLogDays": (90, "Server/error logs (deployment config: journald + logrotate)"),
}
AUTH_ACTIONS = ("user.login", "user.logout", "user.register")
AUTH_ACTION_PREFIXES = ("2fa.", "password_reset.")


class RetentionSettingsError(ValueError):
    pass


def get_retention_settings():
    row = db.session.get(SiteSetting, RETENTION_KEY)
    stored = row.value if row and isinstance(row.value, dict) else {}
    return {k: stored.get(k, default) if isinstance(stored.get(k), int) else default
            for k, (default, *_rest) in RETENTION_RULES.items()}


def retention_settings_payload():
    values = get_retention_settings()
    return {
        "values": values,
        "rules": {k: {"default": d, "min": lo, "max": hi, "unit": unit, "label": label}
                  for k, (d, lo, hi, unit, label) in RETENTION_RULES.items()},
        "fixed": {k: {"value": v, "label": label} for k, (v, label) in FIXED_RULES.items()},
        "unverifiedAccountsActive": True,
    }


def save_retention_settings(data):
    if not isinstance(data, dict):
        raise RetentionSettingsError("Retention settings must be an object.")
    values = data.get("values", data)
    unknown = set(values) - set(RETENTION_RULES)
    if unknown:
        raise RetentionSettingsError(f"Unknown retention setting(s): {', '.join(sorted(unknown))}.")
    current = get_retention_settings()
    for key, value in values.items():
        _default, low, high, unit, label = RETENTION_RULES[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise RetentionSettingsError(f"{label}: a whole number of {unit} from {low} to {high}.")
        current[key] = value
    row = db.session.get(SiteSetting, RETENTION_KEY)
    if row is None:
        db.session.add(SiteSetting(key=RETENTION_KEY, value=current))
    else:
        row.value = current
    return current


def _months(n):
    return timedelta(days=round(n * 30.437))


def _years(n):
    return timedelta(days=round(n * 365.25))


# --- rules ---------------------------------------------------------------------------------------


def _delete(query, dry_run):
    count = query.count()
    if count and not dry_run:
        query.delete(synchronize_session=False)
    return count


def _analytics(now, s, dry_run):
    from app.models.analytics import AnalyticsEvent

    return _delete(AnalyticsEvent.query.filter(AnalyticsEvent.created_at < now - _months(s["analyticsEventsMonths"])),
                   dry_run)


def _auth_ip(now, s, dry_run):
    from app.models.audit import AuditLog

    auth = or_(AuditLog.action.in_(AUTH_ACTIONS), *[AuditLog.action.startswith(p) for p in AUTH_ACTION_PREFIXES])
    query = AuditLog.query.filter(auth, AuditLog.created_at < now - _months(s["authIpMonths"]),
                                  or_(AuditLog.ip_address.isnot(None), AuditLog.user_agent.isnot(None)))
    count = query.count()
    if count and not dry_run:
        query.update({"ip_address": None, "user_agent": None}, synchronize_session=False)
    return count


def _contact(now, s, dry_run):
    from app.models.contact import ContactInquiry

    cutoff = now - _months(s["contactInquiriesMonths"])
    rows = ContactInquiry.query.filter(ContactInquiry.created_at < cutoff).all()
    if not dry_run:
        for row in rows:  # ORM delete so the notes cascade
            db.session.delete(row)
    return len(rows)


def _declined_stories(now, s, dry_run):
    from app.models.article import Article
    from app.models.submissions import StorySubmission

    cutoff = now - _months(s["declinedStoryMonths"])
    rows = (StorySubmission.query.filter(StorySubmission.status == "declined",
                                         func.coalesce(StorySubmission.reviewed_at, StorySubmission.updated_at) < cutoff)
            .filter(~StorySubmission.id.in_(db.session.query(Article.source_submission_id)
                                            .filter(Article.source_submission_id.isnot(None))))
            .all())
    if not dry_run:
        for row in rows:
            db.session.delete(row)
    return len(rows)


def _comment_ip_hashes(now, s, dry_run):
    from app.models.comment import Comment

    query = Comment.query.filter(Comment.ip_hash_expires_at.isnot(None), Comment.ip_hash_expires_at <= now)
    count = query.count()
    if count and not dry_run:
        query.update({"ip_hash": None, "ip_hash_expires_at": None}, synchronize_session=False)
    return count


def _reset_tokens(now, s, dry_run):
    from app.models.password_reset import PasswordResetToken

    return _delete(PasswordResetToken.query.filter(
        PasswordResetToken.created_at < now - timedelta(hours=s["passwordResetTokenHours"])), dry_run)


def _payments(now, s, dry_run):
    """Accounting records vs entitlements (Batch 4 corrections):
      circle_payments, resource_payments, orders: accounting evidence, kept at
        least paymentRecordYears (min 6) after creation, then deleted.
      circle_subscriptions: membership entitlement. Never deleted here. Once a
        subscription has ENDED (cancelled/expired/revoked) for longer than the
        period, only its provider/payment references are cleared.
      resource_purchases: permanent entitlement to a purchased resource. Never
        deleted or reduced by age (they hold no payment detail beyond a
        reference); they end only with the account.
    Deleting an old payment never touches the subscription or purchase it
    paid for."""
    from app.models.circle import CirclePayment, CircleSubscription
    from app.models.commerce import Order
    from app.models.resource import ResourcePayment

    cutoff = now - _years(s["paymentRecordYears"])
    count = _delete(CirclePayment.query.filter(CirclePayment.created_at < cutoff), dry_run)
    count += _delete(ResourcePayment.query.filter(ResourcePayment.created_at < cutoff), dry_run)
    orders = Order.query.filter(Order.created_at < cutoff).all()
    if not dry_run:
        for order in orders:  # ORM delete: order items/notes follow the model's own rules
            db.session.delete(order)
    ended = CircleSubscription.query.filter(
        CircleSubscription.status.in_(("cancelled", "expired", "revoked")),
        func.coalesce(CircleSubscription.ended_at, CircleSubscription.cancelled_at, CircleSubscription.updated_at) < cutoff,
        or_(CircleSubscription.provider_customer_id.isnot(None), CircleSubscription.provider_subscription_id.isnot(None),
            CircleSubscription.payment_reference.isnot(None)))
    minimised = ended.count()
    if minimised and not dry_run:
        ended.update({"provider_customer_id": None, "provider_subscription_id": None, "payment_reference": None},
                     synchronize_session=False)
    return count + len(orders) + minimised


def _consent(now, s, dry_run):
    from app.models.consent import ConsentRecord

    return _delete(ConsentRecord.query.filter(
        ConsentRecord.account_deleted_at.isnot(None),
        ConsentRecord.account_deleted_at < now - _years(s["consentRecordYearsAfterAccount"])), dry_run)


def _removed_comment_text(now, s, dry_run):
    from app.models.comment import Comment, CommentEvent

    rows = Comment.query.filter(Comment.status == "removed", Comment.body.isnot(None),
                                Comment.removed_at < now - _months(s["removedCommentTextMonths"])).all()
    if not dry_run:
        for row in rows:
            row.body = None
            db.session.add(CommentEvent(comment_id=row.id, subject_user_id=row.user_id, actor_id=None,
                                        action="body_erased", meta={"retention_months": s["removedCommentTextMonths"]}))
    return len(rows)


def last_activity(user):
    """Latest real use of the account: sign-in, a session refresh (which is
    how a returning signed-in member shows up) or account creation."""
    from app.models.refresh_session import RefreshSession

    last_refresh = db.session.query(func.max(RefreshSession.last_used_at)).filter(
        RefreshSession.user_id == user.id).scalar()
    times = [t if t is None or t.tzinfo else t.replace(tzinfo=timezone.utc)
             for t in (user.last_login_at, last_refresh, user.created_at)]
    return max(t for t in times if t is not None)


def _inactive_candidates():
    """Accounts automatic deletion may consider: never staff, never active
    Circle members, never an account with a deletion blocker (the same
    blockers self-service deletion uses)."""
    from app.models.circle import CircleSubscription
    from app.models.user import User
    from app.services.account_privacy import NON_STAFF_ROLES, deletion_blockers

    paid = db.session.query(CircleSubscription.user_id).filter(CircleSubscription.status == "active",
                                                               CircleSubscription.user_id.isnot(None))
    for user in User.query.filter(User.deletion_scheduled_for.is_(None), ~User.id.in_(paid)).all():
        if set(user.role_names()) - NON_STAFF_ROLES:
            continue  # staff accounts are never auto-deleted
        if deletion_blockers(user):
            continue
        yield user


def _purge_one(user, action, changes):
    """Purge one account inside a savepoint: a failure is logged and skipped
    so it can't stop the other accounts or the other retention rules."""
    from app.services.account_privacy import purge_user
    from app.services.audit import log_action

    uid = user.id
    try:
        with db.session.begin_nested():
            purge_user(user)
    except Exception:  # noqa: BLE001 - isolate one bad row; logged without personal data
        current_app.logger.exception("Retention: purge of one account failed (%s); skipped.", action)
        return False
    log_action(None, action, "User", uid, changes)
    return True


def _has_payments(user):
    from app.models.circle import CirclePayment, CircleSubscription
    from app.models.commerce import Order
    from app.models.resource import ResourcePayment, ResourcePurchase

    return any(db.session.query(m.id).filter(m.user_id == user.id).first() is not None
               for m in (CircleSubscription, CirclePayment, ResourcePurchase, ResourcePayment, Order))


def _unverified_accounts(now, s, dry_run):
    """New accounts registered under the verification-required flow whose
    email was never confirmed within unverifiedAccountDays. Accounts from
    before verification existed are never touched; nor staff, paid accounts
    or accounts with deletion blockers."""
    from app.models.user import User

    cutoff = now - timedelta(days=s["unverifiedAccountDays"])
    purged = 0
    rows = User.query.filter(User.email_verification_required.is_(True), User.email_verified_at.is_(None),
                             User.deletion_scheduled_for.is_(None), User.created_at < cutoff).all()
    candidates = {u.id for u in _inactive_candidates()} if rows else set()
    for user in rows:
        if user.id not in candidates or _has_payments(user):
            continue
        purged += 1
        if not dry_run and not _purge_one(user, "account.purged_unverified", {"days": s["unverifiedAccountDays"]}):
            purged -= 1
    return purged


def _inactive_accounts(now, s, dry_run):
    """Warn once, inactiveWarningDays before the deadline; delete only after
    a warning was handed off at least that long ago and the member still
    hasn't used the account. Using the account clears the warning."""
    from app.services.email import TRANSACTIONAL, send_email

    limit = _years(s["inactiveAccountYears"])
    warn = timedelta(days=s["inactiveWarningDays"])
    warned = purged = 0
    for user in list(_inactive_candidates()):
        active_at = last_activity(user)
        warned_at = user.inactivity_warning_sent_at
        warned_at = warned_at if warned_at is None or warned_at.tzinfo else warned_at.replace(tzinfo=timezone.utc)
        if warned_at is not None and active_at > warned_at:
            if not dry_run:
                user.inactivity_warning_sent_at = None  # came back: the warning no longer applies
            continue
        if active_at > now - (limit - warn):
            continue
        if warned_at is None:
            warned += 1
            if dry_run:
                continue
            base = current_app.config["FRONTEND_URL"].rstrip("/")
            deadline = (now + warn).strftime("%d %B %Y")
            if send_email(user.email, "Your Women Shaping Futures account will be deleted soon",
                          f"We haven't seen you on Women Shaping Futures for a long time. Unused accounts are deleted "
                          f"after {s['inactiveAccountYears']} years. To keep yours, just sign in before {deadline}:\n"
                          f"{base}/login\n", category=TRANSACTIONAL):
                user.inactivity_warning_sent_at = now
            continue
        if active_at <= now - limit and warned_at <= now - warn:
            purged += 1
            if not dry_run and not _purge_one(user, "account.purged_inactive",
                                              {"inactive_years": s["inactiveAccountYears"]}):
                purged -= 1
    return {"warned": warned, "purged": purged}


RULES = (
    ("analytics_events", _analytics),
    ("auth_ip_cleared", _auth_ip),
    ("contact_inquiries", _contact),
    ("declined_stories", _declined_stories),
    ("comment_ip_hashes", _comment_ip_hashes),
    ("password_reset_tokens", _reset_tokens),
    ("payment_records", _payments),
    ("consent_records", _consent),
    ("removed_comment_text", _removed_comment_text),
    ("inactive_accounts", _inactive_accounts),
    ("unverified_accounts", _unverified_accounts),
)


def run_retention(now=None, dry_run=False):
    """{rule: count} for every rule. Idempotent; a second run straight after
    finds nothing. dry_run counts without changing anything."""
    now = now or datetime.now(timezone.utc)
    settings = get_retention_settings()
    results = {}
    for name, rule in RULES:
        try:
            results[name] = rule(now, settings, dry_run)
        except Exception:  # noqa: BLE001 - one failing rule must not stop the others
            db.session.rollback()
            current_app.logger.exception("Retention rule %s failed; other rules continue.", name)
            results[name] = "error"
            continue
        if dry_run:
            db.session.rollback()
        else:
            db.session.commit()
    current_app.logger.info("Retention run%s: %s", " (dry run)" if dry_run else "", results)
    return results


LAST_RUN_KEY = "retention_last_run"
RUN_INTERVAL = timedelta(hours=23)


def run_retention_if_due(now=None):
    """For the every-few-minutes maintenance command: run at most once a day."""
    now = now or datetime.now(timezone.utc)
    row = db.session.get(SiteSetting, LAST_RUN_KEY)
    last = row.value.get("at") if row and isinstance(row.value, dict) else None
    if last and datetime.fromisoformat(last) > now - RUN_INTERVAL:
        return None
    results = run_retention(now)
    if row is None:
        db.session.add(SiteSetting(key=LAST_RUN_KEY, value={"at": now.isoformat()}))
    else:
        row.value = {"at": now.isoformat()}
    db.session.commit()
    return results
