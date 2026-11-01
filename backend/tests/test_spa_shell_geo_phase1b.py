"""AI Search / GEO Phase 1B — visible, semantic Article/Person content
inside #root on a hard load (app/services/prerender.py), the Person
bootstrap, the Person JSON-LD unpublished-Organization fix, and Person
canonical parity.
"""
import json
import os
import re
from datetime import datetime, timezone

import pytest

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"

HOSTILE_PARAGRAPH = "</p><script>alert('x')</script><p onclick=\"steal()\">Hi</p><img src=x onerror=alert(2)>"
HOSTILE_LINK = '<a href="javascript:alert(1)">bad</a> and <a href="https://example.com/ok">good</a>'


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


# --- helpers ------------------------------------------------------------


def _get(client, path):
    resp = client.get(path)
    return resp.status_code, resp.get_data(as_text=True)


def _root(html):
    match = re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL)
    assert match is not None, "expected a #root element followed by the app script"
    return match.group(1)


def _json_scripts(html, attr):
    return [json.loads(m) for m in re.findall(rf"<script\b[^>]*{re.escape(attr)}[^>]*>(.*?)</script>", html, re.DOTALL)]


def _one(html, attr):
    found = _json_scripts(html, attr)
    assert len(found) == 1, f"expected exactly one {attr}, found {len(found)}"
    return found[0]


def _meta(html, attr, key):
    match = re.search(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']', html)
    return match.group(1) if match else None


def _canonical(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html)
    return match.group(1) if match else None


def _assert_visible_and_not_cloaked(root_html):
    lowered = root_html.lower()
    for marker in (" hidden", "display:none", "display: none", "visibility:hidden", "visibility: hidden", 'aria-hidden="true"', "opacity:0"):
        assert marker not in lowered, marker


_JSON_SCRIPT_RE = re.compile(r'(<script type="application/(?:ld\+)?json"[^>]*>)(.*?)(</script>)', re.DOTALL)


def _assert_no_executable_markup(html):
    # JSON bootstrap / JSON-LD scripts are inert data; they must simply be
    # unable to close their own <script> early (the "</" -> "<\/" guard).
    for _open, body, _close in _JSON_SCRIPT_RE.findall(html):
        assert "</" not in body
    lowered = _JSON_SCRIPT_RE.sub("", html).lower()
    # A stripped <script>'s inner text may survive as inert visible text
    # (bleach strip=True) — what must never survive is anything executable.
    assert not re.search(r"""(?:href|src)\s*=\s*["']?\s*javascript:""", lowered), "javascript: URL survived as a live attribute"
    assert not re.search(r"<[^>]+\son[a-z]+\s*=", lowered), "event-handler attribute survived"
    assert "<img src=x" not in lowered
    assert "<a href=\"javascript" not in lowered
    assert "<noscript" not in lowered
    # The only <script> tags are the shell's own module script and JSON ones.
    for tag in re.findall(r"<script\b[^>]*>", _JSON_SCRIPT_RE.sub(r"\1\3", html)):
        assert 'type="module"' in tag or 'type="application/ld+json"' in tag or 'type="application/json"' in tag, tag


def _author(app, slug="jane-writer", name="Jane Writer"):
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug=slug).first() or Author(slug=slug, name=name, status="active")
        db.session.add(author)
        db.session.commit()
        return author.id


def _article(app, slug, status="published", content=None, **fields):
    from app.models.article import Article

    author_id = fields.pop("author_id", None) or _author(app)
    with app.app_context():
        article = Article(
            slug=slug, title=fields.pop("title", "How She Built It"), status=status, author_id=author_id,
            content=content if content is not None else [{"type": "paragraph", "text": "The first paragraph."}],
            publish_date=fields.pop("publish_date", datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)), **fields,
        )
        db.session.add(article)
        db.session.commit()
        return article.id


