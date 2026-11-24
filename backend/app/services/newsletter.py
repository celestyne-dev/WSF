"""Newsletter subscriptions: WSF is the master subscriber and consent record
(Step 14, provider-neutral). Every flow that collects newsletter consent —
the newsletter forms, and the optional "also send me WSF Weekly" checkbox on
other forms — goes through request_subscription(); nothing else writes a
subscriber's status.

Double opt-in, controlled by WSF (no sending provider involved):
  1. explicit, unticked-by-default checkbox consent -> request_subscription():
     a new address becomes "pending"; a confirmation email (WSF's own
     transactional email service) carries a one-time link. Only the link
     token's SHA-256 is stored; links expire after CONFIRMATION_LIFETIME.
  2. the link -> confirm_subscription(): "active" with confirmed_at, and the
     consent (time, wording version, source) recorded on the subscriber.
     Clicking the same link again is a harmless "already confirmed".
Suppression is authoritative: unsubscribed/bounced/complained addresses
are never reactivated by a signup alone; a fresh signup sends a new
confirmation link and only clicking it reactivates. Every step is in
newsletter_subscriber_events.

Delivery is external: staff export confirmed subscribers (export_rows) and
record where they sent the issue (record_external_send). Unsubscribes
reported by that service come back through import_suppressions() (CSV).
A future provider API can implement DeliveryAdapter; none is built in.
"""
import csv
import hashlib
import io
import re
import secrets
from datetime import datetime, timedelta, timezone

from flask import current_app

from app.extensions import db
from app.models.newsletter import (
    SUPPRESSED_STATUSES,
    NewsletterConfirmation,
    NewsletterSendRecord,
    NewsletterSubscriber,
    NewsletterSubscriberEvent,
    NewsletterSuppressionImport,
)
from app.models.taxonomy import Topic

CONFIRMATION_LIFETIME = timedelta(days=7)
# A repeat signup for the same address within this window does not send
# another email (stops anyone using the form to flood someone's inbox).
RESEND_INTERVAL = timedelta(minutes=10)
RECONFIRM_CONSENT_VERSION = "newsletter-reconfirm-v1"
MAX_IMPORT_ROWS = 50000
EXPORT_COLUMNS = ("email", "first_name", "last_name")
_EMAIL_RE = re.compile(r"^[^@\s,;<>\"']+@[^@\s,;<>\"']+\.[^@\s,;<>\"']+$")


class NewsletterError(Exception):
    def __init__(self, message, status=400, code="newsletter_error"):
        super().__init__(message)
        self.status = status
        self.code = code


def _now():
    return datetime.now(timezone.utc)


def _aware(value):
    return value if value is None or value.tzinfo else value.replace(tzinfo=timezone.utc)


def _hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_email(value):
    if not isinstance(value, str):
        return None
    email = value.strip().strip('"').strip("'").strip().lower()
    return email if len(email) <= 254 and _EMAIL_RE.match(email) else None


def _event(subscriber, event, source=None, consent_version=None, actor=None, import_id=None):
    db.session.add(NewsletterSubscriberEvent(
        subscriber_id=subscriber.id, event=event, source=source, consent_version=consent_version,
        actor_id=actor.id if actor is not None else None, import_id=import_id))


# --- signup + double opt-in --------------------------------------------------------------------


