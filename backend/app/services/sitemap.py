"""Public XML sitemap generation (see the unprefixed /sitemap.xml route
registered directly in app/__init__.py — it must live outside /api/v1 and
outside the SPA's static root, because the sitemap protocol restricts a
sitemap file to only listing URLs at or below its own path; nested under
/api/v1 it could never validly list a page like /jobs/some-slug).

Every entry below reuses the exact same status/visibility condition its
own content type's real public LIST endpoint already enforces (see
app/api/v1/<type>.py) — never a re-derived or parallel notion of "what's
public". Nothing here ever reads or serializes a privileged action field
(application_url, file_url, virtual_link, download target, contact email/
phone, etc.) — only the slug already used to build that entity's own
canonical public page path. A Circle-gated record (access_type ==
"circle_only") is included on exactly the same terms as any other record
of its type: Circle gating controls a privileged ACTION channel on an
otherwise-public detail page (see job_access.py/event_registrations.py/
Resource.is_publicly_visible()'s own docstrings), never the page's own
visibility — this module never reads `access_type` at all, by design.

Structured as one small query-building function per content type so a
future sitemap index / split-by-type could change which functions get
called into which file without touching the functions themselves.
"""
from datetime import date

from sqlalchemy import or_
from xml.etree import ElementTree as ET

from app.extensions import db
from app.models.article import Article
from app.models.commerce import Product
from app.models.directory import DirectoryListing
from app.models.learning import LearningProgram
from app.models.newsletter import NewsletterIssue
from app.models.opportunity import Event, Job, Opportunity
from app.models.page import Page
from app.models.people import Author, Organization, Person
from app.models.resource import Resource as ResourceModel
from app.models.taxonomy import Series, Topic
from app.services.event_registrations import is_event_publicly_visible
from app.services.job_access import is_job_publicly_visible

SITEMAP_XML_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"

# (Page.key, public frontend path) — the only Page rows with a real public
# render route today. A "general" Page has no public route this app
# serves (see app/models/page.py's own docstring), so it must never
# appear here no matter its status.
SYSTEM_PAGE_ROUTES = (
    ("about", "/about"),
    ("contact", "/contact"),
    ("privacy", "/privacy"),
    ("terms", "/terms"),
    ("cookies", "/cookies"),
    ("editorial-policy", "/editorial-policy"),
)


def _entry(path, lastmod=None):
    return {"loc": path, "lastmod": lastmod}


def _system_page_entries():
    entries = []
    for key, path in SYSTEM_PAGE_ROUTES:
        page = Page.query.filter_by(key=key, status="published").first()
        if page is not None:
            entries.append(_entry(path, page.updated_at))
    return entries


def _topic_entries():
    entries = [_entry("/topics")]
    topics = Topic.query.filter_by(status="published").all()
    entries += [_entry(f"/topics/{t.slug}", t.updated_at) for t in topics]
    return entries


def _series_entries():
    entries = [_entry("/series")]
    series = Series.query.filter_by(status="published").all()
    entries += [_entry(f"/series/{s.slug}", s.updated_at) for s in series]
    return entries


def _people_entries():
    entries = [_entry("/people")]
    people = Person.query.filter_by(status="published").all()
    entries += [_entry(f"/people/{p.slug}", p.updated_at) for p in people]
    return entries


def _author_entries():
    entries = [_entry("/authors")]
    authors = Author.query.filter_by(status="active").all()
    entries += [_entry(f"/authors/{a.slug}", a.updated_at) for a in authors]
    return entries


def _organization_entries():
    entries = [_entry("/organizations")]
    orgs = Organization.query.filter_by(status="published").all()
    entries += [_entry(f"/organizations/{o.slug}", o.updated_at) for o in orgs]
    return entries


def _article_entries():
    # No separate "articles index" exists — Topics/Series/Homepage are the
    # only browse surfaces; each article lives at its own flat `/{slug}`.
    articles = Article.query.filter_by(status="published").all()
    return [_entry(f"/{a.slug}", a.updated_at) for a in articles]


