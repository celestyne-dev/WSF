"""AI Search / GEO Phase 4A — profile evidence (Person.sources /
Author.sources), author credibility and identity signals: validation,
update semantics, detail-vs-list payloads, crawler-readable HTML and the
Person/Author JSON-LD (sameAs / knowsAbout / worksFor / award / subjectOf).
"""
import importlib
import json
import os
import re

import pytest
import sqlalchemy as sa

from app.extensions import db
from app.services import indexnow
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"

SOURCE_A = {
    "title": "  Appointed CEO of Example Bank ",
    "url": " https://news.example.org/ceo-appointment ",
    "publisher": "Example News",
    "author": "Business Desk",
    "publishedDate": "2025-06-30",
    "note": "Confirms appointment as CEO.",
}
SOURCE_A_STORED = {
    "title": "Appointed CEO of Example Bank",
    "url": "https://news.example.org/ceo-appointment",
    "publisher": "Example News",
    "author": "Business Desk",
    "publishedDate": "2025-06-30",
    "note": "Confirms appointment as CEO.",
}
SOURCE_B = {"title": "Institutional biography", "url": "https://bank.example.com/about/leadership", "publisher": "", "note": "  "}
SOURCE_B_STORED = {"title": "Institutional biography", "url": "https://bank.example.com/about/leadership"}

# Each profile kind: collection path, minimal valid payload, public status.
KINDS = {
    "people": ({"name": "Evidence Person", "shortBio": "A leader.", "status": "published"}, "published"),
    "authors": ({"name": "Evidence Author", "shortBio": "A writer.", "status": "active"}, "active"),
}


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


@pytest.fixture()
def token(client, app):
    from app.models.user import Role, User

    payload = {"email": "evidence-admin@example.com", "password": "supersecret1", "first_name": "Evi",
               "last_name": "Dence", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


def _create(client, token, kind, **overrides):
    payload = dict(KINDS[kind][0])
    payload.update(overrides)
    return client.post(f"/api/v1/{kind}", json=payload, headers=auth_headers(token))


def _detail(client, kind, slug, token=None):
    headers = auth_headers(token) if token else {}
    data = client.get(f"/api/v1/{kind}/{slug}", headers=headers).get_json()["data"]
    return data["author"] if kind == "authors" else data


def _list(client, kind, token=None):
    headers = auth_headers(token) if token else {}
    return client.get(f"/api/v1/{kind}", headers=headers).get_json()["data"]


def _add(app, *objs):
    with app.app_context():
        db.session.add_all(objs)
        db.session.commit()
        return [o.id for o in objs]


def _root(html):
    return re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL).group(1)


def _json_ld(html, attr):
    scripts = re.findall(rf"<script\b[^>]*{re.escape(attr)}[^>]*>(.*?)</script>", html, re.DOTALL)
    assert len(scripts) == 1, attr
    return json.loads(scripts[0])


# --- migration ------------------------------------------------------------------------------------


def _migration():
    return importlib.import_module("migrations.versions.d4b8e2a6f1c3_profile_sources")


def test_migration_is_single_head_after_article_sources():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    module = _migration()
    assert module.revision == "d4b8e2a6f1c3" and module.down_revision == "c3a9e5f1d2b7"
    config = Config()
    config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
    assert ScriptDirectory.from_config(config).get_heads() == ["d4b8e2a6f1c3"]


