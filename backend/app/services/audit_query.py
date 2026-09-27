"""Read-side support for the Admin Audit Log: human-readable action
labels, presentation-level categories, and a controlled entity-label
resolver. Nothing here writes to AuditLog (see app/services/audit.py for
that) — this module only helps display existing rows.

Action strings and entity_type strings are never rewritten — both stay
exactly as every existing log_action(...) call site already wrote them
(some pre-date this module and use snake_case action names or lowercase
entity_type strings; both are matched verbatim below rather than
normalized, so historical rows keep displaying correctly).
"""

import re

from app.models.article import Article
from app.models.cms import AdvertiseMetric, AdvertiseOffering, Menu
from app.models.commerce import Order, PartnershipInquiry, Sponsor
from app.models.community import Member
from app.models.mentorship import MentorshipApplication, MentorshipProgram
from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
from app.models.nominations import Nomination
from app.models.page import Page
from app.models.submissions import StorySubmission
from app.models.taxonomy import Category, Series, Tag, Topic
from app.models.user import User

# A friendlier fallback than the raw entity_type string for cases with no
# per-row label of their own (a singleton config object) or where
# entity_id is None (site-config actions that touch the whole
# collection rather than one row — see admin.py's homepage/navigation/
# footer.publish calls).
ENTITY_TYPE_DISPLAY_NAMES = {
    "HomepageModule": "Homepage",
    "Menu": "Navigation/Footer",
    "SiteSetting": "Site Settings",
    "CommunityPage": "Community Page",
    "AdvertisePage": "Advertise Page",
    "MentorshipMatch": "Mentorship Match",
    "nomination": "Nomination",
    "story_submission": "Story Submission",
}


def _label_lookup(model, attr):
    def resolver(ids):
        rows = model.query.filter(model.id.in_(ids)).all()
        return {row.id: getattr(row, attr) for row in rows}

    return resolver


def _label_lookup_fn(model, fn):
    def resolver(ids):
        rows = model.query.filter(model.id.in_(ids)).all()
        return {row.id: fn(row) for row in rows}

    return resolver


# entity_type string (exactly as stored) -> callable(list[int]) -> {id: label}.
# Deliberately explicit and bounded — one query per distinct type per
# audit-log page, never a dynamic introspection of an arbitrary table
# (see spec: "Do not dynamically introspect arbitrary tables").
_ENTITY_LABEL_RESOLVERS = {
    "Article": _label_lookup(Article, "title"),
    "Page": _label_lookup(Page, "title"),
    "Topic": _label_lookup(Topic, "name"),
    "Category": _label_lookup(Category, "name"),
    "Series": _label_lookup(Series, "name"),
    "Tag": _label_lookup(Tag, "name"),
    "User": _label_lookup_fn(User, lambda u: u.full_name or u.email),
    "NewsletterIssue": _label_lookup(NewsletterIssue, "title"),
    "NewsletterSubscriber": _label_lookup(NewsletterSubscriber, "email"),
    "PartnershipInquiry": _label_lookup_fn(PartnershipInquiry, lambda p: f"{p.company} ({p.contact_name})"),
    "Sponsor": _label_lookup(Sponsor, "campaign_name"),
    "Order": _label_lookup(Order, "reference"),
    "Member": _label_lookup_fn(Member, lambda m: m.full_name),
    "MentorshipProgram": _label_lookup(MentorshipProgram, "name"),
    "MentorshipApplication": _label_lookup_fn(MentorshipApplication, lambda a: a.full_name),
    "AdvertiseMetric": _label_lookup(AdvertiseMetric, "label"),
    "AdvertiseOffering": _label_lookup(AdvertiseOffering, "name"),
    "nomination": _label_lookup_fn(Nomination, lambda n: n.reference or n.nominee_name),
    "story_submission": _label_lookup_fn(StorySubmission, lambda s: s.reference or s.title),
    "Menu": _label_lookup_fn(Menu, lambda m: m.heading or m.key),
}


