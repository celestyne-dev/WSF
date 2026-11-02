"""AI Search / GEO Phase 4B — profile credentials & qualifications
(Person.credentials / Author.credentials), `hasCredential`, and the Author
page as a schema.org ProfilePage (Person pages stay plain Person).
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

CREDENTIAL = {
    "name": "  Certified Digital Marketing Professional ",
    "category": " Professional certification ",
    "issuer": "Digital Marketing Institute",
    "url": " https://example.org/dmi ",
    "note": "Completed professional certification.",
}
CREDENTIAL_STORED = {
    "name": "Certified Digital Marketing Professional",
    "category": "Professional certification",
    "issuer": "Digital Marketing Institute",
    "url": "https://example.org/dmi",
    "note": "Completed professional certification.",
}
CREDENTIAL_LD = {
    "@type": "EducationalOccupationalCredential",
    "name": "Certified Digital Marketing Professional",
    "credentialCategory": "Professional certification",
    "recognizedBy": {"@type": "Organization", "name": "Digital Marketing Institute"},
    "url": "https://example.org/dmi",
}
SOURCE = {"title": "Appointed CEO of Example Bank", "url": "https://news.example.org/ceo-appointment",
          "publisher": "Example News", "author": "Business Desk", "publishedDate": "2025-06-30"}

KINDS = {
    "people": {"name": "Credential Person", "shortBio": "A leader.", "status": "published"},
    "authors": {"name": "Credential Author", "shortBio": "A writer.", "status": "active"},
}


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


@pytest.fixture()
def token(client, app):
    from app.models.user import Role, User

    payload = {"email": "credentials-admin@example.com", "password": "supersecret1", "first_name": "Cre",
               "last_name": "Dential", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    return client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]


def _create(client, token, kind, **overrides):
    payload = dict(KINDS[kind])
    payload.update(overrides)
    return client.post(f"/api/v1/{kind}", json=payload, headers=auth_headers(token))


def _detail(client, kind, slug, token=None):
    data = client.get(f"/api/v1/{kind}/{slug}", headers=auth_headers(token) if token else {}).get_json()["data"]
    return data["author"] if kind == "authors" else data


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


# --- migration -------------------------------------------------------------------------------------


def _migration():
    return importlib.import_module("migrations.versions.e7a1c4d9b2f6_profile_credentials")


def test_migration_single_head_after_profile_sources():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    module = _migration()
    assert module.revision == "e7a1c4d9b2f6" and module.down_revision == "d4b8e2a6f1c3"
    config = Config()
    config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
    assert ScriptDirectory.from_config(config).get_heads() == ["e7a1c4d9b2f6"]


def test_migration_backfills_existing_rows_and_downgrades_cleanly():
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    module = _migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        for table in ("people", "authors"):
            conn.execute(sa.text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, name TEXT, sources TEXT NOT NULL DEFAULT '[]')"))
            conn.execute(sa.text(f"INSERT INTO {table} (name) VALUES ('Existing')"))
        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()
        for table in ("people", "authors"):
            assert json.loads(conn.execute(sa.text(f"SELECT credentials FROM {table}")).scalar()) == []
            column = next(c for c in sa.inspect(conn).get_columns(table) if c["name"] == "credentials")
            assert column["nullable"] is False
        with Operations.context(MigrationContext.configure(conn)):
            module.downgrade()
        for table in ("people", "authors"):
            # Only `credentials` is removed — Phase 4A's `sources` stays.
            assert {c["name"] for c in sa.inspect(conn).get_columns(table)} == {"id", "name", "sources"}


def test_new_rows_default_to_empty_credentials(app):
    from app.models.people import Author, Person

    with app.app_context():
        person, author = Person(slug="p-cred-default", name="P"), Author(slug="a-cred-default", name="A")
        db.session.add_all([person, author])
        db.session.commit()
        assert person.credentials == [] and author.credentials == []


# --- validation / update semantics (both kinds) ----------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_credentials_normalized_and_persisted(client, token, kind):
    blank_optional = {"name": "MBA", "category": "  ", "issuer": "", "url": "   ", "note": ""}
    resp = _create(client, token, kind, credentials=[CREDENTIAL, blank_optional])
    assert resp.status_code == 201, resp.get_json()
    expected = [CREDENTIAL_STORED, {"name": "MBA"}]
    assert resp.get_json()["data"]["credentials"] == expected
    assert _detail(client, kind, resp.get_json()["data"]["slug"])["credentials"] == expected


@pytest.mark.parametrize("kind", KINDS)
def test_profile_without_credentials_still_publishes(client, token, kind):
    resp = _create(client, token, kind)
    assert resp.status_code == 201 and resp.get_json()["data"]["credentials"] == []


BAD_CREDENTIALS = [
    {"category": "Degree"},
    {"name": ""},
    {"name": "   "},
    {"name": "N" * 251},
    {"name": "X", "category": "C" * 101},
    {"name": "X", "issuer": "I" * 251},
    {"name": "X", "note": "N" * 501},
    {"name": "X", "url": "https://example.org/" + "a" * 2048},
    {"name": "X", "url": "javascript:alert(1)"},
    {"name": "X", "url": "data:text/html,<script>alert(1)</script>"},
    {"name": "X", "url": "ftp://example.org/cert"},
    {"name": "X", "url": "not a url"},
    {"name": "X", "url": "https://localhost/cert"},
    {"name": "X", "url": "https://foo.localhost/cert"},
    {"name": "X", "url": "https://intranet/cert"},
    {"name": "X", "url": "https://127.0.0.1/cert"},
    {"name": "X", "url": "https://192.168.1.20/cert"},
    {"name": "X", "url": "https://[::1]/cert"},
]


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("bad", BAD_CREDENTIALS)
def test_invalid_credentials_rejected(client, token, kind, bad):
    resp = _create(client, token, kind, credentials=[bad])
    assert resp.status_code in (400, 422), bad
    assert "credentials" in json.dumps(resp.get_json()["error"])


@pytest.mark.parametrize("kind", KINDS)
def test_non_public_credential_host_message(client, token, kind):
    resp = _create(client, token, kind, credentials=[{"name": "X", "url": "https://localhost/x"}])
    assert resp.get_json()["error"]["details"]["credentials"] == {"0": {"url": ["Source URL must use a public domain name."]}}


@pytest.mark.parametrize("kind", KINDS)
def test_public_credential_urls_and_boundaries_accepted(client, token, kind):
    credentials = [
        {"name": "A", "url": "https://example.com/cert"},
        {"name": "B", "url": "https://sub.domain.co.ke/cert"},
        {"name": "N" * 250, "category": "C" * 100, "issuer": "I" * 250, "note": "T" * 500, "url": "https://example.org/" + "a" * 2000,
         "verified": True, "html": "<b>x</b>"},
    ]
    resp = _create(client, token, kind, credentials=credentials)
    assert resp.status_code == 201, resp.get_json()
    assert set(resp.get_json()["data"]["credentials"][2]) == {"name", "category", "issuer", "url", "note"}


@pytest.mark.parametrize("kind", KINDS)
def test_duplicate_name_and_issuer_rejected_but_other_issuer_allowed(client, token, kind):
    resp = _create(client, token, kind, credentials=[{"name": "Certified X", "issuer": "Org A"},
                                                     {"name": " certified x ", "issuer": " ORG A "}])
    assert resp.status_code in (400, 422) and "listed more than once" in json.dumps(resp.get_json())
    resp = _create(client, token, kind, credentials=[{"name": "MBA"}, {"name": "mba"}])
    assert resp.status_code in (400, 422)
    resp = _create(client, token, kind, credentials=[{"name": "Certified X", "issuer": "Org A"},
                                                     {"name": "Certified X", "issuer": "Org B"}, {"name": "Certified X"}])
    assert resp.status_code == 201, resp.get_json()


@pytest.mark.parametrize("kind", KINDS)
def test_credential_cap(client, token, kind):
    many = [{"name": f"Credential {i}"} for i in range(31)]
    resp = _create(client, token, kind, credentials=many)
    assert resp.status_code in (400, 422) and "at most 30 credentials" in json.dumps(resp.get_json())
    assert _create(client, token, kind, credentials=many[:30]).status_code == 201


@pytest.mark.parametrize("kind", KINDS)
def test_omitted_credentials_preserved_explicit_empty_clears(client, token, kind):
    slug = _create(client, token, kind, credentials=[CREDENTIAL], sources=[SOURCE],
                   expertise=["Leadership"]).get_json()["data"]["slug"]
    edit = dict(KINDS[kind], name="Renamed", slug=slug)
    resp = client.put(f"/api/v1/{kind}/{slug}", json=edit, headers=auth_headers(token))
    body = resp.get_json()["data"]
    assert resp.status_code == 200 and body["credentials"] == [CREDENTIAL_STORED] and body["sources"] == [SOURCE]
    resp = client.put(f"/api/v1/{kind}/{slug}", json=dict(edit, credentials=[{"name": "MBA"}]), headers=auth_headers(token))
    assert resp.get_json()["data"]["credentials"] == [{"name": "MBA"}]
    resp = client.put(f"/api/v1/{kind}/{slug}", json=dict(edit, credentials=[]), headers=auth_headers(token))
    body = resp.get_json()["data"]
    assert body["credentials"] == [] and body["sources"] == [SOURCE]
    if kind == "authors":  # the Phase 4A expertise-preservation fix still holds
        assert body["expertise"] == ["Leadership"]


# --- payloads: detail only ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
def test_detail_includes_credentials_lists_never(client, token, kind):
    slug = _create(client, token, kind, credentials=[CREDENTIAL], sources=[SOURCE]).get_json()["data"]["slug"]
    assert _detail(client, kind, slug)["credentials"] == [CREDENTIAL_STORED]
    assert _detail(client, kind, slug, token)["credentials"] == [CREDENTIAL_STORED]
    assert _detail(client, kind, slug)["sources"] == [SOURCE]
    for tok in (None, token):
        items = client.get(f"/api/v1/{kind}", headers=auth_headers(tok) if tok else {}).get_json()["data"]
        assert items and all("credentials" not in i and "sources" not in i for i in items)
        assert "Digital Marketing Institute" not in json.dumps(items)


@pytest.mark.parametrize("kind", KINDS)
def test_unpublished_profile_credentials_stay_private(client, token, kind):
    slug = _create(client, token, kind, status="draft", credentials=[CREDENTIAL]).get_json()["data"]["slug"]
    assert client.get(f"/api/v1/{kind}/{slug}").status_code == 404
    assert "Digital Marketing Institute" not in client.get(f"/{kind}/{slug}").get_data(as_text=True)


def test_credentials_stay_out_of_cards_hubs_search_bylines_and_homepage(client, app, token):
    from app.models.cms import HomepageModule

    person = _create(client, token, "people", name="Evidence Person", credentials=[CREDENTIAL]).get_json()["data"]["slug"]
    author = _create(client, token, "authors", name="Evidence Author",
                     credentials=[{"name": "Author Cred", "issuer": "AuthorIssuerX"}]).get_json()["data"]["slug"]
    article = client.post("/api/v1/articles", json={
        "title": "Byline Story", "authorSlug": author, "coAuthorSlugs": [], "status": "published",
        "relatedPersonSlugs": [person], "content": [{"type": "paragraph", "text": "Body."}]}, headers=auth_headers(token)).get_json()["data"]
    _add(app, HomepageModule(type="featured_woman", enabled=True, sort_order=1, heading="Woman", config={"personSlug": person}))
    payloads = [
        article,
        client.get("/api/v1/articles").get_json(),
        client.get(f"/api/v1/articles/{article['slug']}").get_json(),
        client.get(f"/api/v1/authors/{author}").get_json()["data"]["articles"],
        client.get("/api/v1/search?q=Evidence").get_json(),
        client.get("/api/v1/homepage").get_json() if client.get("/api/v1/homepage").status_code == 200 else {},
    ]
    for payload in payloads:
        text = json.dumps(payload)
        assert "Digital Marketing Institute" not in text and "AuthorIssuerX" not in text
    for page in ("/", "/people", "/authors", "/search?q=Evidence", f"/{article['slug']}"):
        html = client.get(page).get_data(as_text=True)
        assert "Digital Marketing Institute" not in html and "AuthorIssuerX" not in html, page


@pytest.mark.parametrize("kind", KINDS)
def test_credential_edit_uses_existing_indexnow_update(client, app, token, kind, monkeypatch):
    calls = []
    app.config.update(INDEXNOW_ENABLED=True, INDEXNOW_KEY="test-indexnow-key-1234", PUBLIC_SITE_URL=SITE)
    monkeypatch.setattr(indexnow, "_post_json", lambda url, payload, timeout: calls.append(payload["urlList"]) or 200)
    slug = _create(client, token, kind).get_json()["data"]["slug"]
    calls.clear()
    client.put(f"/api/v1/{kind}/{slug}", json=dict(KINDS[kind], slug=slug, credentials=[CREDENTIAL]), headers=auth_headers(token))
    assert calls == [[f"{SITE}/{kind}/{slug}"]]


# --- raw HTML ------------------------------------------------------------------------------------------


HOSTILE = {"name": '<script>alert(1)</script>"Quoted" & <b>bold</b>', "category": "Cat > Dog",
           "issuer": "Issuer & Co", "url": "https://example.org/cred?a=1&b=2", "note": "<img src=x onerror=alert(1)>"}


@pytest.mark.parametrize("kind", KINDS)
def test_credentials_in_initial_server_html(client, token, kind):
    extra = {"careerTimeline": [{"year": "2019", "title": "Founded"}], "achievements": ["Built it"]} if kind == "people" else {
        "bio": [{"type": "paragraph", "text": "AUTHOR-BIO-TEXT"}]}
    slug = _create(client, token, kind, credentials=[CREDENTIAL, HOSTILE], sources=[SOURCE], **extra).get_json()["data"]["slug"]
    root = _root(client.get(f"/{kind}/{slug}").get_data(as_text=True))
    section_id = "person-credentials" if kind == "people" else "author-credentials"
    assert f'<section aria-labelledby="{section_id}">' in root
    assert root.count("Credentials &amp; qualifications</h2>") == 1
    assert ">Certified Digital Marketing Professional</p>" in root
    assert "Professional certification · Digital Marketing Institute" in root
    assert '<a href="https://example.org/dmi" target="_blank" rel="noopener noreferrer"' in root
    assert "Completed professional certification." in root
    assert root.index("Certified Digital Marketing") < root.index("&lt;script&gt;")  # stored order
    # Escaped plain text only.
    assert "&lt;script&gt;alert(1)&lt;/script&gt;&quot;Quoted&quot; &amp; &lt;b&gt;bold&lt;/b&gt;" in root
    assert "Cat &gt; Dog · Issuer &amp; Co" in root and "&lt;img src=x onerror=alert(1)&gt;" in root
    assert 'href="https://example.org/cred?a=1&amp;b=2"' in root
    assert "<script>alert" not in root and "<img src=x" not in root and "<b>bold" not in root
    for rel in ("nofollow", "sponsored", "ugc"):
        assert rel not in root
    for claim in ("Verified", "verified", "Fact checked", "Certified by WSF"):
        assert claim not in root
    # Placement: Person — after Career Timeline, before Achievements; Author —
    # after the bio, before Sources & references.
    cred = root.index("Credentials &amp; qualifications")
    if kind == "people":
        assert root.index("Career Timeline") < cred < root.index("Achievements") < root.index("Sources &amp; references")
    else:
        assert root.index("AUTHOR-BIO-TEXT") < cred < root.index("Sources &amp; references")


@pytest.mark.parametrize("kind", KINDS)
def test_no_credentials_means_no_section(client, token, kind):
    slug = _create(client, token, kind).get_json()["data"]["slug"]
    html = client.get(f"/{kind}/{slug}").get_data(as_text=True)
    assert "Credentials &amp; qualifications" not in html and "hasCredential" not in html


def test_person_bootstrap_carries_credentials_once(client, token):
    slug = _create(client, token, "people", credentials=[CREDENTIAL]).get_json()["data"]["slug"]
    html = client.get(f"/people/{slug}").get_data(as_text=True)
    scripts = re.findall(r'<script\b[^>]*data-wsf-bootstrap="person"[^>]*>(.*?)</script>', html, re.DOTALL)
    assert len(scripts) == 1 and json.loads(scripts[0])["data"]["credentials"] == [CREDENTIAL_STORED]


# --- structured data -----------------------------------------------------------------------------------


def test_person_stays_person_with_all_signals_coexisting(client, app, token):
    from app.models.people import Organization

    org_id = _add(app, Organization(slug="example-bank", name="Example Bank", status="published", description=[]))[0]
    slug = _create(client, token, "people", title="CEO", organizationId=org_id, website="https://jane.example.com",
                   social={"linkedin": "jane"}, expertise=["Finance"], awards=["Banker of the Year"],
                   sources=[SOURCE], credentials=[CREDENTIAL]).get_json()["data"]["slug"]
    data = _json_ld(client.get(f"/people/{slug}").get_data(as_text=True), "data-person-structured-data")
    assert data["@type"] == "Person" and "mainEntity" not in data
    assert data["hasCredential"] == [CREDENTIAL_LD]
    assert data["sameAs"] == ["https://jane.example.com", "https://linkedin.com/in/jane"]
    assert data["subjectOf"][0]["url"] == SOURCE["url"]
    assert data["knowsAbout"] == ["Finance"] and data["award"] == ["Banker of the Year"]
    assert data["worksFor"]["url"] == f"{SITE}/organizations/example-bank"
    assert CREDENTIAL_STORED["url"] not in data["sameAs"] and SOURCE["url"] not in data["sameAs"]
    assert all(w["url"] != CREDENTIAL_STORED["url"] for w in data["subjectOf"])
    assert "Completed professional certification" not in json.dumps(data)
    for inferred in ("alumniOf", "affiliation", "memberOf"):
        assert inferred not in data


def test_author_profile_page_json_ld(client, app, token):
    """Same fixture as frontend profileStructuredData.test.js's AUTHOR."""
    from app.models.people import Author
    from app.models.taxonomy import Topic

    _add(app, Topic(slug="leadership", name="Leadership", status="published"),
         Topic(slug="secret-topic", name="Secret Draft Topic", status="draft"))
    slug = _create(client, token, "authors", name="Writer", slug="writer", role="Contributor",
                   shortBio="  Writes about work and money.  ", website="https://writer.example.com",
                   social={"linkedin": "writer", "instagram": "writer_ig"}, topicSlugs=["leadership", "secret-topic"],
                   expertise=["leadership", "Climate finance"], sources=[SOURCE], credentials=[CREDENTIAL]).get_json()["data"]["slug"]
    html = client.get(f"/authors/{slug}").get_data(as_text=True)
    data = _json_ld(html, "data-author-structured-data")
    detail = _detail(client, "authors", slug)
    with app.app_context():
        author = Author.query.filter_by(slug=slug).one()
        created, updated = author.created_at.isoformat(), author.updated_at.isoformat()
    canonical = f"{SITE}/authors/writer"
    assert data == {
        "@context": "https://schema.org",
        "@type": "ProfilePage",
        "dateCreated": created,
        "dateModified": updated,
        "mainEntity": {
            "@id": f"{canonical}#author",
            "@type": "Person",
            "name": "Writer",
            "url": canonical,
            "description": "Writes about work and money.",
            "jobTitle": "Contributor",
            "sameAs": ["https://writer.example.com", "https://linkedin.com/in/writer", "https://instagram.com/writer_ig"],
            "knowsAbout": [{"@type": "Thing", "name": "Leadership", "url": f"{SITE}/topics/leadership"}, "Climate finance"],
            "hasCredential": [CREDENTIAL_LD],
            "subjectOf": [{"@type": "CreativeWork", "name": SOURCE["title"], "url": SOURCE["url"],
                           "author": {"@type": "Thing", "name": "Business Desk"},
                           "publisher": {"@type": "Organization", "name": "Example News"}, "datePublished": "2025-06-30"}],
        },
    }
    # The client builder reads the same timestamps verbatim from the detail API.
    assert (detail["created_at"], detail["updated_at"]) == (created, updated)
    text = json.dumps(data)
    for private in ("user_id", "email", "permission", "credentials-admin", "Secret Draft Topic"):
        assert private not in text
    for inferred in ("worksFor", "award", "alumniOf", "affiliation", "memberOf", "identifier", "hasPart"):
        assert inferred not in data["mainEntity"] and inferred not in data