def test_migration_backfills_existing_rows_and_downgrades_cleanly():
    """Runs the real upgrade()/downgrade() against existing rows (SQLite,
    so it needs no second Postgres database)."""
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE people (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(sa.text("CREATE TABLE authors (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(sa.text("INSERT INTO people (name) VALUES ('Existing Person')"))
        conn.execute(sa.text("INSERT INTO authors (name) VALUES ('Existing Author')"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        for table in ("people", "authors"):
            assert json.loads(conn.execute(sa.text(f"SELECT sources FROM {table}")).scalar()) == []
            column = next(c for c in sa.inspect(conn).get_columns(table) if c["name"] == "sources")
            assert column["nullable"] is False
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        for table in ("people", "authors"):
            assert {c["name"] for c in sa.inspect(conn).get_columns(table)} == {"id", "name"}
            assert conn.execute(sa.text(f"SELECT name FROM {table}")).scalar().startswith("Existing")


def test_new_rows_default_to_empty_sources(app):
    from app.models.people import Author, Person

    with app.app_context():
        person, author = Person(slug="p-default", name="P"), Author(slug="a-default", name="A")
        db.session.add_all([person, author])
        db.session.commit()
        assert person.sources == [] and author.sources == []


# --- validation / update semantics (both kinds) --------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_sources_are_normalized_and_persisted(client, token, kind):
    resp = _create(client, token, kind, sources=[SOURCE_A, SOURCE_B])
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()["data"]
    assert body["sources"] == [SOURCE_A_STORED, SOURCE_B_STORED]
    assert _detail(client, kind, body["slug"])["sources"] == [SOURCE_A_STORED, SOURCE_B_STORED]


@pytest.mark.parametrize("kind", KINDS)
def test_profile_without_sources_still_publishes(client, token, kind):
    resp = _create(client, token, kind)
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["data"]["sources"] == []


BAD_SOURCES = [
    {"title": "X", "url": "javascript:alert(1)"},
    {"title": "X", "url": "data:text/html,<script>alert(1)</script>"},
    {"title": "X", "url": "ftp://example.org/file"},
    {"title": "X", "url": "not a url"},
    {"title": "X", "url": "https://intranet/path"},
    {"title": "X", "url": "https://"},
    {"title": "X", "url": ""},
    {"title": "", "url": "https://example.org"},
    {"title": "   ", "url": "https://example.org"},
    {"url": "https://example.org"},
    {"title": "X"},
    {"title": "X" * 301, "url": "https://example.org"},
    {"title": "X", "url": "https://example.org/" + "a" * 2048},
    {"title": "X", "url": "https://example.org", "publisher": "P" * 251},
    {"title": "X", "url": "https://example.org", "author": "A" * 251},
    {"title": "X", "url": "https://example.org", "note": "N" * 501},
    {"title": "X", "url": "https://example.org", "publishedDate": "15/01/2026"},
    {"title": "X", "url": "https://example.org", "publishedDate": "2026-02-30"},
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad", BAD_SOURCES)
def test_invalid_sources_are_rejected(client, token, kind, bad):
    resp = _create(client, token, kind, sources=[bad])
    assert resp.status_code in (400, 422), bad
    assert "sources" in json.dumps(resp.get_json()["error"])


@pytest.mark.parametrize("kind", KINDS)
def test_boundary_lengths_accepted_and_unknown_fields_ignored(client, token, kind):
    source = {"title": "T" * 300, "url": "https://example.org/" + "a" * 2000, "publisher": "P" * 250,
              "author": "A" * 250, "note": "N" * 500, "verified": True, "html": "<b>x</b>"}
    resp = _create(client, token, kind, sources=[source])
    assert resp.status_code == 201, resp.get_json()
    stored = resp.get_json()["data"]["sources"][0]
    assert set(stored) == {"title", "url", "publisher", "author", "note"}


@pytest.mark.parametrize("kind", KINDS)
def test_duplicate_trimmed_urls_rejected(client, token, kind):
    resp = _create(client, token, kind, sources=[
        {"title": "A", "url": "https://example.com/report"},
        {"title": "B", "url": " https://example.com/report "},
    ])
    assert resp.status_code in (400, 422)
    assert "listed more than once" in json.dumps(resp.get_json())


@pytest.mark.parametrize("kind", KINDS)
def test_source_cap(client, token, kind):
    many = [{"title": f"S{i}", "url": f"https://example.org/{i}"} for i in range(51)]
    resp = _create(client, token, kind, sources=many)
    assert resp.status_code in (400, 422) and "at most 50 sources" in json.dumps(resp.get_json())
    assert _create(client, token, kind, sources=many[:50]).status_code == 201


@pytest.mark.parametrize("kind", KINDS)
def test_omitted_sources_preserved_and_explicit_empty_clears(client, token, kind):
    slug = _create(client, token, kind, sources=[SOURCE_B]).get_json()["data"]["slug"]
    edit = dict(KINDS[kind][0], name="Renamed Profile", slug=slug)
    resp = client.put(f"/api/v1/{kind}/{slug}", json=edit, headers=auth_headers(token))
    assert resp.status_code == 200 and resp.get_json()["data"]["sources"] == [SOURCE_B_STORED]
    resp = client.put(f"/api/v1/{kind}/{slug}", json=dict(edit, sources=[]), headers=auth_headers(token))
    assert resp.get_json()["data"]["sources"] == []


# --- payloads: detail carries sources, lists never ------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_detail_includes_sources_lists_never(client, token, kind):
    slug = _create(client, token, kind, sources=[SOURCE_A]).get_json()["data"]["slug"]
    assert _detail(client, kind, slug)["sources"] == [SOURCE_A_STORED]
    assert _detail(client, kind, slug, token)["sources"] == [SOURCE_A_STORED]
    for items in (_list(client, kind), _list(client, kind, token)):
        assert items and all("sources" not in item for item in items)
    assert "news.example.org" not in json.dumps(_list(client, kind, token))


@pytest.mark.parametrize("kind", KINDS)
def test_unpublished_profile_still_404s_publicly(client, token, kind):
    slug = _create(client, token, kind, status="draft", sources=[SOURCE_A]).get_json()["data"]["slug"]
    assert client.get(f"/api/v1/{kind}/{slug}").status_code == 404
    assert client.get(f"/{kind}/{slug}").get_data(as_text=True).count("news.example.org") == 0


def test_author_payloads_never_carry_user_id(client, token):
    slug = _create(client, token, "authors", sources=[SOURCE_A]).get_json()["data"]["slug"]
    assert "user_id" not in _detail(client, "authors", slug) and "user_id" not in _detail(client, "authors", slug, token)


def test_sources_stay_out_of_cards_hubs_search_and_bylines(client, app, token):
    person_slug = _create(client, token, "people", sources=[SOURCE_A]).get_json()["data"]["slug"]
    author_slug = _create(client, token, "authors", sources=[{"title": "Author ref", "url": "https://authorref.example.org/x"}]).get_json()["data"]["slug"]
    article = client.post("/api/v1/articles", json={
        "title": "Byline Story", "authorSlug": author_slug, "status": "published", "relatedPersonSlugs": [person_slug],
        "content": [{"type": "paragraph", "text": "Body."}]}, headers=auth_headers(token)).get_json()["data"]
    assert "sources" not in article["author"] and all("sources" not in p for p in article["related_people"])
    for payload in (
        client.get("/api/v1/articles").get_json(),
        client.get(f"/api/v1/articles/{article['slug']}").get_json(),
        client.get(f"/api/v1/authors/{author_slug}").get_json()["data"]["articles"],
        client.get("/api/v1/search?q=Evidence").get_json(),
    ):
        text = json.dumps(payload)
        assert "news.example.org" not in text and "authorref.example.org" not in text
    for hub in ("/people", "/authors", "/search?q=Evidence"):
        html = client.get(hub).get_data(as_text=True)
        assert "news.example.org" not in html and "authorref.example.org" not in html


@pytest.mark.parametrize("kind", KINDS)
def test_source_edit_on_public_profile_uses_existing_indexnow_update(client, app, token, kind, monkeypatch):
    calls = []
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY="test-indexnow-key-1234", PUBLIC_SITE_URL=SITE)
    monkeypatch.setattr(indexnow, "_post_json", lambda url, payload, timeout: calls.append(payload["urlList"]) or 200)
    slug = _create(client, token, kind).get_json()["data"]["slug"]
    calls.clear()
    client.put(f"/api/v1/{kind}/{slug}", json=dict(KINDS[kind][0], slug=slug, sources=[SOURCE_B]), headers=auth_headers(token))
    assert calls == [[f"{SITE}/{kind}/{slug}"]]


# --- raw HTML: visible Sources & references -------------------------------------------------------


HOSTILE = {"title": '<script>alert(1)</script>"Quoted" & <b>bold</b>', "url": "https://example.org/hostile?a=1&b=2",
           "note": "<img src=x onerror=alert(1)>", "publisher": "Pub & Co > Others"}


@pytest.mark.parametrize("kind", KINDS)
def test_sources_in_initial_server_html(client, token, kind):
    slug = _create(client, token, kind, sources=[SOURCE_A, HOSTILE]).get_json()["data"]["slug"]
    html = client.get(f"/{kind}/{slug}").get_data(as_text=True)
    root = _root(html)
    section_id = "person-sources" if kind == "people" else "author-sources"
    assert f'<section aria-labelledby="{section_id}"' in root
    assert root.count("Sources &amp; references</h2>") == 1
    assert '<a href="https://news.example.org/ceo-appointment" target="_blank" rel="noopener noreferrer"' in root
    assert "Appointed CEO of Example Bank</a>" in root
    assert "Business Desk · Example News" in root
    assert '<time datetime="2025-06-30">June 30, 2025</time>' in root
    assert "Confirms appointment as CEO." in root
    assert root.index("Appointed CEO") < root.index("&lt;script&gt;")  # stored order
    # Plain text only: hostile values are escaped, never markup.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;&quot;Quoted&quot; &amp; &lt;b&gt;bold&lt;/b&gt;" in root
    assert "&lt;img src=x onerror=alert(1)&gt;" in root and "Pub &amp; Co &gt; Others" in root
    assert 'href="https://example.org/hostile?a=1&amp;b=2"' in root
    assert "<script>alert" not in root and "<img src=x" not in root and "<b>bold" not in root
    for rel in ("nofollow", "sponsored", "ugc"):
        assert rel not in root
    for claim in ("Verified", "Fact checked", "Fact-checked"):
        assert claim not in root


@pytest.mark.parametrize("kind", KINDS)
def test_no_sources_means_no_section(client, token, kind):
    slug = _create(client, token, kind).get_json()["data"]["slug"]
    html = client.get(f"/{kind}/{slug}").get_data(as_text=True)
    assert "Sources &amp; references" not in html and "subjectOf" not in html


def test_person_bootstrap_carries_sources_once(client, token):
    slug = _create(client, token, "people", sources=[SOURCE_A]).get_json()["data"]["slug"]
    html = client.get(f"/people/{slug}").get_data(as_text=True)
    scripts = re.findall(r'<script\b[^>]*data-wsf-bootstrap="person"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert len(scripts) == 1
    assert json.loads(scripts[0])["data"]["sources"] == [SOURCE_A_STORED]


# --- structured data ------------------------------------------------------------------------------


def _orgs(app):
    from app.models.people import Organization

    return _add(app,
                Organization(slug="example-bank", name="Example Bank", status="published", description=[]),
                Organization(slug="secret-org", name="Secret Draft Org", status="draft", description=[]))


def test_person_json_ld_identity_and_evidence(client, app, token):
    pub_org, draft_org = _orgs(app)
    slug = _create(client, token, "people", title="Chief Executive", organizationId=pub_org,
                   website="https://jane.example.com", social={"linkedin": "jane", "twitter": "jane_x", "instagram": "jane_ig"},
                   expertise=["Finance", " finance ", "", "Leadership"], awards=["Banker of the Year 2024", "  "],
                   sources=[SOURCE_A, SOURCE_B]).get_json()["data"]["slug"]
    html = client.get(f"/people/{slug}").get_data(as_text=True)
    data = _json_ld(html, "data-person-structured-data")
    assert data["jobTitle"] == "Chief Executive"
    assert data["worksFor"] == {"@type": "Organization", "name": "Example Bank", "url": f"{SITE}/organizations/example-bank"}
    assert data["sameAs"] == ["https://jane.example.com", "https://linkedin.com/in/jane", "https://twitter.com/jane_x",
                              "https://instagram.com/jane_ig"]
    assert data["knowsAbout"] == ["Finance", "Leadership"]
    assert data["award"] == ["Banker of the Year 2024"]
    assert data["subjectOf"] == [
        {"@type": "CreativeWork", "name": "Appointed CEO of Example Bank", "url": "https://news.example.org/ceo-appointment",
         "author": {"@type": "Thing", "name": "Business Desk"}, "publisher": {"@type": "Organization", "name": "Example News"},
         "datePublished": "2025-06-30"},
        {"@type": "CreativeWork", "name": "Institutional biography", "url": "https://bank.example.com/about/leadership"},
    ]
    # Evidence URLs are never identity; notes never reach JSON-LD.
    assert not set(data["sameAs"]) & {SOURCE_A_STORED["url"], SOURCE_B_STORED["url"]}
    assert "Confirms appointment" not in json.dumps(data)
    # Draft Organization never reaches JSON-LD.
    client.put(f"/api/v1/people/{slug}", json=dict(KINDS["people"][0], slug=slug, organizationId=draft_org), headers=auth_headers(token))
    html = client.get(f"/people/{slug}").get_data(as_text=True)
    assert "worksFor" not in _json_ld(html, "data-person-structured-data") and "Secret Draft Org" not in html


def test_person_json_ld_minimal_has_no_empty_fields(client, token):
    slug = _create(client, token, "people").get_json()["data"]["slug"]
    data = _json_ld(client.get(f"/people/{slug}").get_data(as_text=True), "data-person-structured-data")
    assert set(data) == {"@context", "@type", "name", "url"}


def test_author_json_ld_identity_topics_and_evidence(client, app, token):
    from app.models.taxonomy import Topic

    _add(app, Topic(slug="leadership", name="Leadership", status="published"),
         Topic(slug="secret-topic", name="Secret Draft Topic", status="draft"))
    slug = _create(client, token, "authors", role="Contributor", website="https://writer.example.com",
                   social={"linkedin": "writer", "instagram": "writer_ig"}, topicSlugs=["leadership", "secret-topic"],
                   expertise=["leadership", "Climate finance"], sources=[SOURCE_A]).get_json()["data"]["slug"]
    html = client.get(f"/authors/{slug}").get_data(as_text=True)
    data = _json_ld(html, "data-author-structured-data")
    assert data["jobTitle"] == "Contributor"
    assert data["sameAs"] == ["https://writer.example.com", "https://linkedin.com/in/writer", "https://instagram.com/writer_ig"]
    assert data["knowsAbout"] == [{"@type": "Thing", "name": "Leadership", "url": f"{SITE}/topics/leadership"}, "Climate finance"]
    assert data["subjectOf"][0]["url"] == SOURCE_A_STORED["url"]
    assert SOURCE_A_STORED["url"] not in data["sameAs"]
    assert "Secret Draft Topic" not in html
    for invented in ("worksFor", "award", "hasCredential"):
        assert invented not in data


def test_author_json_ld_minimal_has_no_empty_fields(client, token):
    slug = _create(client, token, "authors").get_json()["data"]["slug"]
    data = _json_ld(client.get(f"/authors/{slug}").get_data(as_text=True), "data-author-structured-data")
    assert set(data) == {"@context", "@type", "name", "url"}


# --- pre-deploy correction: public-host sources (Article/Person/Author) ---------------------------


NON_PUBLIC_URLS = [
    "https://localhost/source",
    "http://localhost:8000/x",
    "https://foo.localhost/x",
    "https://intranet/report",
    "https://127.0.0.1/source",
    "https://192.168.1.20/report",
    "https://10.0.0.5:8443/report",
    "https://[::1]/source",
    "https://[2001:db8::1]/x",
]
PUBLIC_URLS = [
    "https://example.com/report",
    "https://news.example.org/story",
    "https://www.ilo.org/report",
    "https://sub.domain.co.ke/source",
    "http://example.com:8080/path?q=1",
]


def _create_any(client, token, kind, sources):
    if kind == "articles":
        author = _create(client, token, "authors", name="Article Host Author").get_json()["data"]["slug"]
        return client.post("/api/v1/articles", json={"title": "Host Story", "authorSlug": author, "status": "draft",
                                                     "content": [], "sources": sources}, headers=auth_headers(token))
    return _create(client, token, kind, sources=sources)


@pytest.mark.parametrize("kind", ["articles", "people", "authors"])
@pytest.mark.parametrize("url", NON_PUBLIC_URLS)
def test_non_public_source_hosts_rejected_everywhere(client, token, kind, url):
    resp = _create_any(client, token, kind, [{"title": "Internal", "url": url}])
    assert resp.status_code in (400, 422), url
    details = resp.get_json()["error"]["details"]["sources"]
    assert details == {"0": {"url": ["Source URL must use a public domain name."]}}


@pytest.mark.parametrize("kind", ["articles", "people", "authors"])
def test_public_source_domains_accepted_everywhere(client, token, kind):
    sources = [{"title": f"S{i}", "url": url} for i, url in enumerate(PUBLIC_URLS)]
    resp = _create_any(client, token, kind, sources)
    assert resp.status_code == 201, resp.get_json()
    assert [s["url"] for s in resp.get_json()["data"]["sources"]] == PUBLIC_URLS


# --- pre-deploy correction: Author legacy expertise is preserved ---------------------------------


def test_author_expertise_preserved_on_omission_and_cleared_explicitly(client, token):
    slug = _create(client, token, "authors", expertise=["Leadership", "Climate finance"]).get_json()["data"]["slug"]
    base = dict(KINDS["authors"][0], slug=slug)
    for edit in ({"sources": [SOURCE_B]}, {"role": "Editor"}, {"bio": [{"type": "paragraph", "text": "New bio."}]}):
        resp = client.put(f"/api/v1/authors/{slug}", json=dict(base, **edit), headers=auth_headers(token))
        assert resp.status_code == 200, resp.get_json()
        assert resp.get_json()["data"]["expertise"] == ["Leadership", "Climate finance"], edit
    resp = client.put(f"/api/v1/authors/{slug}", json=dict(base, expertise=["Mentoring"]), headers=auth_headers(token))
    assert resp.get_json()["data"]["expertise"] == ["Mentoring"]
    resp = client.put(f"/api/v1/authors/{slug}", json=dict(base, expertise=[]), headers=auth_headers(token))
    assert resp.get_json()["data"]["expertise"] == []


def test_new_author_without_expertise_gets_empty_list(client, token):
    assert _create(client, token, "authors").get_json()["data"]["expertise"] == []


def test_author_knows_about_keeps_preserved_expertise_after_unrelated_save(client, app, token):
    from app.models.taxonomy import Topic

    _add(app, Topic(slug="leadership", name="Leadership", status="published"),
         Topic(slug="secret-topic", name="Secret Draft Topic", status="draft"))
    slug = _create(client, token, "authors", topicSlugs=["leadership", "secret-topic"],
                   expertise=["LEADERSHIP", "Climate finance"]).get_json()["data"]["slug"]
    # An editor opens the Author only to add a source (expertise omitted).
    client.put(f"/api/v1/authors/{slug}", json=dict(KINDS["authors"][0], slug=slug, topicSlugs=["leadership", "secret-topic"],
                                                    sources=[SOURCE_A]), headers=auth_headers(token))
    html = client.get(f"/authors/{slug}").get_data(as_text=True)
    data = _json_ld(html, "data-author-structured-data")
    assert data["knowsAbout"] == [{"@type": "Thing", "name": "Leadership", "url": f"{SITE}/topics/leadership"}, "Climate finance"]
    assert "Secret Draft Topic" not in html
