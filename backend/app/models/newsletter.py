import secrets

from app.extensions import db

# active: receiving newsletter sends. unsubscribed: opted out by their own
# action (recoverable via an ordinary explicit resubscribe). bounced /
# complained: suppressed for deliverability/compliance reasons — reserved
# for a future email-provider webhook to set; nothing in this codebase
# sets them yet, but an ordinary public subscribe must never silently
# clear them (see services/newsletter.py::upsert_subscriber).
SUBSCRIBER_STATUSES = ("active", "unsubscribed", "bounced", "complained")
_SUBSCRIBER_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in SUBSCRIBER_STATUSES) + ")"

# draft: being written, not visible anywhere publicly. scheduled: content
# finalized and a scheduled_at set, awaiting either a future provider/
# worker integration or a manual "mark sent" action — no automated
# delivery exists in this codebase. sent: an admin has explicitly marked
# this issue as sent (an honest manual record, not a claim that this app
# delivered it) — the only status that appears in the public archive.
# archived: retired from the public archive; the record itself persists.
ISSUE_STATUSES = ("draft", "scheduled", "sent", "archived")
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