RICH_CONTENT = [
    {"type": "paragraph", "text": "An <strong>opening</strong> paragraph with a <a href=\"https://example.com\">link</a>."},
    {"type": "heading", "level": 2, "text": "Early years"},
    {"type": "heading", "level": 3, "text": "Sub heading"},
    {"type": "list", "style": "bullet", "items": ["Bullet one", "Bullet two"]},
    {"type": "list", "style": "number", "items": ["Step one", "Step two"]},
    {"type": "blockquote", "text": "A quoted line.", "attribution": "Ama Mensah"},
    {"type": "pullquote", "text": "A pulled quote."},
    {"type": "highlight", "title": "Key lessons", "text": "What we learned:", "listStyle": "bullet", "items": ["Lesson A", "Lesson B"]},
    {"type": "highlight", "title": "Steps", "text": "In order:", "listStyle": "number", "items": ["First", "Second"]},
    {"type": "divider"},
    {"type": "table", "headers": ["Year", "Revenue"], "rows": [["2024", "$1M"], ["2025", "$3M"]]},
    {"type": "faq", "items": [{"q": "Who founded it?", "a": "Jane did."}]},
    {"type": "image", "media": {"id": 1, "mediaPath": "/media/originals/body.jpg"}, "alt": "Jane at work", "caption": "In the lab", "credit": "WSF"},
    {"type": "newsletterCta", "heading": "NEWSLETTER-CTA-HEADING", "text": "NEWSLETTER-CTA-TEXT"},
    {"type": "ad", "slot": "AD-SLOT-SECRET"},
    {"type": "sponsorBlock", "label": "SPONSOR-BLOCK-LABEL", "text": "SPONSOR-BLOCK-TEXT"},
    {"type": "mysteryBlock", "text": "UNKNOWN-BLOCK-TEXT"},
]


# --- Article -------------------------------------------------------------------


def test_article_prerender_structure(client, app):
    co_id = _author(app, "co-writer", "Co Writer")
    from app.models.article import Article
    from app.models.people import Author

    _article(app, "how-she-built-it", content=RICH_CONTENT, subtitle="A founder's story.", excerpt="Card excerpt.")
    with app.app_context():
        article = Article.query.filter_by(slug="how-she-built-it").first()
        article.co_authors.append(db.session.get(Author, co_id))
        db.session.commit()

    status, html = _get(client, "/how-she-built-it")
    assert status == 200
    root = _root(html)
    assert root.startswith('<main data-wsf-prerender="article"')
    assert root.count('data-wsf-prerender="article"') == 1
    assert '<h1 class="' in root and "How She Built It</h1>" in root
    assert "A founder&#x27;s story." in root
    assert 'By <a href="/authors/jane-writer"' in root and 'href="/authors/co-writer"' in root
    assert '<time datetime="2026-03-04T09:00:00+00:00">March 4, 2026</time>' in root
    assert "An <strong>opening</strong> paragraph" in root
    assert re.search(r"<h2[^>]*>Early years</h2>", root)
    assert re.search(r"<h3[^>]*>Sub heading</h3>", root)
    assert re.search(r'<ul class="[^"]*list-disc"><li>Bullet one</li><li>Bullet two</li></ul>', root)
    assert re.search(r'<ol class="[^"]*list-decimal"><li>Step one</li><li>Step two</li></ol>', root)
    assert re.search(r"<blockquote[^>]*><p[^>]*>A quoted line\.</p><cite[^>]*>Ama Mensah</cite></blockquote>", root)
    assert re.search(r"<blockquote[^>]*><p[^>]*>A pulled quote\.</p></blockquote>", root)
    assert re.search(r"Key lessons</p>.*?What we learned:</p><ul[^>]*><li>Lesson A</li><li>Lesson B</li></ul>", root)
    assert re.search(r"In order:</p><ol[^>]*><li>First</li><li>Second</li></ol>", root)
    assert "<hr" in root
    assert re.search(r"<table[^>]*><thead><tr><th[^>]*>Year</th><th[^>]*>Revenue</th></tr></thead><tbody><tr><td[^>]*>2024</td>", root)
    assert re.search(r"<h3[^>]*>Who founded it\?</h3><p[^>]*>Jane did\.</p>", root)
    assert '<img src="/media/originals/body.jpg" alt="Jane at work" loading="lazy"' in root
    assert "In the lab — WSF" in root
    # Interactive/application/unknown blocks are never guessed at.
    # (They remain in the inert JSON bootstrap React itself consumes.)
    for skipped in ("NEWSLETTER-CTA", "AD-SLOT-SECRET", "SPONSOR-BLOCK", "UNKNOWN-BLOCK-TEXT"):
        assert skipped not in root
    # Excerpt isn't shown on the React page, so it isn't in the body either.
    assert "Card excerpt." not in root
    _assert_visible_and_not_cloaked(root)


