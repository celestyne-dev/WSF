"""WSF People Phase 1 — editorial & CMS completeness.

Covers the code-level gaps this phase closes:
- Callout (highlight) blocks carrying an optional bullet/numbered list,
  sanitized item-by-item (shared by Article.content and Person.bio).
- Person seo.ogImageMediaId resolved in the API (same shape as
  ArticleSchema.get_seo) and preferred over the portrait by the
  server-rendered Person metadata.
- GET /api/v1/people?expertise=… filtered server-side, before pagination.
- PersonInputSchema.website validated as a real URL.
- Instagram included in Person JSON-LD sameAs.
"""
import json
import os
import re

import pytest

from app.extensions import db
from app.services.content_blocks import sanitize_content_blocks
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")

EDITOR_PAYLOAD = {
    "email": "people-phase1-editor@example.com",
    "password": "supersecret1",
    "first_name": "Pat",
    "last_name": "Osei",
    "country_code": "US",
}


@pytest.fixture()
def editor_token(client, app):
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=EDITOR_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=EDITOR_PAYLOAD["email"]).first()
        user.roles.append(Role.query.filter_by(name="editor").first())
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": EDITOR_PAYLOAD["email"], "password": EDITOR_PAYLOAD["password"]})
    return login.get_json()["data"]["access_token"]


def _make_media(app, name, alt_text=None):
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename=f"{name}.jpg",
            stored_filename=f"{name}.jpg",
            file_path=f"/srv/private/{name}.jpg",
            public_url=f"/media/originals/{name}.jpg",
            mime_type="image/jpeg",
            alt_text=alt_text,
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _payload(**overrides):
    payload = {
        "name": "Amina Diallo",
        "title": "Founder & CEO",
        "shortBio": "Founder of a fintech startup serving West Africa.",
        "bio": [{"type": "paragraph", "text": "Amina founded her company in 2021."}],
        "status": "published",
    }
    payload.update(overrides)
    return payload


