"""AI Search / GEO Phase 3A — Article sources/references (Article.sources)
and the entity-rich Article JSON-LD built from existing editorial
relationships (citation/articleSection/about/mentions/keywords).
"""
import json
import os
import re

import pytest

from app.extensions import db
from app.services import indexnow
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"

SOURCE_A = {
    "title": "  World Employment and Social Outlook: Trends 2026 ",
    "url": " https://ilo.org/weso-2026 ",
    "publisher": "International Labour Organization",
    "author": "ILO Research Department",
    "publishedDate": "2026-01-15",
    "note": "Global employment figures cited in section 2.",
}
SOURCE_B = {"title": "Women in the Workplace", "url": "https://example.org/wiw", "publisher": "", "note": "   "}


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


@pytest.fixture()
def token(client, app):
    from app.models.user import Role, User

    payload = {"email": "sources-admin@example.com", "password": "supersecret1", "first_name": "Sou",
               "last_name": "Rce", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


@pytest.fixture()
def author_slug(client, token):
    return client.post("/api/v1/authors", json={"name": "Source Author"}, headers=auth_headers(token)).get_json()["data"]["slug"]


def _payload(author_slug, **overrides):
    payload = {"title": "Evidence Story", "authorSlug": author_slug, "status": "published",
               "content": [{"type": "paragraph", "text": "Body text."}]}
    payload.update(overrides)
    return payload


def _create(client, token, author_slug, **overrides):
    return client.post("/api/v1/articles", json=_payload(author_slug, **overrides), headers=auth_headers(token))


# --- validation / persistence ----------------------------------------------------


def test_sources_are_normalized_and_persisted(client, token, author_slug):
    resp = _create(client, token, author_slug, sources=[SOURCE_A, SOURCE_B])
    assert resp.status_code == 201, resp.get_json()
    assert resp.get_json()["data"]["sources"] == [
        {
            "title": "World Employment and Social Outlook: Trends 2026",
            "url": "https://ilo.org/weso-2026",
            "publisher": "International Labour Organization",
            "author": "ILO Research Department",
            "publishedDate": "2026-01-15",
            "note": "Global employment figures cited in section 2.",
        },
        {"title": "Women in the Workplace", "url": "https://example.org/wiw"},
    ]


def test_existing_and_new_articles_default_to_no_sources(client, token, author_slug):
    resp = _create(client, token, author_slug)
    assert resp.get_json()["data"]["sources"] == []


@pytest.mark.parametrize("bad", [
    {"title": "X", "url": "javascript:alert(1)"},
    {"title": "X", "url": "data:text/html,<script>alert(1)</script>"},
    {"title": "X", "url": ""},
    {"title": "X", "url": "   "},
    {"title": "X", "url": "not a url"},
    {"title": "X", "url": "ftp://example.org/file"},
    {"title": "X", "url": "https://"},
    {"title": "", "url": "https://example.org"},
    {"title": "   ", "url": "https://example.org"},
    {"url": "https://example.org"},
    {"title": "X"},
    {"title": "X" * 301, "url": "https://example.org"},
    {"title": "X", "url": "https://example.org/" + "a" * 2048},
    {"title": "X", "url": "https://example.org", "publisher": "P" * 251},
    {"title": "X", "url": "https://example.org", "note": "N" * 501},
    {"title": "X", "url": "https://example.org", "publishedDate": "15/01/2026"},
    # Pre-deploy correction: a source must be on a public domain name.
    {"title": "X", "url": "https://localhost/source"},
    {"title": "X", "url": "https://127.0.0.1/source"},
])
def test_invalid_sources_are_rejected(client, token, author_slug, bad):
    resp = _create(client, token, author_slug, sources=[bad])
    assert resp.status_code in (400, 422)
    assert "sources" in json.dumps(resp.get_json()["error"])


def test_duplicate_source_urls_rejected_after_trimming(client, token, author_slug):
    resp = _create(client, token, author_slug, sources=[
        {"title": "A", "url": "https://example.com/report"},
        {"title": "B", "url": " https://example.com/report "},
    ])
    assert resp.status_code in (400, 422)
    assert "listed more than once" in json.dumps(resp.get_json())


def test_source_cap(client, token, author_slug):
    many = [{"title": f"S{i}", "url": f"https://example.org/{i}"} for i in range(51)]
    assert _create(client, token, author_slug, sources=many).status_code in (400, 422)
    assert _create(client, token, author_slug, sources=many[:50]).status_code == 201


def test_update_keeps_sources_unless_sent_and_clears_with_empty_list(client, token, author_slug):
    slug = _create(client, token, author_slug, sources=[SOURCE_B]).get_json()["data"]["slug"]
    resp = client.put(f"/api/v1/articles/{slug}", json=_payload(author_slug, slug=slug, title="Edited"), headers=auth_headers(token))
    assert resp.get_json()["data"]["sources"] == [{"title": "Women in the Workplace", "url": "https://example.org/wiw"}]
    resp = client.put(f"/api/v1/articles/{slug}", json=_payload(author_slug, slug=slug, sources=[]), headers=auth_headers(token))
    assert resp.get_json()["data"]["sources"] == []


def test_revision_snapshot_includes_sources(client, app, token, author_slug):
    from app.models.article import Article, ArticleRevision

    slug = _create(client, token, author_slug, sources=[SOURCE_B]).get_json()["data"]["slug"]
    client.put(f"/api/v1/articles/{slug}", json=_payload(author_slug, slug=slug, sources=[SOURCE_A]), headers=auth_headers(token))
    with app.app_context():
        article = Article.query.filter_by(slug=slug).first()
        revisions = ArticleRevision.query.filter_by(article_id=article.id).order_by(ArticleRevision.id).all()
        assert [r.data["sources"][0]["url"] for r in revisions] == ["https://example.org/wiw", "https://ilo.org/weso-2026"]


def test_public_detail_has_sources_but_lists_do_not(client, token, author_slug):
    slug = _create(client, token, author_slug, sources=[SOURCE_B]).get_json()["data"]["slug"]
    assert client.get(f"/api/v1/articles/{slug}").get_json()["data"]["sources"][0]["url"] == "https://example.org/wiw"
    public_list = client.get("/api/v1/articles").get_json()["data"]
    assert public_list and all("sources" not in item for item in public_list)
    admin_list = client.get("/api/v1/articles", headers=auth_headers(token)).get_json()["data"]
    assert admin_list and all("sources" not in item for item in admin_list)


def test_published_source_edit_uses_existing_indexnow_update(client, app, token, author_slug, monkeypatch):
    calls = []
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY="test-indexnow-key-1234", PUBLIC_SITE_URL=SITE)
    monkeypatch.setattr(indexnow, "_post_json", lambda url, payload, timeout: calls.append(payload["urlList"]) or 200)
    slug = _create(client, token, author_slug).get_json()["data"]["slug"]
    calls.clear()
    client.put(f"/api/v1/articles/{slug}", json=_payload(author_slug, slug=slug, sources=[SOURCE_B]), headers=auth_headers(token))
    assert calls == [[f"{SITE}/{slug}"]]