def test_article_content_appears_only_inside_root(client, app):
    _article(app, "only-in-root", content=[{"type": "paragraph", "text": "UNIQUE-BODY-SENTENCE"}])
    _, html = _get(client, "/only-in-root")
    outside = html.replace(_root(html), "")
    # Outside #root it may only appear inside the machine-readable bootstrap.
    without_bootstrap = re.sub(r'<script type="application/json" data-wsf-bootstrap="article">.*?</script>', "", outside, flags=re.DOTALL)
    assert "UNIQUE-BODY-SENTENCE" not in without_bootstrap
    assert "<noscript" not in html.lower()


def test_hostile_content_cannot_escape(client, app):
    _article(app, "hostile", title="<script>alert('x')</script>Title", content=[
        {"type": "paragraph", "text": HOSTILE_PARAGRAPH},
        {"type": "paragraph", "text": HOSTILE_LINK},
        {"type": "heading", "level": 2, "text": "<img src=x onerror=alert(2)>Heading"},
        {"type": "list", "style": "bullet", "items": [HOSTILE_PARAGRAPH, HOSTILE_LINK]},
        {"type": "highlight", "title": "<script>alert('x')</script>T", "text": HOSTILE_LINK, "listStyle": "number", "items": [HOSTILE_PARAGRAPH]},
        {"type": "blockquote", "text": HOSTILE_PARAGRAPH, "attribution": "<script>alert('x')</script>"},
        {"type": "table", "headers": ["<script>alert('x')</script>"], "rows": [["<img src=x onerror=alert(2)>"]]},
        {"type": "faq", "items": [{"q": "<script>alert('x')</script>?", "a": HOSTILE_LINK}]},
        {"type": "image", "media": {"mediaPath": "javascript:alert(1)"}, "alt": "x"},
        {"type": "image", "media": {"mediaPath": "/srv/private/secret.jpg"}, "alt": "x"},
    ])
    status, html = _get(client, "/hostile")
    assert status == 200
    _assert_no_executable_markup(html)
    root = _root(html)
    assert '<a href="https://example.com/ok">good</a>' in root
    # A non-public image path written into block JSON is never rendered.
    assert "/srv/private" not in root and "<img" not in root


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_unpublished_article_has_no_prerender(client, app, status_value):
    _article(app, "not-public", status=status_value, content=[{"type": "paragraph", "text": "SECRET-DRAFT-BODY"}], title="Secret Draft Title")
    status, html = _get(client, "/not-public")
    assert status == 404
    assert "data-wsf-prerender" not in html
    assert "SECRET-DRAFT-BODY" not in html and "Secret Draft Title" not in html


def test_article_bootstrap_structured_data_canonical_unchanged(client, app):
    _article(app, "unchanged", seo={"canonical": "https://example.org/canonical-article"})
    _, html = _get(client, "/unchanged")
    bootstrap = _one(html, 'data-wsf-bootstrap="article"')
    assert bootstrap["key"] == "unchanged"
    _one(html, "data-article-structured-data")
    _one(html, "data-site-structured-data")
    crumbs = _one(html, "data-breadcrumb-structured-data")["itemListElement"]
    assert [c["name"] for c in crumbs] == ["Home", "Stories", "How She Built It"]
    assert _canonical(html) == "https://example.org/canonical-article"
    assert crumbs[-1]["item"] == "https://example.org/canonical-article"
    root = _root(html)
    for private in ("ai_editorial_notes", "approved_by", "file_path", "stored_filename", "uploaded_by_id"):
        assert private not in root


def test_sponsored_article_prerender_keeps_disclosure(client, app):
    _article(app, "sponsored", is_sponsored=True, sponsor={"name": "Acme", "disclosure": "Paid partnership with Acme"})
    _, html = _get(client, "/sponsored")
    assert "Paid partnership with Acme" in _root(html)