def test_author_profile_page_follows_effective_canonical(client, token):
    override = "https://womenshapingfutures.org/authors/canonical-writer"
    slug = _create(client, token, "authors", name="Moved Writer", seo={"canonical": override}).get_json()["data"]["slug"]
    html = client.get(f"/authors/{slug}").get_data(as_text=True)
    assert re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']' + re.escape(override) + '["\']', html)
    data = _json_ld(html, "data-author-structured-data")
    assert data["mainEntity"]["url"] == override and data["mainEntity"]["@id"] == f"{override}#author"
    crumbs = _json_ld(html, "data-breadcrumb-structured-data")["itemListElement"]
    assert crumbs[-1]["item"] == override
    og = re.search(r'<meta\s+property=["\']og:url["\']\s+content=["\']([^"\']+)', html)
    assert og is None or og.group(1) == override


def test_article_author_markup_points_to_wsf_author_pages(client, app, token):
    primary = _create(client, token, "authors", name="Primary Writer", credentials=[CREDENTIAL],
                      website="https://primary.example.com").get_json()["data"]["slug"]
    co = _create(client, token, "authors", name="Co Writer").get_json()["data"]["slug"]
    article = client.post("/api/v1/articles", json={
        "title": "Credentialed Story", "authorSlug": primary, "coAuthorSlugs": [co], "status": "published",
        "content": [{"type": "paragraph", "text": "Body."}]}, headers=auth_headers(token)).get_json()["data"]
    html = client.get(f"/{article['slug']}").get_data(as_text=True)
    data = _json_ld(html, "data-article-structured-data")
    assert data["author"] == [
        {"@type": "Person", "name": "Primary Writer", "url": f"{SITE}/authors/{primary}"},
        {"@type": "Person", "name": "Co Writer", "url": f"{SITE}/authors/{co}"},
    ]
    assert "hasCredential" not in html and "Digital Marketing Institute" not in html
    # Visible bylines keep linking to the WSF Author pages.
    root = _root(html)
    assert f'href="/authors/{primary}"' in root and f'href="/authors/{co}"' in root