def resolve_entity_labels(entries):
    """Batch-resolve {(entity_type, entity_id): label} for a page of
    AuditLog rows — at most one query per distinct entity_type present on
    the page (never per-row), and a row whose target has since been
    deleted simply gets no label (falls back to the generic "Type #id"
    the caller applies), never an error.
    """
    ids_by_type = {}
    for entry in entries:
        if entry.entity_id is None:
            continue
        resolver = _ENTITY_LABEL_RESOLVERS.get(entry.entity_type)
        if resolver is None:
            continue
        if not entry.entity_id.isdigit():
            continue
        ids_by_type.setdefault(entry.entity_type, set()).add(int(entry.entity_id))

    labels = {}
    for entity_type, ids in ids_by_type.items():
        resolver = _ENTITY_LABEL_RESOLVERS[entity_type]
        for entity_id, label in resolver(ids).items():
            if label:
                labels[(entity_type, str(entity_id))] = label
    return labels


def entity_label_for(entry, resolved_labels):
    if entry.entity_id is not None:
        resolved = resolved_labels.get((entry.entity_type, entry.entity_id))
        if resolved:
            return resolved
        return f"{ENTITY_TYPE_DISPLAY_NAMES.get(entry.entity_type, entry.entity_type)} #{entry.entity_id}"
    return ENTITY_TYPE_DISPLAY_NAMES.get(entry.entity_type, entry.entity_type)


# Human-readable labels for the actions actually in use across the
# backend (see every log_action(...) call site) — kept as a lookup table
# rather than a live introspection so a typo'd/removed action can never
# throw, and so the mapping is reviewable in one place. Anything not
# listed falls back to _humanize_action() below rather than showing a
# raw slug.
ACTION_LABELS = {
    "user.register": "Registered account",
    "user.login": "Logged in",
    "user.create": "Created staff account",
    "user.update": "Updated staff profile",
    "user.activate": "Activated account",
    "user.deactivate": "Deactivated account",
    "user.roles_update": "Updated roles",
    "user.password_reset": "Reset password",
    "article.create": "Created article",
    "article.update": "Updated article",
    "article.publish": "Published article",
    "page.create": "Created page",
    "page.update": "Updated page",
    "page.delete": "Deleted page",
    "page.status_change": "Changed page status",
    "page.reviewed": "Reviewed page",
    "settings.update": "Updated site settings",
    "homepage.publish": "Published homepage",
    "navigation.publish": "Published navigation",
    "footer.publish": "Published footer",
    "topic.create": "Created topic",
    "topic.update": "Updated topic",
    "topic.delete": "Deleted topic",
    "topic.status_change": "Changed topic status",
    "category.create": "Created category",
    "category.update": "Updated category",
    "category.delete": "Deleted category",
    "category.status_change": "Changed category status",
    "series.create": "Created series",
    "series.update": "Updated series",
    "series.delete": "Deleted series",
    "series.status_change": "Changed series status",
    "tag.create": "Created tag",
    "tag.update": "Updated tag",
    "tag.delete": "Deleted tag",
    "partnership.update": "Updated partnership",
    "partnership.status_change": "Changed partnership status",
    "partnership.assign": "Assigned partnership",
    "partnership.organization_link": "Linked partnership to organization",
    "partnership.note_add": "Added partnership note",
    "sponsor.create": "Created sponsor",
    "sponsor.update": "Updated sponsor",
    "sponsor.delete": "Deleted sponsor",
    "sponsor.placement_update": "Updated sponsor placement",
    "advertise.page_update": "Updated advertise page",
    "advertise.metric_create": "Created advertise metric",
    "advertise.metric_update": "Updated advertise metric",
    "advertise.metric_delete": "Deleted advertise metric",
    "advertise.offering_create": "Created advertise offering",
    "advertise.offering_update": "Updated advertise offering",
    "advertise.offering_delete": "Deleted advertise offering",
    "member.update": "Updated member",
    "member.delete": "Deleted member",
    "member.note_add": "Added member note",
    "member.export": "Exported members",
    "community_page.update": "Updated community page",
    "mentorship.program_create": "Created mentorship program",
    "mentorship.program_update": "Updated mentorship program",
    "mentorship.program_delete": "Deleted mentorship program",
    "mentorship.application_update": "Updated mentorship application",
    "mentorship.application_delete": "Deleted mentorship application",
    "mentorship.application_note_add": "Added application note",
    "mentorship.match_update": "Updated mentorship match",
    "mentorship.match_note_add": "Added match note",
    "mentorship.session_add": "Added mentorship session",
    "mentorship.session_update": "Updated mentorship session",
    "newsletter_issue_created": "Created newsletter issue",
    "newsletter_issue_status_changed": "Changed newsletter issue status",
    "newsletter_issue_marked_sent": "Marked newsletter issue sent",
    "newsletter_issue_archived": "Archived newsletter issue",
    "newsletter_subscriber_suppressed": "Suppressed subscriber",
    "newsletter_subscriber_reactivated": "Reactivated subscriber",
    "newsletter_subscribers_exported": "Exported subscribers",
    "nomination.received": "Received nomination",
    "nomination.updated": "Updated nomination",
    "nomination.deleted": "Deleted nomination",
    "nomination.status_changed": "Changed nomination status",
    "nomination.reviewer_assigned": "Assigned nomination reviewer",
    "nomination.note_added": "Added nomination note",
    "submission.received": "Received story submission",
    "submission.updated": "Updated story submission",
    "submission.deleted": "Deleted story submission",
    "submission.status_changed": "Changed submission status",
    "submission.editor_assigned": "Assigned submission editor",
    "submission.note_added": "Added submission note",
    "order.status_change": "Changed order status",
    "order.payment_status_change": "Changed order payment status",
    "order.fulfillment_status_change": "Changed order fulfillment status",
    "order.create": "Created order",
    "order.delete": "Deleted order",
    "order.cancel": "Cancelled order",
    "order.archive": "Archived order",
    "order.unarchive": "Unarchived order",
    "order.note_add": "Added order note",
}


