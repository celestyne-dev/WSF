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
    (a link went out minutes ago), "already_subscribed", or
    "confirmation_failed" (the email service reported a failure). Never makes
    an address active, and never changes an existing subscriber's name,
    country or interests: the details typed in are held on the confirmation
    and applied only when its link is confirmed. Caller commits."""
    email = normalize_email(email)
    if email is None:
        raise NewsletterError("Please enter a valid email address.", 422, "validation_error")
    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    if subscriber is None:
        subscriber = NewsletterSubscriber(email=email, status="pending", placement=placement, acquisition=acquisition)
        db.session.add(subscriber)
        db.session.flush()
    if subscriber.status == "active":
        return subscriber, "already_subscribed"
    proposed = {k: v for k, v in (("first_name", first_name), ("last_name", last_name),
                                  ("country_code", country_code), ("topic_slugs", list(topic_slugs or []))) if v}
    _event(subscriber, "signup_requested", source=placement, consent_version=consent_version)
    latest = (NewsletterConfirmation.query
              .filter_by(subscriber_id=subscriber.id, confirmed_at=None, superseded_at=None)
              .order_by(NewsletterConfirmation.created_at.desc()).first())
    if latest is not None and _aware(latest.created_at) > _now() - RESEND_INTERVAL:
        return subscriber, "recently_sent"
    if not _send_confirmation(subscriber, consent_version=consent_version, source=placement, proposed=proposed):
        return subscriber, "confirmation_failed"
    return subscriber, "confirmation_sent"


def _apply_profile(subscriber, proposed):
    proposed = proposed or {}
    for field in ("first_name", "last_name", "country_code"):
        if proposed.get(field):
            setattr(subscriber, field, proposed[field])
    slugs = [s for s in proposed.get("topic_slugs") or [] if isinstance(s, str)]
    if slugs:
        existing = {t.slug for t in subscriber.interests}
        new = [s for s in slugs if s not in existing]
        if new:
            subscriber.interests.extend(Topic.query.filter(Topic.slug.in_(new)).all())


def _send_confirmation(subscriber, *, consent_version, source, reconfirm=False, proposed=None):
    """Returns True only if the email service reported a successful hand-off.
    On failure the new link is withdrawn at once (nothing live is left that
    the person never received, and they can retry immediately)."""
    now = _now()
    NewsletterConfirmation.query.filter_by(subscriber_id=subscriber.id, confirmed_at=None, superseded_at=None).update(
        {"superseded_at": now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    row = NewsletterConfirmation(
        subscriber_id=subscriber.id, token_hash=_hash(raw), consent_at=now, consent_version=consent_version,
        consent_source=source, expires_at=now + CONFIRMATION_LIFETIME, proposed_profile=proposed or None)
    db.session.add(row)
    db.session.flush()
    from app.services.email import TRANSACTIONAL, send_email

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
    text = (f"{intro}\n\n{link}\n\nOpen the link and press the button to confirm. It works for {days} days. {tail}\n\n"
            f"How we use your email: {base}/privacy\n")
    # Transactional: it answers the person's own signup request.
    if send_email(subscriber.email, subject, text, category=TRANSACTIONAL):
        return True
    row.superseded_at = now
    _event(subscriber, "confirmation_send_failed", source=source, consent_version=consent_version)
    return False


HARD_SUPPRESSIONS = ("bounced", "complained")


def _usable(row, subscriber):
    """A confirmation can act only if it is still the live link and was
    issued after the address's latest suppression event."""
    if row.superseded_at is not None or row.confirmed_at is not None:
        return False
    last = _aware(subscriber.last_suppressed_at)
    return last is None or _aware(row.consent_at) > last