def _use_fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _meta_content(html, attr, key):
    match = re.search(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(rf'<meta\s+content=["\']([^"\']*)["\']\s+{attr}=["\']{re.escape(key)}["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _person_json_ld(html):
    match = re.search(r"<script\b[^>]*data-person-structured-data[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    assert match is not None
    return json.loads(match.group(1))


def _make_person(app, slug, **fields):
    from app.models.people import Person

    with app.app_context():
        person = Person(slug=slug, name=fields.pop("name", "Amara Okafor"), status=fields.pop("status", "published"), **fields)
        db.session.add(person)
        db.session.commit()
        return person.id


# --- A. Callout list sanitization -------------------------------------


class TestCalloutSanitization:
    def test_text_only_callout_unchanged(self):
        block = {"type": "highlight", "title": "Note", "text": "Plain <b>bold</b> text"}
        assert sanitize_content_blocks([block]) == [block]

    def test_bullet_list_persists_and_sanitizes(self):
        [block] = sanitize_content_blocks([{
            "type": "highlight",
            "title": "Key lessons",
            "text": "What her journey teaches us:",
            "listStyle": "bullet",
            "items": ["Start <em>before</em> you feel ready.", 'Build <a href="https://example.com">relationships</a>.'],
        }])
        assert block["listStyle"] == "bullet"
        assert block["items"] == ["Start <em>before</em> you feel ready.", 'Build <a href="https://example.com">relationships</a>.']

    def test_numbered_list_persists(self):
        [block] = sanitize_content_blocks([{"type": "highlight", "text": "Steps", "listStyle": "number", "items": ["One", "Two"]}])
        assert block["listStyle"] == "number"
        assert block["items"] == ["One", "Two"]

    def test_unsafe_html_removed_from_items_and_title(self):
        [block] = sanitize_content_blocks([{
            "type": "highlight",
            "title": "<b>Q&A</b><script>x</script>",
            "text": "Intro",
            "listStyle": "bullet",
            "items": [
                '<script>alert(1)</script>Safe',
                '<a href="javascript:alert(1)" onclick="x()">Click</a>',
                '<img src=x onerror=alert(1)>Image',
                '<div><h1>Big</h1></div>',
            ],
        }])
        assert block["title"] == "Q&Ax"
        joined = " ".join(block["items"])
        for forbidden in ("<script", "javascript:", "onclick", "onerror", "<img", "<div", "<h1"):
            assert forbidden not in joined
        assert block["items"][0].endswith("Safe")

    @pytest.mark.parametrize("style", ["none", "", None, "checklist", 3, ["bullet"]])
    def test_invalid_or_empty_list_style_normalizes_to_none_and_keeps_items(self, style):
        [block] = sanitize_content_blocks([{"type": "highlight", "text": "x", "listStyle": style, "items": ["kept"]}])
        assert block["listStyle"] is None
        assert block["items"] == ["kept"]

    @pytest.mark.parametrize("items", ["not a list", {"a": 1}, 42, None])
    def test_malformed_items_do_not_crash(self, items):
        [block] = sanitize_content_blocks([{"type": "highlight", "text": "x", "listStyle": "bullet", "items": items}])
        assert block["items"] == []

    def test_non_string_items_dropped(self):
        [block] = sanitize_content_blocks([{"type": "highlight", "text": "x", "listStyle": "number", "items": ["a", 1, None, {"x": 1}, "b"]}])
        assert block["items"] == ["a", "b"]


def test_callout_list_round_trips_through_person_api(client, editor_token):
    bio = [{
        "type": "highlight",
        "title": "Key lessons",
        "text": "What her journey teaches us:",
        "listStyle": "number",
        "items": ["Start before you feel ready.", "<script>x</script>Build relationships."],
    }]
    resp = client.post("/api/v1/people", json=_payload(bio=bio), headers=auth_headers(editor_token))
    assert resp.status_code == 201
    [block] = resp.get_json()["data"]["bio"]
    assert block["listStyle"] == "number"
    assert block["items"][0] == "Start before you feel ready."
    assert "<script" not in block["items"][1]


# --- B. Person SEO image -------------------------------------------------


def test_person_seo_og_image_persists_and_resolves(client, app, editor_token):
    og_id = _make_media(app, "og-share", alt_text="Amina speaking on stage")
    seo = {"title": "Amina", "description": "Desc", "canonical": None, "ogImageMediaId": og_id}
    resp = client.post("/api/v1/people", json=_payload(seo=seo), headers=auth_headers(editor_token))
    assert resp.status_code == 201

    public = client.get("/api/v1/people/amina-diallo").get_json()["data"]
    assert public["seo"]["ogImageMediaId"] == og_id
    assert public["seo"]["ogImage"] == "/media/originals/og-share.jpg"
    assert public["seo"]["ogImageAlt"] == "Amina speaking on stage"
    assert public["seo"]["title"] == "Amina"
    # No new serialization path leaks Media's internal storage fields.
    assert set(public["seo"]) <= {"title", "description", "canonical", "robots", "ogImageMediaId", "ogImage", "ogImageAlt"}
    assert "/srv/private" not in json.dumps(public["seo"])

    # The stored JSON keeps only the id — resolved fields are dump-only.
    from app.models.people import Person

    with app.app_context():
        stored = Person.query.filter_by(slug="amina-diallo").first().seo
        assert stored["ogImageMediaId"] == og_id
        assert "ogImage" not in stored


def test_person_seo_without_alt_has_no_fabricated_alt(client, app, editor_token):
    og_id = _make_media(app, "no-alt-share")
    client.post("/api/v1/people", json=_payload(seo={"ogImageMediaId": og_id}), headers=auth_headers(editor_token))
    seo = client.get("/api/v1/people/amina-diallo").get_json()["data"]["seo"]
    assert seo["ogImage"] == "/media/originals/no-alt-share.jpg"
    assert "ogImageAlt" not in seo


def test_person_seo_missing_media_and_null_seo(client, app, editor_token):
    client.post("/api/v1/people", json=_payload(seo={"ogImageMediaId": 999999}), headers=auth_headers(editor_token))
    seo = client.get("/api/v1/people/amina-diallo").get_json()["data"]["seo"]
    assert seo == {"ogImageMediaId": 999999}

    client.post("/api/v1/people", json=_payload(name="No Seo"), headers=auth_headers(editor_token))
    assert client.get("/api/v1/people/no-seo").get_json()["data"]["seo"] is None


def test_server_person_meta_prefers_explicit_og_image(client, app):
    _use_fixture_index(app)
    photo_id = _make_media(app, "portrait", alt_text="Portrait of Amara")
    og_id = _make_media(app, "share-card", alt_text="Amara at the summit")
    _make_person(app, "amara-okafor", photo_media_id=photo_id, seo={"ogImageMediaId": og_id})

    html = client.get("/people/amara-okafor").get_data(as_text=True)
    assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/share-card.jpg"
    assert _meta_content(html, "property", "og:image:alt") == "Amara at the summit"


def test_server_person_meta_falls_back_to_portrait(client, app):
    _use_fixture_index(app)
    photo_id = _make_media(app, "portrait-only", alt_text="Portrait of Amara")
    _make_person(app, "amara-okafor", photo_media_id=photo_id, seo={"title": "Custom"})

    html = client.get("/people/amara-okafor").get_data(as_text=True)
    assert _meta_content(html, "property", "og:image") == "https://womenshapingfutures.org/media/originals/portrait-only.jpg"
    assert _meta_content(html, "property", "og:image:alt") == "Portrait of Amara"


# --- C. Expertise filter ---------------------------------------------------


def test_expertise_filter_is_server_side_and_composes(client, app, editor_token):
    headers = auth_headers(editor_token)
    client.post("/api/v1/people", json=_payload(name="Fin Leader", expertise=["Fintech", "Leadership"], industry="Finance", countryCode="KE"), headers=headers)
    client.post("/api/v1/people", json=_payload(name="Fin Other", expertise=["Fintech"], industry="Health", countryCode="NG"), headers=headers)
    client.post("/api/v1/people", json=_payload(name="Policy Person", expertise=["Policy"], industry="Finance"), headers=headers)
    # Substring of an expertise value must not match (exact item matching).
    client.post("/api/v1/people", json=_payload(name="Fin Partial", expertise=["Fintech Policy"]), headers=headers)
    client.post("/api/v1/people", json=_payload(name="Fin Draft", expertise=["Fintech"], status="draft"), headers=headers)

    def names(**params):
        resp = client.get("/api/v1/people", query_string=params)
        assert resp.status_code == 200
        return sorted(p["name"] for p in resp.get_json()["data"])

    assert names(expertise="Fintech") == ["Fin Leader", "Fin Other"]
    assert names(expertise="Policy") == ["Policy Person"]
    assert names(expertise="Nonexistent") == []
    assert names(expertise="Fintech", industry="Finance") == ["Fin Leader"]
    assert names(expertise="Fintech", country="NG") == ["Fin Other"]
    assert names(expertise="Fintech", query="Leader") == ["Fin Leader"]
    # Empty value behaves as "no filter".
    assert "Policy Person" in names(expertise="")


def test_expertise_filter_composes_with_series_and_pagination(client, app, editor_token):
    from app.models.taxonomy import Series

    with app.app_context():
        db.session.add(Series(slug="founder-stories", name="Founder Stories", status="published"))
        db.session.commit()
    headers = auth_headers(editor_token)
    client.post("/api/v1/people", json=_payload(name="In Series", expertise=["Fintech"], seriesSlugs=["founder-stories"]), headers=headers)
    client.post("/api/v1/people", json=_payload(name="Not In Series", expertise=["Fintech"]), headers=headers)
    for i in range(3):
        client.post("/api/v1/people", json=_payload(name=f"Aaa Filler {i}", expertise=["Other"]), headers=headers)

    resp = client.get("/api/v1/people", query_string={"expertise": "Fintech", "series": "founder-stories"})
    assert [p["name"] for p in resp.get_json()["data"]] == ["In Series"]

    # Filter applies before pagination: page 1 of size 2 holds only matches.
    resp = client.get("/api/v1/people", query_string={"expertise": "Fintech", "pageSize": 2})
    body = resp.get_json()
    assert sorted(p["name"] for p in body["data"]) == ["In Series", "Not In Series"]


# --- D. Website validation ------------------------------------------------


def test_person_website_valid_url_accepted(client, editor_token):
    resp = client.post("/api/v1/people", json=_payload(website="https://amina.example.com/about"), headers=auth_headers(editor_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["website"] == "https://amina.example.com/about"


@pytest.mark.parametrize("website", ["not a url", "javascript:alert(1)", "https://no-tld", "example"])
def test_person_website_invalid_url_rejected(client, editor_token, website):
    resp = client.post("/api/v1/people", json=_payload(website=website), headers=auth_headers(editor_token))
    assert resp.status_code in (400, 422)


def test_person_website_null_still_allowed(client, editor_token):
    resp = client.post("/api/v1/people", json=_payload(website=None), headers=auth_headers(editor_token))
    assert resp.status_code == 201


# --- E. Structured data -----------------------------------------------------


def test_person_same_as_includes_instagram(client, app):
    _use_fixture_index(app)
    _make_person(
        app, "amara-okafor", website="https://amara.example.com",
        social={"linkedin": "amara", "twitter": "amara_tw", "instagram": "amara_ig"},
    )
    data = _person_json_ld(client.get("/people/amara-okafor").get_data(as_text=True))
    assert data["sameAs"] == [
        "https://amara.example.com",
        "https://linkedin.com/in/amara",
        "https://twitter.com/amara_tw",
        "https://instagram.com/amara_ig",
    ]


def test_person_same_as_omits_absent_instagram(client, app):
    _use_fixture_index(app)
    _make_person(app, "amara-okafor", social={"linkedin": "amara", "instagram": ""})
    data = _person_json_ld(client.get("/people/amara-okafor").get_data(as_text=True))
    assert data["sameAs"] == ["https://linkedin.com/in/amara"]


def test_person_instagram_only_same_as(client, app):
    _use_fixture_index(app)
    _make_person(app, "amara-okafor", social={"instagram": "amara_ig"})
    data = _person_json_ld(client.get("/people/amara-okafor").get_data(as_text=True))
    assert data["sameAs"] == ["https://instagram.com/amara_ig"]


def test_author_same_as_unchanged(client, app):
    from app.models.people import Author

    _use_fixture_index(app)
    with app.app_context():
        db.session.add(Author(slug="wsf-editorial", name="WSF Editorial", status="active", social={"twitter": "wsf", "instagram": "wsf_ig"}))
        db.session.commit()
    html = client.get("/authors/wsf-editorial").get_data(as_text=True)
    match = re.search(r"<script\b[^>]*data-author-structured-data[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    assert match is not None
    # GEO Phase 4A: an Author's visible Instagram is now an identity URL too.
    assert json.loads(match.group(1))["sameAs"] == ["https://twitter.com/wsf", "https://instagram.com/wsf_ig"]