def _humanize_action(action):
    words = re.split(r"[._]+", action)
    return " ".join(words).strip().capitalize() or action


def action_label(action):
    return ACTION_LABELS.get(action, _humanize_action(action))


# Presentation-level grouping only — never mutates the stored action
# string. Matched by the entity_type an action operates on (a stable,
# already-existing column) rather than parsing the action string itself.
_CATEGORY_BY_ENTITY_TYPE = {
    "Article": "content",
    "Page": "content",
    "Topic": "content",
    "Category": "content",
    "Series": "content",
    "Tag": "content",
    "User": "access",
    "HomepageModule": "site",
    "Menu": "site",
    "SiteSetting": "site",
    "PartnershipInquiry": "commercial",
    "Sponsor": "commercial",
    "AdvertisePage": "commercial",
    "AdvertiseMetric": "commercial",
    "AdvertiseOffering": "commercial",
    "Order": "commercial",
    "Member": "community",
    "CommunityPage": "community",
    "MentorshipProgram": "community",
    "MentorshipApplication": "community",
    "MentorshipMatch": "community",
    "nomination": "community",
    "story_submission": "community",
    "NewsletterIssue": "newsletter",
    "NewsletterSubscriber": "newsletter",
}


ALL_CATEGORIES = ("content", "access", "site", "commercial", "community", "newsletter", "system")

# Inverse of _CATEGORY_BY_ENTITY_TYPE, plus "system" catching every
# entity_type not otherwise listed — used to push a category filter down
# to SQL (entity_type IN (...)) so it can run before pagination rather
# than discarding rows from an already-paginated page.
KNOWN_ENTITY_TYPES = tuple(_CATEGORY_BY_ENTITY_TYPE)


def entity_types_for_category(category):
    if category == "system":
        return None  # sentinel: "every entity_type not in the map" — caller uses NOT IN instead
    return tuple(t for t, c in _CATEGORY_BY_ENTITY_TYPE.items() if c == category)


def action_category(entry):
    return _CATEGORY_BY_ENTITY_TYPE.get(entry.entity_type, "system")


def actor_display(user):
    if user is None:
        return {"id": None, "name": "System", "email": None}
    return {"id": user.id, "name": user.full_name, "email": user.email}


def serialize_audit_entry(entry, resolved_labels):
    return {
        "id": entry.id,
        "createdAt": entry.created_at.isoformat() if entry.created_at else None,
        "actor": actor_display(entry.user),
        "action": entry.action,
        "actionLabel": action_label(entry.action),
        "category": action_category(entry),
        "entity": {
            "type": entry.entity_type,
            "id": entry.entity_id,
            "label": entity_label_for(entry, resolved_labels),
        },
        "metadata": entry.changes,
    }


def serialize_audit_page(entries):
    resolved_labels = resolve_entity_labels(entries)
    return [serialize_audit_entry(entry, resolved_labels) for entry in entries]