def request_subscription(email, *, consent_version, first_name=None, last_name=None, country_code=None,
                         placement=None, acquisition=None, topic_slugs=None):
    """Record an explicit consent request and send the confirmation link.
    Returns (subscriber, outcome): "confirmation_sent", "recently_sent"
    (a link went out minutes ago), or "already_subscribed". Never makes an
    address active. The caller has already checked the consent checkbox and
    commits afterwards."""
    email = normalize_email(email)
    if email is None:
        raise NewsletterError("Please enter a valid email address.", 422, "validation_error")
    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    if subscriber is None:
        subscriber = NewsletterSubscriber(email=email, status="pending", placement=placement, acquisition=acquisition)
        db.session.add(subscriber)
        db.session.flush()
    # Contact details and interests are kept current either way.
    subscriber.first_name = first_name or subscriber.first_name
    subscriber.last_name = last_name or subscriber.last_name
    subscriber.country_code = country_code or subscriber.country_code
    if topic_slugs:
        existing = {t.slug for t in subscriber.interests}
        new = [s for s in topic_slugs if s not in existing]
        if new:
            subscriber.interests.extend(Topic.query.filter(Topic.slug.in_(new)).all())
    if subscriber.status == "active":
        return subscriber, "already_subscribed"
    _event(subscriber, "signup_requested", source=placement, consent_version=consent_version)
    latest = (NewsletterConfirmation.query
              .filter_by(subscriber_id=subscriber.id, confirmed_at=None, superseded_at=None)
              .order_by(NewsletterConfirmation.created_at.desc()).first())
    if latest is not None and _aware(latest.created_at) > _now() - RESEND_INTERVAL:
        return subscriber, "recently_sent"
    _send_confirmation(subscriber, consent_version=consent_version, source=placement)
    return subscriber, "confirmation_sent"


