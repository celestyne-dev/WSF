"""AI Search / GEO Phase 4C — Topic & Series editorial authority: long-form
content, Sources & references, the curated featured ("Start here")
Article, Topic contributors (existing author_topics) and Series people
(existing person_series), with server-rendered parity and strict public
gating.
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
SOURCE = {"title": "Women in the Workplace 2026", "url": "https://example.org/wiw-2026", "publisher": "Example Institute"}
CONTENT = [
    {"type": "heading", "level": 2, "text": "Why EDITORIAL-HEADING matters"},
    {"type": "paragraph", "text": "EDITORIAL-BODY-TEXT with <strong>emphasis</strong>."},
]
HOSTILE_CONTENT = [
    {"type": "paragraph", "text": 'Safe <script>alert(1)</script><b onclick="x()">bold</b> <a href="javascript:alert(1)">bad</a>'},
    {"type": "heading", "level": 2, "text": "Head <img src=x onerror=alert(1)>"},
    {"type": "list", "items": ["one", "<script>two</script>", '<a href="javascript:alert(2)" onclick="y()">three</a>']},
]
# kind -> (admin collection path, public prefix, public detail key, people key)
KINDS = {
    "topics": ("/api/v1/admin/taxonomy/topics", "topics", "topic", "contributors"),
    "series": ("/api/v1/admin/taxonomy/series", "series", "series", "people"),
}


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


@pytest.fixture()
def token(client, app):
    from app.models.user import Role, User

    payload = {"email": "depth-admin@example.com", "password": "supersecret1", "first_name": "Dep",
               "last_name": "Th", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


def _add(app, *objs):
    with app.app_context():
        db.session.add_all(objs)
        db.session.commit()
        return [o.id for o in objs]


def _author(app, slug="depth-author", status="active", **kw):
    from app.models.people import Author

    return _add(app, Author(slug=slug, name=kw.pop("name", slug.replace("-", " ").title()), status=status, **kw))[0]


def _article(app, slug, title, status="published", **kw):
    from app.models.article import Article

    author_id = _author(app, slug=f"by-{slug}") if "author_id" not in kw else kw.pop("author_id")
    return _add(app, Article(slug=slug, title=title, status=status, author_id=author_id, excerpt=f"{title} excerpt.",
                             content=[{"type": "paragraph", "text": "x"}], **kw))[0]


def _create(client, token, kind, **fields):
    payload = {"name": fields.pop("name", f"Depth {kind}"), "status": "published"}
    payload.update(fields)
    resp = client.post(KINDS[kind][0], json=payload, headers=auth_headers(token))
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["data"]


def _update(client, token, kind, entity_id, **fields):
    return client.put(f"{KINDS[kind][0]}/{entity_id}", json=fields, headers=auth_headers(token))


def _public(client, kind, slug):
    body = client.get(f"/api/v1/{KINDS[kind][1]}/{slug}").get_json()["data"]
    return body[KINDS[kind][2]], body


def _root(html):
    return re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL).group(1)


# --- migration -------------------------------------------------------------------------------------


def _migration():
    return importlib.import_module("migrations.versions.f2c6a8e4d1b9_topic_series_editorial_depth")


def test_migration_single_head_after_profile_credentials():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    module = _migration()
    assert module.revision == "f2c6a8e4d1b9" and module.down_revision == "e7a1c4d9b2f6"
    config = Config()
    config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
    assert ScriptDirectory.from_config(config).get_heads() == ["f2c6a8e4d1b9"]


def test_migration_backfills_existing_rows_and_downgrades_cleanly():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE articles (id INTEGER PRIMARY KEY)"))
        for table in ("topics", "series"):
            conn.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT)"))
            conn.execute(sa.text(f"INSERT INTO {table} (name) VALUES ('Existing')"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        for table in ("topics", "series"):
            row = conn.execute(sa.text(f"SELECT content, sources, featured_article_id FROM {table}")).one()
            assert json.loads(row[0]) == [] and json.loads(row[1]) == [] and row[2] is None
            cols = {c["name"]: c for c in sa.inspect(conn).get_columns(table)}
            assert cols["content"]["nullable"] is False and cols["sources"]["nullable"] is False
            fks = sa.inspect(conn).get_foreign_keys(table)
            assert any(fk["referred_table"] == "articles" and fk["options"].get("ondelete") == "SET NULL" for fk in fks)
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        for table in ("topics", "series"):
            assert {c["name"] for c in sa.inspect(conn).get_columns(table)} == {"id", "name"}


def test_new_rows_default_to_empty_depth(app):
    from app.models.taxonomy import Series, Topic

    with app.app_context():
        topic, series = Topic(slug="t-default", name="T"), Series(slug="s-default", name="S")
        db.session.add_all([topic, series])
        db.session.commit()
        for entity in (topic, series):
            assert entity.content == [] and entity.sources == [] and entity.featured_article_id is None


# --- editorial fields: validation, sanitization, update semantics ----------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_supported_hostile_content_is_sanitized(client, token, kind):
    entity = _create(client, token, kind, content=HOSTILE_CONTENT)
    stored = json.dumps(entity["content"])
    for unsafe in ("<script", "onclick", "javascript:", "onerror"):
        assert unsafe not in stored, unsafe
    paragraph, heading, items = entity["content"][0]["text"], entity["content"][1]["text"], entity["content"][2]["items"]
    assert paragraph.startswith("Safe") and "<b>bold</b>" in paragraph and "<a>bad</a>" in paragraph
    assert heading == "Head"  # headings are plain text
    assert items == ["one", "two", "<a>three</a>"]
    root = _root(client.get(f"/{KINDS[kind][1]}/{entity['slug']}").get_data(as_text=True))
    assert "Safe" in root and "<b>bold</b>" in root
    for unsafe in ("<script", "onclick", "javascript:", "onerror"):
        assert unsafe not in root, unsafe


UNSUPPORTED_BLOCKS = [
    {"type": "raw_html", "html": "<iframe src=https://evil.example></iframe>"},
    {"type": "button", "label": "Go", "url": "https://example.org"},
    {"type": "articleCard", "slug": "some-story"},
    {"type": "footerNote", "text": "Footer"},
    {"type": "newsletterCta"},
    {"type": "madeUpBlock", "text": "x"},
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("block", UNSUPPORTED_BLOCKS, ids=lambda b: b["type"])
def test_unsupported_block_types_rejected_and_nothing_persisted(client, app, token, kind, block):
    from app.models.taxonomy import Series, Topic

    model = Topic if kind == "topics" else Series
    resp = client.post(KINDS[kind][0], json={"name": f"Rejected {block['type']}", "content": [CONTENT[1], block]},
                       headers=auth_headers(token))
    assert resp.status_code in (400, 422)
    assert resp.get_json()["error"]["details"]["content"] == [f"Unsupported content block type: {block['type']}."]
    with app.app_context():
        assert model.query.filter_by(name=f"Rejected {block['type']}").first() is None
    # Update is rejected too, and the stored content is left untouched.
    entity = _create(client, token, kind, name=f"Kept {block['type']}", content=CONTENT)
    resp = _update(client, token, kind, entity["id"], content=[block])
    assert resp.status_code in (400, 422)
    with app.app_context():
        assert db.session.get(model, entity["id"]).content == entity["content"]
    assert [b["type"] for b in _public(client, kind, entity["slug"])[0]["content"]] == ["heading", "paragraph"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad", [["not a block"], [{"text": "no type"}], [{"type": 7}]])
def test_malformed_blocks_rejected(client, token, kind, bad):
    resp = client.post(KINDS[kind][0], json={"name": "Malformed", "content": bad}, headers=auth_headers(token))
    assert resp.status_code in (400, 422) and "content" in resp.get_json()["error"]["details"]


ALL_SUPPORTED_BLOCKS = [
    {"type": "paragraph", "text": "Paragraph text."},
    {"type": "heading", "level": 2, "text": "A heading"},
    {"type": "list", "style": "bullet", "items": ["One", "Two"]},
    {"type": "blockquote", "text": "A quote.", "attribution": "Someone"},
    {"type": "pullquote", "text": "A pullquote."},
    {"type": "image", "src": "https://example.org/a.jpg", "alt": "Alt text", "caption": "Caption"},
    {"type": "highlight", "title": "Note", "text": "Highlighted."},
    {"type": "divider"},
]


@pytest.mark.parametrize("kind", KINDS)
def test_all_eight_supported_block_types_accepted(client, token, kind):
    entity = _create(client, token, kind, content=ALL_SUPPORTED_BLOCKS)
    assert [b["type"] for b in entity["content"]] == [b["type"] for b in ALL_SUPPORTED_BLOCKS]
    body = _update(client, token, kind, entity["id"], content=ALL_SUPPORTED_BLOCKS[:3]).get_json()["data"]
    assert [b["type"] for b in body["content"]] == ["paragraph", "heading", "list"]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad", [
    {"title": "X", "url": "https://localhost/x"},
    {"title": "X", "url": "https://127.0.0.1/x"},
    {"title": "X", "url": "javascript:alert(1)"},
    {"title": "", "url": "https://example.org"},
])
def test_invalid_sources_rejected(client, token, kind, bad):
    resp = client.post(KINDS[kind][0], json={"name": "Bad Sources", "sources": [bad]}, headers=auth_headers(token))
    assert resp.status_code in (400, 422) and "sources" in json.dumps(resp.get_json()["error"])


@pytest.mark.parametrize("kind", KINDS)
def test_duplicate_source_and_cap(client, token, kind):
    dup = [{"title": "A", "url": "https://example.com/r"}, {"title": "B", "url": " https://example.com/r "}]
    resp = client.post(KINDS[kind][0], json={"name": "Dup", "sources": dup}, headers=auth_headers(token))
    assert resp.status_code in (400, 422) and "listed more than once" in json.dumps(resp.get_json())
    many = [{"title": f"S{i}", "url": f"https://example.org/{i}"} for i in range(51)]
    resp = client.post(KINDS[kind][0], json={"name": "Many", "sources": many}, headers=auth_headers(token))
    assert resp.status_code in (400, 422) and "at most 50 sources" in json.dumps(resp.get_json())


@pytest.mark.parametrize("kind", KINDS)
def test_omitted_fields_preserved_explicit_values_clear(client, app, token, kind):
    article_id = _article(app, "cornerstone", "Cornerstone Story")
    entity = _create(client, token, kind, content=CONTENT, sources=[SOURCE], featuredArticleId=article_id)
    assert entity["featured_article_id"] == article_id and len(entity["content"]) == 2 and entity["sources"] == [SOURCE]
    # An unrelated SEO/status edit omits all three -> untouched.
    resp = _update(client, token, kind, entity["id"], seo={"title": "New SEO"}, description="Short summary.")
    body = resp.get_json()["data"]
    assert resp.status_code == 200
    assert body["featured_article_id"] == article_id and len(body["content"]) == 2 and body["sources"] == [SOURCE]
    status = client.put(f"{KINDS[kind][0]}/{entity['id']}/status", json={"status": "published"}, headers=auth_headers(token))
    assert status.get_json()["data"]["featured_article_id"] == article_id
    # Explicit empty/null values clear.
    body = _update(client, token, kind, entity["id"], content=[], sources=[], featuredArticleId=None).get_json()["data"]
    assert body["content"] == [] and body["sources"] == [] and body["featured_article_id"] is None


@pytest.mark.parametrize("kind", KINDS)
def test_nonexistent_featured_article_rejected(client, token, kind):
    resp = client.post(KINDS[kind][0], json={"name": "Ghost", "featuredArticleId": 999999}, headers=auth_headers(token))
    assert resp.status_code == 400
    assert resp.get_json()["error"]["details"] == {"featuredArticleId": ["Article not found."]}


@pytest.mark.parametrize("kind", KINDS)
def test_deleting_featured_article_sets_null(client, app, token, kind):
    from app.models.article import Article
    from app.models.taxonomy import Series, Topic

    article_id = _article(app, "doomed", "Doomed Story")
    entity = _create(client, token, kind, featuredArticleId=article_id)
    with app.app_context():
        db.session.delete(db.session.get(Article, article_id))
        db.session.commit()
        model = Topic if kind == "topics" else Series
        assert db.session.get(model, entity["id"]).featured_article_id is None
    assert _public(client, kind, entity["slug"])[0]["featured_article"] is None


# --- featured Article public gating ------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("status", ["draft", "archived"])
def test_non_published_featured_article_kept_in_cms_hidden_publicly(client, app, token, kind, status):
    article_id = _article(app, f"secret-{status}", f"Secret {status.title()} Story", status=status)
    entity = _create(client, token, kind, featuredArticleId=article_id)
    admin = client.get(f"{KINDS[kind][0]}/{entity['id']}", headers=auth_headers(token)).get_json()["data"]
    assert admin["featured_article_id"] == article_id and admin["featured_article"]["status"] == status
    public, _ = _public(client, kind, entity["slug"])
    assert public["featured_article"] is None and "featured_article_id" not in public
    html = client.get(f"/{KINDS[kind][1]}/{entity['slug']}").get_data(as_text=True)
    for leak in (f"Secret {status.title()} Story", f"secret-{status}", "Start here"):
        assert leak not in html, leak


@pytest.mark.parametrize("kind", KINDS)
def test_published_featured_article_public_summary(client, app, token, kind):
    article_id = _article(app, "start-here-story", "Start Here Story")
    entity = _create(client, token, kind, featuredArticleId=article_id)
    public, _ = _public(client, kind, entity["slug"])
    featured = public["featured_article"]
    assert featured["slug"] == "start-here-story" and featured["title"] == "Start Here Story"
    assert "content" not in featured  # the lightweight public summary, not the full Article


# --- contributors / people -----------------------------------------------------------------------------


def test_topic_contributors_are_active_authors_with_the_topic(client, app, token):
    from app.models.people import Author
    from app.models.taxonomy import Topic

    topic = _create(client, token, "topics", name="Leadership Depth")
    with app.app_context():
        t = db.session.get(Topic, topic["id"])
        other = Topic(slug="other-topic", name="Other", status="published")
        db.session.add(other)
        db.session.add_all([
            Author(slug="active-with", name="Active With", status="active", role="Editor", short_bio="Writes on leadership.",
                   topics=[t], sources=[SOURCE], credentials=[{"name": "MBA", "issuer": "SecretIssuerX"}]),
            Author(slug="active-without", name="Active Without", status="active", topics=[other]),
            Author(slug="draft-with", name="Draft With", status="draft", topics=[t]),
            Author(slug="archived-with", name="Archived With", status="archived", topics=[t]),
        ])
        db.session.commit()
    public, _ = _public(client, "topics", topic["slug"])
    assert public["contributors"] == [{"slug": "active-with", "name": "Active With", "role": "Editor",
                                       "short_bio": "Writes on leadership.", "photo": None}]
    root = _root(client.get(f"/topics/{topic['slug']}").get_data(as_text=True))
    assert "Contributors covering this topic" in root and 'href="/authors/active-with"' in root
    for leak in ("Active Without", "Draft With", "Archived With", "SecretIssuerX", SOURCE["url"], "user_id"):
        assert leak not in root and leak not in json.dumps(public), leak


def test_topic_contributors_are_bounded(client, app, token):
    from app.models.people import Author
    from app.models.taxonomy import Topic

    topic = _create(client, token, "topics", name="Busy Topic")
    with app.app_context():
        t = db.session.get(Topic, topic["id"])
        db.session.add_all([Author(slug=f"writer-{i}", name=f"Writer {i:02d}", status="active", topics=[t]) for i in range(9)])
        db.session.commit()
    names = [a["name"] for a in _public(client, "topics", topic["slug"])[0]["contributors"]]
    assert names == [f"Writer {i:02d}" for i in range(6)]


def test_series_people_are_published_people_in_the_series(client, app, token):
    from app.models.people import Person
    from app.models.taxonomy import Series

    series = _create(client, token, "series", name="Founders Depth")
    with app.app_context():
        s = db.session.get(Series, series["id"])
        db.session.add_all([
            Person(slug="pub-in", name="Published In", status="published", title="Founder", short_bio="Built it.",
                   series=[s], sources=[SOURCE], credentials=[{"name": "CPA", "issuer": "SecretIssuerY"}]),
            Person(slug="pub-out", name="Published Out", status="published"),
            Person(slug="draft-in", name="Draft In", status="draft", series=[s]),
            Person(slug="archived-in", name="Archived In", status="archived", series=[s]),
        ])
        db.session.commit()
    public, _ = _public(client, "series", series["slug"])
    assert public["people"] == [{"slug": "pub-in", "name": "Published In", "title": "Founder", "short_bio": "Built it.", "photo": None}]
    root = _root(client.get(f"/series/{series['slug']}").get_data(as_text=True))
    assert "People in this series" in root and 'href="/people/pub-in"' in root
    for leak in ("Published Out", "Draft In", "Archived In", "SecretIssuerY", SOURCE["url"]):
        assert leak not in root and leak not in json.dumps(public), leak


@pytest.mark.parametrize("org_status, shown", [("published", True), ("draft", False), ("archived", False)])
def test_series_sponsor_disclosure_published_only(client, app, token, org_status, shown):
    from app.models.people import Organization

    org_id = _add(app, Organization(slug=f"sponsor-{org_status}", name=f"Sponsor {org_status.title()} Org",
                                    status=org_status, description=[]))[0]
    series = _create(client, token, "series", name=f"Sponsored {org_status}", sponsorOrganizationId=org_id)
    admin = client.get(f"/api/v1/admin/taxonomy/series/{series['id']}", headers=auth_headers(token)).get_json()["data"]
    assert admin["sponsor_organization_id"] == org_id  # the editor can pre-select it
    public, _ = _public(client, "series", series["slug"])
    root = _root(client.get(f"/series/{series['slug']}").get_data(as_text=True))
    name = f"Sponsor {org_status.title()} Org"
    if shown:
        assert public["sponsor_organization"] == {"slug": f"sponsor-{org_status}", "name": name, "logo": None}
        assert f"Presented in partnership with {name}" in root
    else:
        assert public["sponsor_organization"] is None
        assert name not in root and name not in json.dumps(public)
    assert "sponsor_organization_id" not in public


# --- payloads: lists stay lightweight -----------------------------------------------------------------


def test_public_lists_and_previews_carry_no_depth(client, app, token):
    article_id = _article(app, "list-story", "List Story")
    for kind in KINDS:
        _create(client, token, kind, name=f"Listed {kind}", content=CONTENT, sources=[SOURCE], featuredArticleId=article_id)
    for path, extra in (("/api/v1/topics", "contributors"), ("/api/v1/series", "people")):
        items = client.get(path).get_json()["data"]
        assert items
        for item in items:
            for key in ("content", "sources", "featured_article", "featured_article_id", extra):
                assert key not in item, (path, key)
        assert "EDITORIAL-BODY-TEXT" not in json.dumps(items) and SOURCE["url"] not in json.dumps(items)
    for kind in KINDS:  # admin lists too
        items = client.get(KINDS[kind][0], headers=auth_headers(token)).get_json()["data"]
        assert all("content" not in i and "sources" not in i for i in items)
    for page in ("/topics", "/series"):
        html = client.get(page).get_data(as_text=True)
        assert "EDITORIAL-BODY-TEXT" not in html and SOURCE["url"] not in html


# --- detail API + raw HTML -----------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_detail_api_contract_preserved_and_extended(client, app, token, kind):
    article_id = _article(app, f"{kind}-feature", "Featured Depth Story")
    entity = _create(client, token, kind, content=CONTENT, sources=[SOURCE], featuredArticleId=article_id)
    public, body = _public(client, kind, entity["slug"])
    assert set(body) == {KINDS[kind][2], "articles"}
    assert public["content"][1]["text"] == "EDITORIAL-BODY-TEXT with <strong>emphasis</strong>."
    assert public["sources"] == [SOURCE] and public["featured_article"]["slug"] == f"{kind}-feature"
    assert KINDS[kind][3] in public
    meta = client.get(f"/api/v1/{KINDS[kind][1]}/{entity['slug']}").get_json()["meta"]
    assert "pagination" in meta or "page" in json.dumps(meta)


@pytest.mark.parametrize("kind", KINDS)
def test_raw_html_editorial_depth_in_order(client, app, token, kind):
    from app.models.people import Author, Person
    from app.models.taxonomy import Series, Topic

    article_id = _article(app, f"{kind}-cornerstone", "Cornerstone Depth Story")
    entity = _create(client, token, kind, description="SHORT-DESCRIPTION.", content=CONTENT, sources=[SOURCE],
                     featuredArticleId=article_id, **({"subtitle": "SERIES-SUBTITLE"} if kind == "series" else {}))
    with app.app_context():
        if kind == "topics":
            db.session.add(Author(slug="depth-writer", name="Depth Writer", status="active",
                                  topics=[db.session.get(Topic, entity["id"])]))
        else:
            db.session.add(Person(slug="depth-person", name="Depth Person", status="published",
                                  series=[db.session.get(Series, entity["id"])]))
        db.session.commit()
    html = client.get(f"/{KINDS[kind][1]}/{entity['slug']}").get_data(as_text=True)
    root = _root(html)
    assert len(re.findall(r"<h1\b", root)) == 1 and f">{entity['name']}</h1>" in root
    assert root.count("SHORT-DESCRIPTION.") == 1
    assert "EDITORIAL-HEADING" in root and "EDITORIAL-BODY-TEXT with <strong>emphasis</strong>." in root
    assert f'href="/{kind}-cornerstone"' in root and "Cornerstone Depth Story" in root
    people_heading, link = (("Contributors covering this topic", 'href="/authors/depth-writer"') if kind == "topics"
                            else ("People in this series", 'href="/people/depth-person"'))
    assert people_heading in root and link in root
    assert f'<a href="{SOURCE["url"]}" target="_blank" rel="noopener noreferrer"' in root
    # Server order matches React: content -> Start here -> people -> sources.
    order = [root.index("EDITORIAL-BODY-TEXT"), root.index("Start here"), root.index(people_heading),
             root.index("Sources &amp; references")]
    assert order == sorted(order)
    for once in ("Start here</h2>", f"{people_heading}</h2>", "Sources &amp; references</h2>"):
        assert root.count(once) == 1, once
    if kind == "series":
        assert root.index("SERIES-SUBTITLE") < root.index("SHORT-DESCRIPTION.")
    for claim in ("Verified", "Fact checked", "verified", "experts"):
        assert claim not in root


@pytest.mark.parametrize("kind", KINDS)
def test_empty_depth_renders_cleanly(client, token, kind):
    entity = _create(client, token, kind, description="Only a short description.")
    public, _ = _public(client, kind, entity["slug"])
    assert public["content"] == [] and public["sources"] == [] and public["featured_article"] is None
    assert public[KINDS[kind][3]] == []
    root = _root(client.get(f"/{KINDS[kind][1]}/{entity['slug']}").get_data(as_text=True))
    assert "Only a short description." in root
    for heading in ("Start here", "Contributors covering this topic", "People in this series", "Sources &amp; references"):
        assert heading not in root, heading


@pytest.mark.parametrize("kind", KINDS)
def test_seo_description_never_uses_long_content(client, token, kind):
    entity = _create(client, token, kind, description="Concise summary.", content=CONTENT)
    html = client.get(f"/{KINDS[kind][1]}/{entity['slug']}").get_data(as_text=True)
    desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']*)', html).group(1)
    assert desc == "Concise summary." and "EDITORIAL" not in desc


@pytest.mark.parametrize("kind", KINDS)
def test_no_new_entity_structured_data(client, token, kind):
    entity = _create(client, token, kind, content=CONTENT, sources=[SOURCE])
    html = client.get(f"/{KINDS[kind][1]}/{entity['slug']}").get_data(as_text=True)
    assert len(re.findall(r"<script\b[^>]*data-breadcrumb-structured-data", html)) == 1
    for schema_type in ("CollectionPage", "CreativeWorkSeries", "subjectOf", "sameAs\": [\"https://example.org"):
        assert schema_type not in html


@pytest.mark.parametrize("kind", KINDS)
def test_editorial_edit_uses_existing_indexnow_update(client, app, token, kind, monkeypatch):
    calls = []
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY="test-indexnow-key-1234", PUBLIC_SITE_URL=SITE)
    monkeypatch.setattr(indexnow, "_post_json", lambda url, payload, timeout: calls.append(payload["urlList"]) or 200)
    entity = _create(client, token, kind)
    calls.clear()
    _update(client, token, kind, entity["id"], content=CONTENT, sources=[SOURCE])
    assert calls == [[f"{SITE}/{KINDS[kind][1]}/{entity['slug']}"]]


@pytest.mark.parametrize("kind", KINDS)
def test_detail_query_count_is_bounded(client, app, token, kind):
    """Contributors/people are one bounded query (+ photos), not N+1."""
    from app.models.people import Author, Person
    from app.models.taxonomy import Series, Topic

    entity = _create(client, token, kind, content=CONTENT)
    with app.app_context():
        if kind == "topics":
            t = db.session.get(Topic, entity["id"])
            db.session.add_all([Author(slug=f"q-{i}", name=f"Q {i}", status="active", topics=[t]) for i in range(6)])
        else:
            s = db.session.get(Series, entity["id"])
            db.session.add_all([Person(slug=f"q-{i}", name=f"Q {i}", status="published", series=[s]) for i in range(8)])
        db.session.commit()
    counts = []
    with app.app_context():
        engine = db.engine
        listener = lambda *a, **k: counts.append(1)  # noqa: E731
        sa.event.listen(engine, "before_cursor_execute", listener)
        try:
            assert client.get(f"/api/v1/{KINDS[kind][1]}/{entity['slug']}").status_code == 200
        finally:
            sa.event.remove(engine, "before_cursor_execute", listener)
    assert len(counts) <= 12, len(counts)