def _job_entries():
    entries = [_entry("/jobs")]
    # Coarse SQL pre-filter (cheap, avoids loading draft/closed/archived
    # rows) — the real decision is is_job_publicly_visible()'s own
    # scheduled-date rule, applied per row below so this can never drift
    # from JobDetailResource's actual behavior.
    jobs = Job.query.filter(Job.status.in_(["published", "scheduled"])).all()
    entries += [_entry(f"/jobs/{j.slug}", j.updated_at) for j in jobs if is_job_publicly_visible(j)]
    return entries


def _opportunity_entries():
    entries = [_entry("/opportunities")]
    today = date.today()
    # Mirrors OpportunityListResource's exact public filter (no separate
    # access predicate exists for Opportunity) — status=="published" and
    # not past its own expiry_date.
    opportunities = (
        Opportunity.query.filter(Opportunity.status == "published")
        .filter(or_(Opportunity.expiry_date.is_(None), Opportunity.expiry_date >= today))
        .all()
    )
    entries += [_entry(f"/opportunities/{o.slug}", o.updated_at) for o in opportunities]
    return entries


def _event_entries():
    entries = [_entry("/events")]
    events = Event.query.filter(
        Event.status.in_(["published", "cancelled", "postponed", "scheduled"])
    ).all()
    entries += [_entry(f"/events/{e.slug}", e.updated_at) for e in events if is_event_publicly_visible(e)]
    return entries


def _resource_entries():
    entries = [_entry("/resources")]
    resources = ResourceModel.query.filter(ResourceModel.status.in_(["published", "scheduled"])).all()
    entries += [_entry(f"/resources/{r.slug}", r.updated_at) for r in resources if r.is_publicly_visible()]
    return entries


def _learning_program_entries():
    entries = [_entry("/learning")]
    programs = LearningProgram.query.filter_by(status="published").all()
    entries += [_entry(f"/learning/{p.slug}", p.updated_at) for p in programs]
    return entries


def _directory_entries():
    entries = [_entry("/directory")]
    # Two-column projection (not full ORM objects) — avoids pulling the
    # rest of DirectoryListing/Organization's columns and avoids an N+1
    # lazy-load on listing.organization for every row.
    rows = (
        db.session.query(DirectoryListing.updated_at, Organization.slug)
        .join(Organization, DirectoryListing.organization_id == Organization.id)
        .filter(DirectoryListing.status == "published", Organization.status == "published")
        .all()
    )
    entries += [_entry(f"/directory/{slug}", updated_at) for updated_at, slug in rows]
    return entries


def _newsletter_entries():
    entries = [_entry("/newsletter")]
    issues = NewsletterIssue.query.filter_by(status="sent").all()
    entries += [_entry(f"/newsletter/{i.slug}", i.sent_at or i.updated_at) for i in issues]
    return entries


def _product_entries():
    entries = [_entry("/shop")]
    # "unavailable" still renders a real, indexable detail page (a
    # "Coming soon"/"Currently unavailable" state, not a 404) — see
    # ProductDetailResource.get's identical status check.
    products = Product.query.filter(Product.status.in_(["active", "unavailable"])).all()
    entries += [_entry(f"/shop/{p.slug}", p.updated_at) for p in products]
    return entries


# Fixed public singleton marketing/content pages — verified by reading
# each page component's own useSeo() call (frontend/src/pages/*.jsx):
# none of these eight sets `robots: 'noindex, nofollow'` (contrast with
# AccountMembershipPage.jsx/NewsletterUnsubscribePage.jsx, which
# explicitly do, and are correctly never listed here), and every one
# hand-sets its own `canonical` URL — the same deliberate-indexability
# signal AdvertisePage/CommunityPage already carry. Re-verify this list
# against useSeo() usage if any of these pages' SEO config changes.
# No backing per-page "last modified" row is read generically across all
# eight (Advertise/Community do have their own CMS content models, but
# gating sitemap inclusion on that model's status would be a new
# visibility rule this module wasn't asked to add — the route itself
# always renders regardless of that model's draft/published state), so
# none of these carries a <lastmod> — acceptable per the sitemap spec.
SINGLETON_PUBLIC_PAGE_ROUTES = (
    "/advertise",
    "/partnerships",
    "/community",
    "/circle",
    "/mentorship",
    "/submit",
    "/nominate",
    "/directory/submit",
)