def confirm_subscription(raw_token):
    """Returns "confirmed", "already_confirmed", "review_required" (a bounced
    or complained address: consent recorded, delivery stays off until an
    audited deliverability review), "expired" or "invalid". The subscriber
    and confirmation rows are locked, so a suppression committed at the same
    time can't be overridden by a stale link."""
    if not raw_token or not isinstance(raw_token, str) or len(raw_token) > 100:
        return "invalid"
    row = NewsletterConfirmation.query.filter_by(token_hash=_hash(raw_token)).first()
    if row is None:
        return "invalid"
    subscriber = (NewsletterSubscriber.query.filter_by(id=row.subscriber_id)
                  .with_for_update().populate_existing().one())
    row = NewsletterConfirmation.query.filter_by(id=row.id).with_for_update().populate_existing().one()
    if row.confirmed_at is not None:
        return "already_confirmed" if subscriber.status == "active" else (
            "review_required" if subscriber.status in HARD_SUPPRESSIONS and _usable_for_review(row, subscriber)
            else "invalid")
    if not _usable(row, subscriber):
        # A newer link was sent, or the address was suppressed after this
        # link went out: it no longer works.
        return "already_confirmed" if subscriber.status == "active" else "invalid"
    if _aware(row.expires_at) <= _now():
        return "expired"
    now = _now()
    row.confirmed_at = now
    previous = subscriber.status
    if previous in HARD_SUPPRESSIONS:
        # Fresh consent is recorded, but a hard bounce/complaint also needs an
        # audited deliverability review before anything is sent again.
        _event(subscriber, "reactivation_confirmed_awaiting_review", source=row.consent_source,
               consent_version=row.consent_version)
        db.session.commit()
        return "review_required"
    _activate(subscriber, row, previous, now)
    _event(subscriber, "reactivated_by_confirmation" if previous in SUPPRESSED_STATUSES else "confirmed",
           source=row.consent_source, consent_version=row.consent_version)
    db.session.commit()
    return "confirmed"


def _activate(subscriber, row, previous, now):
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
    _apply_profile(subscriber, row.proposed_profile)


def _usable_for_review(row, subscriber):
    last = _aware(subscriber.last_suppressed_at)
    return row.superseded_at is None and row.confirmed_at is not None and (last is None or _aware(row.consent_at) > last)


def approve_after_deliverability_review(subscriber, actor, note):
    """Studio: reactivate a bounced/complained address ONLY when the person
    has already given fresh consent and confirmed it (a confirmed link issued
    after the latest suppression). Staff approval alone never subscribes
    anyone; it records the deliverability review. Caller audits + commits."""
    note = (note or "").strip()
    if subscriber.status not in HARD_SUPPRESSIONS:
        raise NewsletterError("Only bounced or complained addresses need a deliverability review.", 409, "not_hard_suppressed")
    if not note:
        raise NewsletterError("Describe the deliverability review (what was checked).", 422, "validation_error")
    subscriber = (NewsletterSubscriber.query.filter_by(id=subscriber.id).with_for_update().populate_existing().one())
    row = (NewsletterConfirmation.query.filter(NewsletterConfirmation.subscriber_id == subscriber.id,
                                               NewsletterConfirmation.confirmed_at.isnot(None),
                                               NewsletterConfirmation.superseded_at.is_(None))
           .order_by(NewsletterConfirmation.confirmed_at.desc()).with_for_update().first())
    if row is None or not _usable_for_review(row, subscriber):
        raise NewsletterError("The person hasn't given and confirmed fresh consent since this address was suppressed. "
                              "Staff approval can't replace their consent.", 409, "consent_confirmation_required")
    previous = subscriber.status
    _activate(subscriber, row, previous, _now())
    _event(subscriber, "deliverability_review_approved", source=f"studio: {note}"[:80], actor=actor,
           consent_version=row.consent_version)
    return subscriber


