"""Public linked-entity visibility (GEO security correction).

A public parent (an Event, Job, Resource, Article, ...) may reference a
linked entity that is itself NOT public — a draft Person, a draft/
archived Organization, an inactive Author, an unpublished Topic/Tag/
Series/Category. Anonymous/public serializations must never reveal that
linked entity merely because a public parent points at it: its nested
preview (name, slug, logo/photo, profile link) is dropped from the
PUBLIC dump. Parent-owned fallback text stored on the parent itself
(Job.company_name, Opportunity.organization_name, Event.organizer_name,
EventSpeaker.name/title/organization_name, Resource.author_name) is
public content and is left alone.

These helpers only post-process an already-dumped public payload, using
the ORM objects it was dumped from. Staff/CMS dumps never call them, so
editors keep seeing (and can keep linking) draft relationships. Nothing
here mutates stored data.

Statuses are the existing public ones — none invented:
  Person/Organization/Topic/Tag/Series/Category: "published"
  Author: "active"
"""


def is_public_person(person):
    return person is not None and person.status == "published"


def is_public_organization(organization):
    return organization is not None and organization.status == "published"


def is_public_author(author):
    return author is not None and author.status == "active"


def is_public_taxonomy(term):
    """Topic / Tag / Series / Category — all share the "published" status
    convention (app/models/taxonomy.py)."""
    return term is not None and term.status == "published"


def filter_dumped(dumped_items, objects, predicate):
    """Keeps the dumped items whose source object passes `predicate`.
    `dumped_items` was produced from `objects` in the same order."""
    if not isinstance(dumped_items, list):
        return dumped_items
    objects = list(objects or [])
    return [item for item, obj in zip(dumped_items, objects) if predicate(obj)]


def keep_if(dumped, obj, predicate):
    return dumped if obj is not None and predicate(obj) else None


# --- per-entity public post-processors ----------------------------------


def public_person_dump(data, person):
    """PersonSchema already limits `organization` to a published one; the
    nested `series` list is filtered here to published Series."""
    if isinstance(data, dict) and person is not None and "series" in data:
        data["series"] = filter_dumped(data["series"], person.series, is_public_taxonomy)
    return data


def public_author_dump(data, author):
    """AuthorSchema already limits `person` to a published one; `topics`
    is filtered here to published Topics."""
    if isinstance(data, dict) and author is not None and "topics" in data:
        data["topics"] = filter_dumped(data["topics"], author.topics, is_public_taxonomy)
    return data


def public_article_dump(data, article):
    """Taxonomy + related entities of a public Article payload/summary.
    The byline (author/co_authors) is editorial attribution and stays;
    only those Authors' own nested topic lists are filtered."""
    if not isinstance(data, dict) or article is None:
        return data
    if "category" in data:
        data["category"] = keep_if(data["category"], article.category, is_public_taxonomy)
    if "series" in data:
        data["series"] = keep_if(data["series"], article.series, is_public_taxonomy)
    if "topics" in data:
        data["topics"] = filter_dumped(data["topics"], article.topics, is_public_taxonomy)
    if "tags" in data:
        data["tags"] = filter_dumped(data["tags"], article.tags, is_public_taxonomy)
    if "related_people" in data:
        people = [p for p in (article.related_people or []) if is_public_person(p)]
        dumped = filter_dumped(data["related_people"], article.related_people, is_public_person)
        data["related_people"] = [public_person_dump(d, p) for d, p in zip(dumped, people)]
    if "related_organizations" in data:
        data["related_organizations"] = filter_dumped(
            data["related_organizations"], article.related_organizations, is_public_organization
        )
    if isinstance(data.get("author"), dict):
        public_author_dump(data["author"], article.author)
    if isinstance(data.get("co_authors"), list):
        for dumped, author in zip(data["co_authors"], article.co_authors or []):
            public_author_dump(dumped, author)
    return data


def public_event_dump(data, event):
    """Organizer / speaker Person / sponsor Organization previews only when
    public. EventSpeaker's and EventSponsor's own stored fallback fields
    (and Event.organizer_name) are untouched."""
    if not isinstance(data, dict) or event is None:
        return data
    if "organizer" in data:
        data["organizer"] = keep_if(data["organizer"], event.organizer, is_public_organization)
    for dumped, speaker in zip(data.get("speakers") or [], event.speakers or []):
        if isinstance(dumped, dict) and "person" in dumped:
            dumped["person"] = keep_if(dumped["person"], speaker.person, is_public_person)
    for dumped, sponsor in zip(data.get("sponsors") or [], event.sponsors or []):
        if isinstance(dumped, dict) and "organization" in dumped:
            dumped["organization"] = keep_if(dumped["organization"], sponsor.organization, is_public_organization)
    return data


def public_organization_preview(organization, dump):
    """`dump` is a callable producing the preview dict; None unless the
    Organization is published."""
    return dump(organization) if is_public_organization(organization) else None


def public_resource_relations(data, resource, *, author_key="author", sponsor_key="sponsor"):
    """Author (active only), sponsor Organization (published only), and
    Topics/Tags (published only) of a public Resource payload.
    Resource.author_name — parent-owned text — is untouched."""
    if not isinstance(data, dict) or resource is None:
        return data
    if author_key in data:
        data[author_key] = keep_if(data[author_key], resource.author, is_public_author)
        if isinstance(data[author_key], dict):
            public_author_dump(data[author_key], resource.author)
    if sponsor_key in data:
        data[sponsor_key] = keep_if(data[sponsor_key], resource.sponsor, is_public_organization)
    if "topics" in data:
        data["topics"] = filter_dumped(data["topics"], resource.topics, is_public_taxonomy)
    if "tags" in data:
        data["tags"] = filter_dumped(data["tags"], resource.tags, is_public_taxonomy)
    return data


def public_learning_dump(data, program):
    """Instructor (active Author only), co-instructors, provider
    Organization (published only) and Topics (published only) of a public
    Learning program payload/summary. The schema's own related-article/
    related-resource/event methods already filter to public records."""
    if not isinstance(data, dict) or program is None:
        return data
    if "primary_instructor" in data:
        data["primary_instructor"] = keep_if(data["primary_instructor"], program.primary_instructor, is_public_author)
    if "co_instructors" in data:
        data["co_instructors"] = filter_dumped(data["co_instructors"], program.co_instructors, is_public_author)
    if "provider_organization" in data:
        data["provider_organization"] = keep_if(data["provider_organization"], program.provider_organization, is_public_organization)
    if "topics" in data:
        data["topics"] = filter_dumped(data["topics"], program.topics, is_public_taxonomy)
    return data


def public_sponsor_disclosure(sponsor):
    """The minimal PUBLIC disclosure for a linked Sponsor campaign — only
    while that campaign is itself publicly eligible (Sponsor.
    is_publicly_eligible: active, public_visible, inside its date window).
    Never tier, campaign name, commercial/internal fields or the admin id;
    the Organization preview only when that Organization is published.
    Keys match what ArticlePage's disclosure reads (publicName,
    disclosure_label, organization.name)."""
    if sponsor is None or not sponsor.is_publicly_eligible():
        return None
    organization = sponsor.organization
    return {
        "publicName": sponsor.resolved_public_name,
        "disclosure_label": sponsor.disclosure_label,
        "organization": (
            {"slug": organization.slug, "name": organization.name} if is_public_organization(organization) else None
        ),
    }