def _singleton_page_entries():
    return [_entry(path) for path in SINGLETON_PUBLIC_PAGE_ROUTES]


def collect_public_sitemap_entries():
    """Every real, public, indexable URL on the site today — see this
    module's own docstring for what "real" and "public" mean here.
    Deliberately excludes: admin/account/auth routes, the client-side
    /search page (Google's own sitemap guidance: never list an internal
    search page), and any Category/Tag page (no public route exists for
    either — see app/models/page.py and the taxonomy audit). The eight
    public singleton pages (Advertise/Partnerships/Community/Circle/
    Mentorship/Submit/Nominate/Directory-submit) ARE included — see
    SINGLETON_PUBLIC_PAGE_ROUTES's own comment for the code-verified
    reasoning (none of them sets noindex; all hand-set a canonical URL).
    """
    entries = [_entry("/")]
    entries += _system_page_entries()
    entries += _singleton_page_entries()
    entries += _topic_entries()
    entries += _series_entries()
    entries += _people_entries()
    entries += _author_entries()
    entries += _organization_entries()
    entries += _job_entries()
    entries += _opportunity_entries()
    entries += _event_entries()
    entries += _resource_entries()
    entries += _learning_program_entries()
    entries += _directory_entries()
    entries += _newsletter_entries()
    entries += _product_entries()
    entries += _article_entries()
    return entries


def _format_lastmod(value):
    if value is None:
        return None
    # date/datetime both expose isoformat(); a plain date (e.g. Page has
    # no date-only columns today, but kept generic) yields "YYYY-MM-DD",
    # a tz-aware datetime yields the full "YYYY-MM-DDThh:mm:ss+00:00" —
    # both are valid lastmod formats under the sitemap protocol.
    return value.isoformat()


def render_sitemap_xml(entries, base_url):
    """Builds the sitemap document as UTF-8 XML bytes. Uses the stdlib's
    ElementTree (no new dependency) — its text-node serialization already
    XML-escapes &/</>/quotes, so an unusual slug or base_url never
    produces malformed XML.
    """
    base_url = base_url.rstrip("/")
    urlset = ET.Element("urlset", {"xmlns": SITEMAP_XML_NS})
    for entry in entries:
        url_el = ET.SubElement(urlset, "url")
        loc_el = ET.SubElement(url_el, "loc")
        loc_el.text = f"{base_url}{entry['loc']}"
        lastmod_text = _format_lastmod(entry["lastmod"])
        if lastmod_text:
            lastmod_el = ET.SubElement(url_el, "lastmod")
            lastmod_el.text = lastmod_text
    return ET.tostring(urlset, encoding="UTF-8", xml_declaration=True)


def build_sitemap_xml(base_url):
    """The one function the /sitemap.xml route calls."""
    return render_sitemap_xml(collect_public_sitemap_entries(), base_url)


# The one Disallow directive this app has ever needed (see
# frontend/public/robots.txt's own comment/history) — kept here, not
# re-derived from anything, since there's no admin-route registry this
# could safely be generated from.
ROBOTS_DISALLOW_PATHS = ("/admin/",)


def build_robots_txt(base_url):
    """The one function the /robots.txt route calls — generates the
    Sitemap: directive from the same configured canonical origin
    /sitemap.xml uses, instead of a hard-coded domain (see
    frontend/public/robots.txt's own comment for why that static file no
    longer carries this line, and deploy/nginx/*.conf.example for the
    routing change that makes this the one actually served in
    production).
    """
    base_url = base_url.rstrip("/")
    lines = [
        "# Women Shaping Futures — public site is crawlable; the admin CMS",
        "# is a client-side-only route (no server-rendered content to",
        "# index) and is excluded here as a courtesy signal, not as access",
        "# control — the real protection is the backend's own",
        "# authentication.",
        "User-agent: *",
    ]
    lines += [f"Disallow: {path}" for path in ROBOTS_DISALLOW_PATHS]
    lines += ["", f"Sitemap: {base_url}/sitemap.xml"]
    return "\n".join(lines) + "\n"