def test_non_prerendered_routes_keep_an_empty_root(client, app):
    for path in ("/", "/topics", "/login", "/account", "/this-does-not-exist", "/newsletter/unsubscribe/tok123"):
        _, html = _get(client, path)
        assert "data-wsf-prerender" not in html, path


# --- Person ----------------------------------------------------------------


def _org(app, slug, status, name):
    from app.models.people import Organization

    with app.app_context():
        org = Organization(slug=slug, name=name, status=status, description=[])
        db.session.add(org)
        db.session.commit()
        return org.id


def _series(app, slug, name, status):
    from app.models.taxonomy import Series

    with app.app_context():
        series = Series(slug=slug, name=name, status=status)
        db.session.add(series)
        db.session.commit()
        return series.id


def _person(app, slug="amara-okafor", status="published", series_ids=(), **fields):
    from app.models.media import Media
    from app.models.people import Person
    from app.models.taxonomy import Series

    with app.app_context():
        media = Media(original_filename="p.jpg", stored_filename="stored-p.jpg", file_path="/srv/private-storage/p.jpg",
                      public_url="/media/originals/p.jpg", mime_type="image/jpeg", alt_text="Portrait")
        db.session.add(media)
        db.session.flush()
        person = Person(slug=slug, name=fields.pop("name", "Amara Okafor"), status=status, photo_media_id=media.id, **fields)
        person.series = [db.session.get(Series, sid) for sid in series_ids]
        db.session.add(person)
        db.session.commit()
        return person.id


FULL_PERSON = dict(
    pronouns="she/her",
    title="Founder & CEO",
    profession="Engineer",
    location="Lagos",
    industry="Fintech",
    short_bio="Builds payment rails for small merchants.",
    expertise=["Payments", "Leadership"],
    featured_quote="Start before you feel ready.",
    bio=[
        {"type": "paragraph", "text": "Amara grew up in <em>Enugu</em>."},
        {"type": "heading", "level": 2, "text": "Career"},
        {"type": "list", "style": "bullet", "items": ["Founded Kaziwave", "Raised a seed round"]},
        {"type": "highlight", "title": "Lessons", "text": "Her rules:", "listStyle": "number", "items": ["Listen", "Ship"]},
    ],
    achievements=["Forbes 30 Under 30"],
    career_timeline=[{"year": "2019", "title": "Founded Kaziwave"}],
    awards=["Fintech Woman of the Year"],
)


def test_person_prerender_structure(client, app):
    org_id = _org(app, "kaziwave", "published", "Kaziwave Labs")
    _person(app, organization_id=org_id, **FULL_PERSON)
    status, html = _get(client, "/people/amara-okafor")
    assert status == 200
    root = _root(html)
    assert root.startswith('<main data-wsf-prerender="person"')
    assert re.search(r"<h1[^>]*>Amara Okafor <span[^>]*>\(she/her\)</span></h1>", root)
    assert 'Founder &amp; CEO at <a href="/organizations/kaziwave"' in root and "Kaziwave Labs</a>" in root
    assert ">Engineer</p>" in root
    assert "Lagos · Fintech" in root
    assert "Builds payment rails for small merchants." in root
    assert re.search(r"<ul[^>]*><li[^>]*>Payments</li><li[^>]*>Leadership</li></ul>", root)
    assert "Start before you feel ready." in root
    assert re.search(r"<h2[^>]*>About</h2><p[^>]*>Amara grew up in <em>Enugu</em>\.</p>", root)
    assert re.search(r"<h2[^>]*>Career</h2>", root)
    assert re.search(r"<ul[^>]*><li>Founded Kaziwave</li><li>Raised a seed round</li></ul>", root)
    assert re.search(r"Her rules:</p><ol[^>]*><li>Listen</li><li>Ship</li></ol>", root)
    assert re.search(r"<h2[^>]*>Career Timeline</h2><ol[^>]*><li><p[^>]*>2019</p><p[^>]*>Founded Kaziwave</p></li></ol>", root)
    assert re.search(r"<h2[^>]*>Achievements</h2><ul[^>]*><li>Forbes 30 Under 30</li></ul>", root)
    assert re.search(r"<h2[^>]*>Awards</h2><ul[^>]*><li>Fintech Woman of the Year</li></ul>", root)
    _assert_visible_and_not_cloaked(root)
    assert "<noscript" not in html.lower()
    data = _one(html, "data-person-structured-data")
    assert data["worksFor"] == {"@type": "Organization", "name": "Kaziwave Labs"}