def request_reconfirmation(subscriber, actor):
    """Studio: ask a legacy_unconfirmed subscriber to confirm (they consented
    before double opt-in existed). Never for suppressed addresses."""
    if subscriber.status != "legacy_unconfirmed":
        raise NewsletterError("Only legacy (unconfirmed) subscribers can be asked to confirm.", 409,
                              "not_legacy")
    _event(subscriber, "reconfirmation_requested", source="studio", actor=actor)
    if not _send_confirmation(subscriber, consent_version=RECONFIRM_CONSENT_VERSION, source="reconfirmation",
                              reconfirm=True):
        raise NewsletterError("The confirmation email could not be sent. Nothing was changed; try again later.",
                              503, "email_send_failed")


# --- unsubscribe / suppression -----------------------------------------------------------------


SUPPRESSION_RANK = {"unsubscribed": 1, "bounced": 2, "complained": 3}


def record_suppression_event(subscriber, now=None):
    """Every suppression event, even for an address already suppressed:
    stamp it and withdraw every outstanding confirmation link, so no link
    issued before it can ever reactivate the address."""
    now = now or _now()
    subscriber.last_suppressed_at = now
    NewsletterConfirmation.query.filter_by(subscriber_id=subscriber.id, confirmed_at=None, superseded_at=None).update(
        {"superseded_at": now}, synchronize_session=False)
    # A confirmed-but-unreviewed reactivation of a hard suppression is void too.
    NewsletterConfirmation.query.filter(NewsletterConfirmation.subscriber_id == subscriber.id,
                                        NewsletterConfirmation.confirmed_at.isnot(None),
                                        NewsletterConfirmation.superseded_at.is_(None)).update(
        {"superseded_at": now}, synchronize_session=False)


def unsubscribe(subscriber, source, reason=None, actor=None, kind="unsubscribed"):
    """Suppress an address. Idempotent; pending links stop working too.
    kind: "unsubscribed" (ordinary), "bounced" (hard bounce) or "complained";
    a stronger classification replaces a weaker one, never the reverse."""
    if kind not in SUPPRESSION_RANK:
        raise NewsletterError("Unknown suppression type.", 422, "validation_error")
    now = _now()
    current = SUPPRESSION_RANK.get(subscriber.status, 0)
    changed = SUPPRESSION_RANK[kind] > current
    if changed:
        subscriber.status = kind
        subscriber.unsubscribed_at = subscriber.unsubscribed_at if current else now
        subscriber.unsubscribe_source = source
        subscriber.unsubscribe_reason = (reason or None) and reason[:200]
        _event(subscriber, kind, source=source if not reason else f"{source}: {reason}"[:80], actor=actor)
    record_suppression_event(subscriber, now)
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


def import_suppressions(provider, text, filename, actor, kind="unsubscribed"):
    """Apply an external sending service's suppression list (kind:
    unsubscribed / bounced / complained). Unknown addresses are recorded as
    suppressed too, so they can never be exported later. Every listed address
    gets a suppression event (outstanding links withdrawn) even if it was
    already suppressed. Never reactivates anything; safe to repeat."""
    if kind not in SUPPRESSION_RANK:
        raise NewsletterError("Choose unsubscribes, hard bounces or complaints.", 422, "validation_error")
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
        # Row lock: a confirmation click racing this import waits for it.
        subscriber = NewsletterSubscriber.query.filter_by(email=email).with_for_update().first()
        if subscriber is None:
            now = _now()
            subscriber = NewsletterSubscriber(email=email, status=kind, unsubscribed_at=now, last_suppressed_at=now,
                                              unsubscribe_source="external_import", unsubscribe_reason=provider,
                                              placement="external-suppression")
            db.session.add(subscriber)
            db.session.flush()
            _event(subscriber, "suppressed_by_import", source=provider[:80], actor=actor, import_id=batch.id)
            batch.added_unknown += 1
            continue
        was_suppressed = subscriber.status in SUPPRESSED_STATUSES
        unsubscribe(subscriber, "external_import", reason=provider, actor=actor, kind=kind)
        _event(subscriber, "suppressed_by_import", source=provider[:80], actor=actor, import_id=batch.id)
        if was_suppressed:
            batch.already_suppressed += 1
        else:
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
