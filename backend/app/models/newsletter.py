import secrets

from app.extensions import db

# WSF is the master subscriber and consent record (Step 14, provider-neutral;
# rules in app/services/newsletter.py):
#   pending             asked to subscribe (explicit checkbox consent) but has
#                       not clicked the confirmation link yet. NOT subscribed:
#                       never in an audience or an export.
#   active              confirmed by double opt-in (confirmed_at set). The only
#                       status that is exported or counted as an audience.
#   legacy_unconfirmed  subscribed before double opt-in existed; whether they
#                       ever confirmed is not known, so they are not exported
#                       until they confirm (a Studio "ask to confirm" email).
#   unsubscribed        suppressed: opted out (link, form, Studio, or an
#                       external sending service's unsubscribe import).
#   bounced/complained  suppressed for deliverability/complaint reasons.
# Suppressed addresses never return through an ordinary signup alone: only
# a fresh explicit signup AND a click on its confirmation link reactivates.
SUBSCRIBER_STATUSES = ("pending", "active", "legacy_unconfirmed", "unsubscribed", "bounced", "complained")
SUPPRESSED_STATUSES = ("unsubscribed", "bounced", "complained")
_SUBSCRIBER_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in SUBSCRIBER_STATUSES) + ")"

# WSF does not transmit newsletters itself; staff send them through an
# external service chosen as needed (provider-neutral).
#   draft     being written, not public.
#   ready     content final, ready to export (scheduled_at = planned date,
#             informational only — nothing sends automatically).
#   sent      staff recorded that it was SENT EXTERNALLY (a
#             newsletter_send_records row says where, when, to how many) —
#             the only status in the public archive.
#   archived  retired from the public archive; the record persists.
# "Exported" is not a status: each recipient export is its own send record.
ISSUE_STATUSES = ("draft", "ready", "sent", "archived")
_ISSUE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in ISSUE_STATUSES) + ")"

newsletter_subscriber_topics = db.Table(
    "newsletter_subscriber_topics",
    db.Column(
        "subscriber_id", db.Integer, db.ForeignKey("newsletter_subscribers.id", ondelete="CASCADE"), primary_key=True
    ),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)


def _generate_unsubscribe_token():
    return secrets.token_urlsafe(32)


class NewsletterSubscriber(db.Model):
    __tablename__ = "newsletter_subscribers"
    __table_args__ = (db.CheckConstraint(_SUBSCRIBER_STATUS_CHECK_SQL, name="ck_newsletter_subscribers_status"),)

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")
    # Where on the site they subscribed (footer/homepage/article-inline/...)
    # plus first-touch UTM + LinkedIn-referral attribution — see
    # frontend/src/utils/analytics.js withAcquisitionMetadata, which this
    # column's shape mirrors: {source, utmSource, utmMedium, utmCampaign,
    # referrer, isFromLinkedIn}.
    placement = db.Column(db.String(50))
    acquisition = db.Column(db.JSON)
    # An unguessable, stable, per-subscriber link secret — the ONLY thing
    # a one-click email unsubscribe link needs to carry, so a raw email
    # address or numeric id is never exposed as the unsubscribe mechanism.
    unsubscribe_token = db.Column(
        db.String(64), unique=True, nullable=False, index=True, default=_generate_unsubscribe_token
    )
    subscribed_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    unsubscribed_at = db.Column(db.DateTime(timezone=True))
    # Consent provenance (operational record, not legal proof): when the
    # visitor last gave signup consent and which wording version they saw
    # (engagement_settings.NEWSLETTER_CONSENT_VERSION). Where = `placement`.
    # Never an IP address or browser identity. NULL on rows from before
    # this was recorded.
    consent_at = db.Column(db.DateTime(timezone=True))
    consent_version = db.Column(db.String(40))
    # Where the consent now in force was given (the form's placement).
    consent_source = db.Column(db.String(50))
    # Double opt-in: when they clicked the confirmation link. NULL = never
    # confirmed through WSF (pending, or legacy_unconfirmed).
    confirmed_at = db.Column(db.DateTime(timezone=True))
    # How the last unsubscribe/suppression happened: "link", "form",
    # "studio", "external_import"; reason = provider name / staff note.
    unsubscribe_source = db.Column(db.String(40))
    unsubscribe_reason = db.Column(db.String(200))

    country = db.relationship("Country", foreign_keys=[country_code])
    interests = db.relationship("Topic", secondary=newsletter_subscriber_topics, backref="newsletter_subscribers")