# --- server HTML / prerender ------------------------------------------------------


def _root(html):
    return re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL).group(1)


def _json_scripts(html, attr):
    return re.findall(rf"<script\b[^>]*{re.escape(attr)}[^>]*>(.*?)</script>", html, re.DOTALL)


def test_sources_in_initial_server_html(client, token, author_slug):
    hostile = {"title": "<script>alert(1)</script>Report", "url": "https://example.org/hostile",
               "note": "<img src=x onerror=alert(1)>", "publisher": "Pub & Co"}
    slug = _create(client, token, author_slug, sources=[SOURCE_A, hostile]).get_json()["data"]["slug"]
    html = client.get(f"/{slug}").get_data(as_text=True)
    root = _root(html)
    assert '<section aria-labelledby="article-sources"' in root
    assert '<h2 id="article-sources"' in root and "Sources &amp; references</h2>" in root
    assert "<ol " in root
    assert '<a href="https://ilo.org/weso-2026" target="_blank" rel="noopener noreferrer"' in root
    assert "World Employment and Social Outlook: Trends 2026</a>" in root
    assert "International Labour Organization" in root and "ILO Research Department" in root
    assert '<time datetime="2026-01-15">January 15, 2026</time>' in root
    assert "Global employment figures cited in section 2." in root
    # Plain text only: hostile values are escaped, never markup.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;Report" in root
    assert "&lt;img src=x onerror=alert(1)&gt;" in root
    assert "<script>alert" not in root and "<img src=x" not in root
    assert "Pub &amp; Co" in root
    for rel in ("nofollow", "sponsored", "ugc"):
        assert rel not in root
    # Each source appears once in the visible prerender.
    assert root.count("https://ilo.org/weso-2026") == 1
    assert len(_json_scripts(html, 'data-wsf-bootstrap="article"')) == 1
    assert len(_json_scripts(html, "data-article-structured-data")) == 1