def _send_confirmation(subscriber, *, consent_version, source, reconfirm=False):
    now = _now()
    NewsletterConfirmation.query.filter_by(subscriber_id=subscriber.id, confirmed_at=None, superseded_at=None).update(
        {"superseded_at": now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    db.session.add(NewsletterConfirmation(
        subscriber_id=subscriber.id, token_hash=_hash(raw), consent_at=now, consent_version=consent_version,
        consent_source=source, expires_at=now + CONFIRMATION_LIFETIME))
    db.session.flush()
    from app.services.email import send_email

    base = current_app.config["FRONTEND_URL"].rstrip("/")
    link = f"{base}/newsletter/confirm/{raw}"
    days = CONFIRMATION_LIFETIME.days
    if reconfirm:
        subject = "Please confirm you'd like to keep receiving WSF Weekly"
        intro = ("You're on the Women Shaping Futures newsletter list from before we started asking every reader "
                 "to confirm. Please confirm you'd like to keep receiving WSF Weekly by email:")
        tail = "If you don't confirm, we won't send you the newsletter."
    else:
        subject = "Please confirm your WSF Weekly subscription"
        intro = "Someone (we hope you) asked to receive the WSF Weekly newsletter from Women Shaping Futures at this address. Please confirm:"
        tail = "If this wasn't you, ignore this email: you won't be subscribed."
    text = (f"{intro}\n\n{link}\n\nThis link works for {days} days. {tail}\n\n"
            f"How we use your email: {base}/privacy\n")
    send_email(subscriber.email, subject, text)


def confirm_subscription(raw_token):
    """Returns "confirmed", "already_confirmed", "expired" or "invalid"."""
    if not raw_token or not isinstance(raw_token, str) or len(raw_token) > 100:
        return "invalid"
    row = NewsletterConfirmation.query.filter_by(token_hash=_hash(raw_token)).first()
    if row is None:
        return "invalid"
    subscriber = row.subscriber
    if row.confirmed_at is not None:
        return "already_confirmed"
    if row.superseded_at is not None:
        # A newer link was sent; this one no longer works. (If they already
        # confirmed through the newer one, say so.)
        return "already_confirmed" if subscriber.status == "active" else "invalid"
    if _aware(row.expires_at) <= _now():
        return "expired"
    now = _now()
    row.confirmed_at = now
    previous = subscriber.status
    subscriber.status = "active"
    subscriber.confirmed_at = now
    subscriber.consent_at = row.consent_at
    subscriber.consent_version = row.consent_version
    subscriber.consent_source = row.consent_source
    if previous != "legacy_unconfirmed":
        subscriber.subscribed_at = now  # a legacy row keeps its original signup date
    subscriber.unsubscribed_at = None
    subscriber.unsubscribe_source = None
    subscriber.unsubscribe_reason = None
    _event(subscriber, "reactivated_by_confirmation" if previous in SUPPRESSED_STATUSES else "confirmed",
           source=row.consent_source, consent_version=row.consent_version)
    db.session.commit()
    return "confirmed"


def request_reconfirmation(subscriber, actor):
    """Studio: ask a legacy_unconfirmed subscriber to confirm (they consented
    before double opt-in existed). Never for suppressed addresses."""
    if subscriber.status != "legacy_unconfirmed":
        raise NewsletterError("Only legacy (unconfirmed) subscribers can be asked to confirm.", 409,
                              "not_legacy")
    _event(subscriber, "reconfirmation_requested", source="studio", actor=actor)
    _send_confirmation(subscriber, consent_version=RECONFIRM_CONSENT_VERSION, source="reconfirmation",
                       reconfirm=True)


# --- unsubscribe / suppression -----------------------------------------------------------------


def unsubscribe(subscriber, source, reason=None, actor=None):
    """Suppress an address. Idempotent; pending links stop working too."""
    changed = subscriber.status not in SUPPRESSED_STATUSES
    if changed:
        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = _now()
        subscriber.unsubscribe_source = source
        subscriber.unsubscribe_reason = (reason or None) and reason[:200]
        _event(subscriber, "unsubscribed", source=source if not reason else f"{source}: {reason}"[:80], actor=actor)
    NewsletterConfirmation.query.filter_by(subscriber_id=subscriber.id, confirmed_at=None, superseded_at=None).update(
        {"superseded_at": _now()}, synchronize_session=False)
    return changed


def _parse_import(text):
    """Emails from a provider's unsubscribe CSV: the "email"/"Email Address"
    column when there is a header, otherwise the first column."""
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if not rows:
        return []
    header = [c.strip().lower() for c in rows[0]]
    column, start = 0, 0
    for i, name in enumerate(header):
        if name in ("email", "email address", "e-mail", "email_address", "emailaddress"):
            column, start = i, 1
            break
    else:
        if normalize_email(rows[0][0]) is None and "@" not in rows[0][0]:
            start = 1  # an unrecognised header line
    return [row[column] if column < len(row) else "" for row in rows[start:]]


def import_suppressions(provider, text, filename, actor):
    """Apply an external sending service's unsubscribe list. Unknown
    addresses are recorded as unsubscribed too, so they can never be
    exported later. Never reactivates anything; safe to repeat."""
    provider = (provider or "").strip()
    if not provider or len(provider) > 100:
        raise NewsletterError("Name the service the list came from.", 422, "validation_error")
    values = _parse_import(text or "")
    if len(values) > MAX_IMPORT_ROWS:
        raise NewsletterError(f"Please split files over {MAX_IMPORT_ROWS} rows.", 422, "validation_error")
    batch = NewsletterSuppressionImport(provider=provider, filename=(filename or "")[:200] or None,
                                        actor_id=actor.id if actor else None)
    db.session.add(batch)
    db.session.flush()
    seen = set()
    for value in values:
        batch.rows += 1
        email = normalize_email(value)
        if email is None:
            batch.invalid += 1
            continue
        if email in seen:
            batch.already_suppressed += 1
            continue
        seen.add(email)
        subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
        if subscriber is None:
            subscriber = NewsletterSubscriber(email=email, status="unsubscribed", unsubscribed_at=_now(),
                                              unsubscribe_source="external_import", unsubscribe_reason=provider,
                                              placement="external-suppression")
            db.session.add(subscriber)
            db.session.flush()
            _event(subscriber, "suppressed_by_import", source=provider[:80], actor=actor, import_id=batch.id)
            batch.added_unknown += 1
        elif subscriber.status in SUPPRESSED_STATUSES:
            batch.already_suppressed += 1
        else:
            unsubscribe(subscriber, "external_import", reason=provider, actor=actor)
            _event(subscriber, "suppressed_by_import", source=provider[:80], actor=actor, import_id=batch.id)
            batch.newly_suppressed += 1
    db.session.commit()
    return batch


# --- export + external sends -------------------------------------------------------------------


def audience_query(audience_filter):
    """Confirmed, currently active subscribers, optionally segmented:
    {"topicSlugs": [...], "countryCodes": [...]} (ANDed). The one query both
    the audience estimate and every export use, so they never disagree."""
    query = NewsletterSubscriber.query.filter(NewsletterSubscriber.status == "active",
                                              NewsletterSubscriber.confirmed_at.isnot(None))
    audience_filter = audience_filter or {}
    topic_slugs = audience_filter.get("topicSlugs") or []
    if topic_slugs:
        query = query.filter(NewsletterSubscriber.interests.any(Topic.slug.in_(topic_slugs)))
    country_codes = audience_filter.get("countryCodes") or []
    if country_codes:
        query = query.filter(NewsletterSubscriber.country_code.in_(country_codes))
    return query


def count_audience(audience_filter):
    return audience_query(audience_filter).count()


def export_csv(audience_filter=None):
    """(csv text, row count): delivery fields only — no ids, IP data or
    consent internals."""
    rows = audience_query(audience_filter).order_by(NewsletterSubscriber.email.asc()).all()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for s in rows:
        writer.writerow([s.email, s.first_name or "", s.last_name or ""])
    return buffer.getvalue(), len(rows)


def record_export(issue, count, actor):
    db.session.add(NewsletterSendRecord(issue_id=issue.id, kind="export", recipient_count=count,
                                        occurred_at=_now(), actor_id=actor.id))
    db.session.commit()


def record_external_send(issue, *, provider_name, recipient_count, external_reference=None, sent_at=None,
                         note=None, actor):
    """Staff record that the issue was SENT EXTERNALLY. WSF did not send it."""
    provider_name = (provider_name or "").strip()
    if not provider_name or len(provider_name) > 100:
        raise NewsletterError("Name the service you sent it with.", 422, "validation_error")
    if isinstance(recipient_count, bool) or not isinstance(recipient_count, int) or not 0 <= recipient_count <= 10_000_000:
        raise NewsletterError("Recipient count must be a whole number.", 422, "validation_error")
    sent_at = _aware(sent_at) or _now()
    if sent_at > _now() + timedelta(minutes=5):
        raise NewsletterError("The send time can't be in the future.", 422, "validation_error")
    reference = (external_reference or "").strip()[:200] or None
    record = NewsletterSendRecord(issue_id=issue.id, kind="external_send", provider_name=provider_name,
                                  external_reference=reference, recipient_count=recipient_count,
                                  occurred_at=sent_at, note=(note or "").strip()[:500] or None, actor_id=actor.id)
    db.session.add(record)
    issue.status = "sent"
    issue.sent_at = sent_at
    issue.provider = provider_name[:50]
    issue.provider_campaign_id = reference[:100] if reference else None
    db.session.commit()
    return record


class DeliveryAdapter:
    """Boundary for an OPTIONAL future sending-service API. None is
    implemented: WSF exports confirmed subscribers and staff record external
    sends. An adapter would push export_csv()-equivalent data and pull
    unsubscribes into import_suppressions(); WSF stays the master record."""

    name = None

    def push_audience(self, subscribers):  # pragma: no cover - interface only
        raise NotImplementedError

    def pull_unsubscribes(self):  # pragma: no cover - interface only
        raise NotImplementedError


def request_subscription_safely(email, **kwargs):
    """For the optional "also send me WSF Weekly" checkbox on other forms:
    the same double opt-in, but a newsletter problem never fails the form
    the person actually submitted."""
    try:
        return request_subscription(email, **kwargs)
    except NewsletterError:
        return None, "invalid"
