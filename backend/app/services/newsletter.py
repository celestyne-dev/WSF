"""The single place newsletter consent is ever recorded or subscription
status is ever changed. Any flow that captures explicit newsletter
consent — the public /newsletter/subscribe form, the Resources
email-gate's optional "also subscribe me" checkbox, or any future one —
must call upsert_subscriber() rather than writing to NewsletterSubscriber
directly, so the suppression/resubscribe rules below are enforced
consistently everywhere.
"""
from app.extensions import db
from app.models.newsletter import NewsletterSubscriber
from app.models.taxonomy import Topic

# Statuses an ordinary explicit subscribe action is allowed to clear back
# to "active". bounced/complained are reserved for a future email-provider
# webhook and must never be silently cleared by a plain signup — a
# deliverability suppression needs a deliberate admin decision, not an
# ordinary re-submission of the same signup form.
_REACTIVATABLE_STATUSES = ("unsubscribed",)


def upsert_subscriber(
    email,
    first_name=None,
    last_name=None,
    country_code=None,
    placement=None,
    acquisition=None,
    topic_slugs=None,
):
    """Create or update a subscriber record from an explicit consent
    action. Returns (subscriber, created, reactivated).
    """
    email = email.strip().lower()
    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    created = subscriber is None
    reactivated = False

    if subscriber is None:
        subscriber = NewsletterSubscriber(email=email)
        db.session.add(subscriber)
    elif subscriber.status in _REACTIVATABLE_STATUSES:
        reactivated = True

    if created or subscriber.status in _REACTIVATABLE_STATUSES:
        subscriber.status = "active"
        subscriber.unsubscribed_at = None
    # A bounced/complained subscriber's contact details below are still
    # updated (so a later admin review has current info) but their
    # suppressed status is left untouched by this ordinary signup.

    subscriber.first_name = first_name or subscriber.first_name
    subscriber.last_name = last_name or subscriber.last_name
    subscriber.country_code = country_code or subscriber.country_code
    subscriber.placement = placement or subscriber.placement
    subscriber.acquisition = acquisition or subscriber.acquisition

    if topic_slugs:
        existing_slugs = {t.slug for t in subscriber.interests}
        new_slugs = [s for s in topic_slugs if s not in existing_slugs]
        if new_slugs:
            found = Topic.query.filter(Topic.slug.in_(new_slugs)).all()
            subscriber.interests.extend(found)

    return subscriber, created, reactivated


def audience_query(audience_filter):
    """The one place a newsletter issue's `audience_filter` is turned into
    an actual subscriber query — shared by the live "estimated recipients"
    count and (later) whatever actually resolves a send list, so the two
    can never disagree. `audience_filter` is `None`/`{}` for "all active
    subscribers", or {"topicSlugs": [...], "countryCodes": [...]}, both
    optional and ANDed together.
    """
    query = NewsletterSubscriber.query.filter_by(status="active")
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