def test_person_profession_identical_to_title_is_not_repeated(client, app):
    _person(app, title="Founder & CEO", profession="founder  &  ceo", short_bio="x")
    root = _root(_get(client, "/people/amara-okafor")[1])
    assert root.count("Founder &amp; CEO") == 1


@pytest.mark.parametrize("org_status", ["draft", "archived"])
def test_unpublished_organization_never_appears(client, app, org_status):
    org_id = _org(app, "hidden-org", org_status, "Hidden Org Name")
    _person(app, organization_id=org_id, title="Director", short_bio="x")
    status, html = _get(client, "/people/amara-okafor")
    assert status == 200
    assert "Hidden Org Name" not in html
    assert "hidden-org" not in html
    assert "worksFor" not in _one(html, "data-person-structured-data")
    bootstrap = _one(html, 'data-wsf-bootstrap="person"')
    assert bootstrap["data"]["organization"] is None
    assert "organization_id" not in bootstrap["data"]


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_unpublished_person_has_no_prerender(client, app, status_value):
    _person(app, status=status_value, name="Secret Person", short_bio="SECRET-BIO")
    status, html = _get(client, "/people/amara-okafor")
    assert status == 404
    assert "data-wsf-prerender" not in html and "SECRET-BIO" not in html and "Secret Person" not in html
    assert 'data-wsf-bootstrap="person"' not in html


def test_person_effective_canonical_override(client, app):
    override = "https://example.org/canonical/amara"
    _person(app, short_bio="x", seo={"canonical": override})
    _, html = _get(client, "/people/amara-okafor")
    assert _canonical(html) == override
    assert _meta(html, "property", "og:url") == override
    assert _one(html, "data-breadcrumb-structured-data")["itemListElement"][-1]["item"] == override
    assert _one(html, "data-person-structured-data")["url"] == override


def test_person_bootstrap_is_public_safe(client, app):
    published = _series(app, "founder-stories", "Founder Stories", "published")
    draft = _series(app, "secret-series", "Secret Series Name", "draft")
    _person(app, series_ids=(published, draft), **FULL_PERSON)
    _, html = _get(client, "/people/amara-okafor")
    bootstrap = _one(html, 'data-wsf-bootstrap="person"')
    assert bootstrap["key"] == "amara-okafor"
    data = bootstrap["data"]
    assert data["slug"] == "amara-okafor" and data["name"] == "Amara Okafor"
    assert data["series"] == [{"slug": "founder-stories", "name": "Founder Stories"}]
    assert "Secret Series Name" not in html and "secret-series" not in html
    raw = json.dumps(data)
    for private in ("file_path", "stored_filename", "uploaded_by_id", "/srv/private-storage", "password", "email", "user_id"):
        assert private not in raw, private
    assert data["photo"]["public_url"] == "/media/originals/p.jpg"


def test_person_page_html_size_is_reasonable(client, app):
    long_bio = [{"type": "paragraph", "text": "A realistic biography sentence with some detail. " * 12} for _ in range(25)]
    _person(app, short_bio="Short intro.", bio=long_bio, achievements=["A"] * 10, awards=["B"] * 5)
    _, html = _get(client, "/people/amara-okafor")
    root = _root(html)
    bootstrap = re.search(r'<script type="application/json" data-wsf-bootstrap="person">.*?</script>', html, re.DOTALL).group(0)
    # Visible prerender + bootstrap roughly double the body text; flag only
    # if something pathological (e.g. a recursive dump) blows it up.
    assert len(root) < 40_000 and len(bootstrap) < 40_000


def test_no_user_agent_branch_in_rendering_path():
    # Same HTML for every visitor: neither the shell nor the prerender
    # module ever inspects who is asking.
    import inspect

    from app.services import prerender, spa_shell

    for module in (prerender, spa_shell):
        source = inspect.getsource(module).lower()
        # (Docstrings may say "no User-Agent branch"; code may not read it.)
        assert "user_agent" not in source
        assert "request.headers" not in source and "request.environ" not in source