def test_no_sources_means_no_section_and_no_citation(client, token, author_slug):
    slug = _create(client, token, author_slug).get_json()["data"]["slug"]
    html = client.get(f"/{slug}").get_data(as_text=True)
    assert "article-sources" not in html
    assert "citation" not in json.loads(_json_scripts(html, "data-article-structured-data")[0])


# --- entity-rich Article JSON-LD -----------------------------------------------------


def test_article_json_ld_entity_fields(client, app, token, author_slug):
    from app.models.article import Article
    from app.models.people import Organization, Person
    from app.models.taxonomy import Category, Tag, Topic

    slug = _create(client, token, author_slug, sources=[SOURCE_A, SOURCE_B]).get_json()["data"]["slug"]
    with app.app_context():
        article = Article.query.filter_by(slug=slug).first()
        category = Category(slug="careers", name="Careers", status="published")
        topics = [Topic(slug="leadership", name="Leadership", status="published"),
                  Topic(slug="hidden-topic", name="Hidden Topic", status="archived")]
        tags = [Tag(slug="pay", name="Pay", status="published"), Tag(slug="leadership-tag", name="leadership", status="published"),
                Tag(slug="old-tag", name="Old Tag", status="archived")]
        people = [Person(slug="amara", name="Amara Okafor", status="published"),
                  Person(slug="draft-person", name="Draft Person Name", status="draft")]
        orgs = [Organization(slug="kaziwave", name="Kaziwave Labs", status="published", description=[]),
                Organization(slug="old-org", name="Archived Org Name", status="archived", description=[])]
        db.session.add_all([category, *topics, *tags, *people, *orgs])
        db.session.flush()
        article.category_id = category.id
        article.topics = topics
        article.tags = tags
        article.related_people = people
        article.related_organizations = orgs
        db.session.commit()

    html = client.get(f"/{slug}").get_data(as_text=True)
    data = json.loads(_json_scripts(html, "data-article-structured-data")[0])
    assert data["articleSection"] == "Careers"
    assert data["keywords"] == "Leadership, Pay"
    assert data["about"] == [
        {"@type": "Thing", "name": "Leadership", "url": f"{SITE}/topics/leadership"},
        {"@type": "Thing", "name": "Careers"},
    ]
    assert data["mentions"] == [
        {"@type": "Person", "name": "Amara Okafor", "url": f"{SITE}/people/amara"},
        {"@type": "Organization", "name": "Kaziwave Labs", "url": f"{SITE}/organizations/kaziwave"},
    ]
    assert data["citation"] == [
        {
            "@type": "CreativeWork",
            "name": "World Employment and Social Outlook: Trends 2026",
            "url": "https://ilo.org/weso-2026",
            "author": {"@type": "Thing", "name": "ILO Research Department"},
            "publisher": {"@type": "Organization", "name": "International Labour Organization"},
            "datePublished": "2026-01-15",
        },
        {"@type": "CreativeWork", "name": "Women in the Workplace", "url": "https://example.org/wiw"},
    ]
    structured = _json_scripts(html, "data-article-structured-data")[0]
    for private in ("Draft Person Name", "Archived Org Name", "Hidden Topic", "Old Tag", "Global employment figures"):
        assert private not in structured


def test_article_section_falls_back_to_first_published_topic(client, app, token, author_slug):
    from app.models.article import Article
    from app.models.taxonomy import Category, Topic

    slug = _create(client, token, author_slug).get_json()["data"]["slug"]
    with app.app_context():
        article = Article.query.filter_by(slug=slug).first()
        draft_category = Category(slug="draft-cat", name="Draft Category", status="archived")
        db.session.add(draft_category)
        db.session.flush()
        article.category_id = draft_category.id
        article.topics = [Topic(slug="money", name="Money", status="published")]
        db.session.commit()
    data = json.loads(_json_scripts(client.get(f"/{slug}").get_data(as_text=True), "data-article-structured-data")[0])
    assert data["articleSection"] == "Money"
    assert "Draft Category" not in json.dumps(data)