class NewsletterIssue(db.Model):
    __tablename__ = "newsletter_issues"
    __table_args__ = (db.CheckConstraint(_ISSUE_STATUS_CHECK_SQL, name="ck_newsletter_issues_status"),)

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    issue_number = db.Column(db.Integer, nullable=True)
    # Internal name an editor uses to find this draft — distinct from the
    # `subject`, which is the actual email subject line.
    title = db.Column(db.String(200), nullable=False)
    subject = db.Column(db.String(300), nullable=False)
    preheader = db.Column(db.String(300))
    # Ordered content-block list — same shape/sanitizer as every other
    # content type in this app (see app/services/content_blocks.py). Block
    # types stay email-friendly: heading, paragraph, image, button, list,
    # blockquote/pullquote, divider, callout, articleCard, footerNote.
    content = db.Column(db.JSON, nullable=False, default=list)
    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    summary = db.Column(db.Text)  # short internal description / archive teaser
    featured_article_id = db.Column(db.Integer, db.ForeignKey("articles.id"), nullable=True)

    status = db.Column(db.String(20), nullable=False, default="draft")
    # Recipient segment. `null` means "all active subscribers". Shape:
    # {"topicSlugs": [...], "countryCodes": [...]} — both optional, ANDed
    # together; an empty/absent filter list means "don't filter on this".
    audience_filter = db.Column(db.JSON)

    # Scheduling metadata only — no worker/queue exists in this codebase to
    # act on it yet. `sent_at` is set only by an explicit admin "mark as
    # sent" action, never implied by any other status change.
    scheduled_at = db.Column(db.DateTime(timezone=True))
    send_timezone = db.Column(db.String(50), default="UTC")
    sent_at = db.Column(db.DateTime(timezone=True))

    # Small, optional email-provider boundary — populated later by
    # whichever provider integration connects to this CMS. Never required,
    # never coupled to a specific vendor's field shape.
    provider = db.Column(db.String(50))
    provider_campaign_id = db.Column(db.String(100))
    provider_message_id = db.Column(db.String(100))

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    featured_article = db.relationship("Article", foreign_keys=[featured_article_id])
    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])


class NewsletterConfirmation(db.Model):
    """One double-opt-in request: the consent given at signup, waiting for
    its link to be clicked. Only the SHA-256 of the link token is stored.
    A newer request for the same address supersedes older unconfirmed
    ones, so there is at most one usable link at a time."""

    __tablename__ = "newsletter_confirmations"

    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey("newsletter_subscribers.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    consent_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consent_version = db.Column(db.String(40), nullable=False)
    consent_source = db.Column(db.String(50))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    confirmed_at = db.Column(db.DateTime(timezone=True))
    superseded_at = db.Column(db.DateTime(timezone=True))

    subscriber = db.relationship("NewsletterSubscriber")


class NewsletterSubscriberEvent(db.Model):
    """Consent/suppression trail for one address: signup requested,
    confirmed, unsubscribed (and how), imported suppression, legacy mapping.
    Operational record; no IP address or browser data."""

    __tablename__ = "newsletter_subscriber_events"

    id = db.Column(db.Integer, primary_key=True)
    subscriber_id = db.Column(db.Integer, db.ForeignKey("newsletter_subscribers.id", ondelete="CASCADE"),
                              nullable=False, index=True)
    event = db.Column(db.String(40), nullable=False)
    source = db.Column(db.String(80))
    consent_version = db.Column(db.String(40))
    import_id = db.Column(db.Integer, db.ForeignKey("newsletter_suppression_imports.id", ondelete="SET NULL"))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)


class NewsletterSuppressionImport(db.Model):
    """One CSV of unsubscribes reported by an external sending service,
    applied to WSF (counts only; the addresses are on the events)."""

    __tablename__ = "newsletter_suppression_imports"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(200))
    rows = db.Column(db.Integer, nullable=False, default=0)
    invalid = db.Column(db.Integer, nullable=False, default=0)
    newly_suppressed = db.Column(db.Integer, nullable=False, default=0)
    already_suppressed = db.Column(db.Integer, nullable=False, default=0)
    added_unknown = db.Column(db.Integer, nullable=False, default=0)
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)


SEND_RECORD_KINDS = ("export", "external_send")


class NewsletterSendRecord(db.Model):
    """What staff did with an issue outside WSF: an "export" (recipient CSV
    downloaded) or an "external_send" (sent through the named external
    service). WSF never claims it transmitted the email itself."""

    __tablename__ = "newsletter_send_records"
    __table_args__ = (db.CheckConstraint("kind IN ('export', 'external_send')", name="ck_newsletter_send_records_kind"),)

    id = db.Column(db.Integer, primary_key=True)
    issue_id = db.Column(db.Integer, db.ForeignKey("newsletter_issues.id", ondelete="CASCADE"), nullable=False,
                         index=True)
    kind = db.Column(db.String(20), nullable=False)
    provider_name = db.Column(db.String(100))
    external_reference = db.Column(db.String(200))
    recipient_count = db.Column(db.Integer, nullable=False, default=0)
    occurred_at = db.Column(db.DateTime(timezone=True), nullable=False)
    note = db.Column(db.String(500))
    actor_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    actor = db.relationship("User")
