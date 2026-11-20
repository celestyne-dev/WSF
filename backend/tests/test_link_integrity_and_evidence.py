"""Rich list items, link integrity and People evidence (Parts A, B, C, G).

A link an editor adds either round-trips as a real sanitized anchor or is
rejected at save time with a message naming the block; it is never reduced
to its text silently."""
import os
import re

import pytest

from app.services.content_blocks import sanitize_content_blocks, unsafe_inline_problem
from app.services.prerender import render_content_blocks
from tests.conftest import auth_headers
from tests.test_footer_cms import _register_with_role

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
EDITOR = {"email": "links-editor@example.com", "password": "supersecret1", "first_name": "L", "last_name": "E"}

RICH = 'Read <strong>bold</strong>, <em>italic</em>, <a href="https://example.org/report">the report</a> and <a href="/topics/careers">careers</a>.'
RICH_BIO = [
    {"type": "paragraph", "text": RICH},
    {"type": "list", "style": "bullet", "items": [RICH, 'Source: <a href="https://example.org/s">Annual survey</a>']},
]


@pytest.fixture()
def editor_token(client, app):
    return _register_with_role(client, app, EDITOR, "editor")


def _anchors(text):
    return re.findall(r'<a href="([^"]+)"', text)


# --- unit: what is accepted and rejected -------------------------------------------------

@pytest.mark.parametrize("text", [
    RICH,
    '<a href="mailto:hello@example.org">Email</a>',
    '<a href="#faq">Jump</a>',
    "plain text, no markup",
])
def test_safe_inline_content_is_accepted(text):
    assert unsafe_inline_problem(text) is None


@pytest.mark.parametrize("text, fragment", [
    ('<a href="javascript:alert(1)">x</a>', "javascript:alert(1)"),
    ('<a href="data:text/html;base64,AAAA">x</a>', "data:text/html"),
    ('<a href="www.example.org">x</a>', "www.example.org"),
    ('<a href="//evil.example">x</a>', "//evil.example"),
    ('<a href="/admin/users">x</a>', "/admin/users"),
    ('<strong onclick="x()">x</strong>', "event attribute"),
    ('<img src=x onerror=alert(1)>', "event attribute"),
    ("<script>alert(1)</script>", "script"),
])
def test_unsafe_inline_content_is_rejected(text, fragment):
    problem = unsafe_inline_problem(text)
    assert problem and fragment in problem


# --- Article: Paragraph and List round-trip ---------------------------------------------

def _article(client, token, content):
    author = client.post("/api/v1/authors", json={"name": "Link Author"}, headers=auth_headers(token)).get_json()["data"]["slug"]
    return client.post("/api/v1/articles", json={"title": "Links", "authorSlug": author, "content": content}, headers=auth_headers(token))


def test_article_paragraph_and_list_links_round_trip(client, editor_token):
    content = [
        {"type": "paragraph", "text": RICH},
        {"type": "list", "style": "number", "items": [RICH, "<strong>Second</strong> item"]},
        {"type": "list", "style": "bullet", "items": ['<em>Note</em> <a href="https://example.org/n">source</a>']},
    ]
    resp = _article(client, editor_token, content)
    assert resp.status_code == 201, resp.get_json()
    slug = resp.get_json()["data"]["slug"]
    saved = client.get(f"/api/v1/articles/{slug}", headers=auth_headers(editor_token)).get_json()["data"]["content"]
    assert _anchors(saved[0]["text"]) == ["https://example.org/report", "/topics/careers"]
    assert "<strong>bold</strong>" in saved[0]["text"] and "<em>italic</em>" in saved[0]["text"]
    assert _anchors(saved[1]["items"][0]) == ["https://example.org/report", "/topics/careers"]
    assert saved[1]["items"][1] == "<strong>Second</strong> item"
    assert _anchors(saved[2]["items"][0]) == ["https://example.org/n"]
    # Old plain-string items are untouched.
    resp = _article(client, editor_token, [{"type": "list", "style": "bullet", "items": ["one", "two"]}])
    assert resp.get_json()["data"]["content"][0]["items"] == ["one", "two"]


@pytest.mark.parametrize("block, where", [
    ({"type": "paragraph", "text": 'Hi <a href="javascript:alert(1)">x</a>'}, "block 1 (Paragraph)"),
    ({"type": "list", "style": "bullet", "items": ["ok", '<a href="data:text/html,x">x</a>']}, "block 1 (List)"),
    ({"type": "blockquote", "text": '<em onmouseover="x()">q</em>'}, "block 1 (Quote)"),
    ({"type": "highlight", "text": "t", "listStyle": "bullet", "items": ['<a href="www.example.org">x</a>']}, "block 1 (Callout)"),
])
def test_article_unsafe_link_is_rejected_with_block_message(client, editor_token, block, where):
    resp = _article(client, editor_token, [block])
    assert resp.status_code == 422
    assert where in str(resp.get_json())


# --- Prerender parity: rich list 1-10, paragraph, rich list 11-15 -------------------------

def test_rich_list_prerender_numbering_and_anchors():
    first = [f'<strong>Step {i}</strong> see <a href="https://example.org/{i}">ref {i}</a>' for i in range(1, 11)]
    second = [f'<em>Step {i}</em> <a href="/topics/t{i}">topic</a>' for i in range(11, 16)]
    blocks = [
        {"type": "list", "style": "number", "items": first},
        {"type": "paragraph", "text": RICH},
        {"type": "list", "style": "number", "numberingMode": "continue", "items": second + ["<strong></strong>"]},
    ]
    html = render_content_blocks(blocks)
    lists = re.findall(r"<ol([^>]*)>(.*?)</ol>", html)
    assert len(lists) == 2
    assert 'start=' not in lists[0][0] and 'start="11"' in lists[1][0]
    assert lists[0][1].count("<li>") == 10 and lists[1][1].count("<li>") == 5  # markup-only item hidden
    assert '<a href="https://example.org/10">ref 10</a>' in html and '<a href="/topics/t15">topic</a>' in html
    assert "<strong>Step 1</strong>" in html and "<em>Step 15</em>" in html


def test_markup_only_items_are_blank_but_a_link_is_not():
    [block] = sanitize_content_blocks([{"type": "list", "style": "number", "items": ['<a href="/x">Source</a>', "<strong></strong>", "c"]}])
    from app.services.content_blocks import resolve_list_starts, visible_text
    assert [bool(visible_text(i)) for i in block["items"]] == [True, False, True]
    assert resolve_list_starts([block, {"type": "list", "style": "number", "numberingMode": "continue", "items": ["d"]}]) == [1, 3]


# --- Person: bio, evidence, public page --------------------------------------------------

EVIDENCE = {
    "achievements": ["Legacy plain achievement",
                     {"text": "Led a 40-person team", "date": "2023", "sourceLabel": "Company report", "sourceUrl": "https://example.org/report"}],
    "awards": ["Legacy Award 2019",
               {"name": "Leadership Award", "issuer": "Example Foundation", "date": "2024",
                "sourceLabel": "Announcement", "sourceUrl": "https://example.org/award"}],
    "careerTimeline": [{"year": "2018", "title": "Analyst"},
                       {"year": "2021", "title": "Director", "organization": "Example Co",
                        "sourceLabel": "Press release", "sourceUrl": "https://example.org/press"}],
}


def _person(client, token, **extra):
    payload = {"name": "Evidence Person", "shortBio": "Intro.", "status": "published", "bio": RICH_BIO, **EVIDENCE}
    payload.update(extra)
    return client.post("/api/v1/people", json=payload, headers=auth_headers(token))


def test_person_bio_and_evidence_round_trip(client, editor_token):
    resp = _person(client, editor_token)
    assert resp.status_code == 201, resp.get_json()
    data = client.get("/api/v1/people/evidence-person").get_json()["data"]
    assert _anchors(data["bio"][0]["text"]) == ["https://example.org/report", "/topics/careers"]
    assert _anchors(data["bio"][1]["items"][1]) == ["https://example.org/s"]
    assert data["achievements"][0] == {"text": "Legacy plain achievement", "date": "", "sourceLabel": "", "sourceUrl": ""}
    assert data["achievements"][1]["sourceUrl"] == "https://example.org/report"
    assert data["awards"][0]["name"] == "Legacy Award 2019"
    assert data["awards"][1] == {"name": "Leadership Award", "issuer": "Example Foundation", "date": "2024",
                                 "sourceLabel": "Announcement", "sourceUrl": "https://example.org/award"}
    assert data["career_timeline"][0] == {"year": "2018", "title": "Analyst", "organization": "", "sourceLabel": "", "sourceUrl": ""}
    assert data["career_timeline"][1]["organization"] == "Example Co"


@pytest.mark.parametrize("field, bad, message", [
    ("awards", [{"name": "A", "sourceUrl": "javascript:alert(1)"}], "Awards, item 1"),
    ("achievements", ["ok", {"text": "B", "sourceUrl": "ftp://example.org/x"}], "Achievements, item 2"),
    ("careerTimeline", [{"year": "2020", "title": "C", "sourceUrl": "data:text/html,x"}], "Career Timeline, item 1"),
])
def test_person_invalid_source_url_is_a_clear_422(client, editor_token, field, bad, message):
    resp = _person(client, editor_token, **{field: bad})
    assert resp.status_code == 422
    assert message in str(resp.get_json())


def test_person_bio_unsafe_link_rejected(client, editor_token):
    resp = _person(client, editor_token, bio=[{"type": "list", "style": "bullet", "items": ['<a href="javascript:x">x</a>']}])
    assert resp.status_code == 422 and "Biography, block 1 (List)" in str(resp.get_json())


def test_person_prerender_shows_source_links_safely(client, app, editor_token):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    assert _person(client, editor_token).status_code == 201
    html = client.get("/people/evidence-person").get_data(as_text=True)
    root = html.split("data-wsf-prerender", 1)[1]
    for url in ("https://example.org/award", "https://example.org/press", "https://example.org/report"):
        tag = re.search(rf'<a href="{re.escape(url)}"[^>]*>', root)
        assert tag, url
    sources = re.findall(r'<a href="https://example.org/(?:award|press)"[^>]*>', root)
    assert all('target="_blank"' in t and 'rel="noopener noreferrer"' in t and "opens in a new tab" in t for t in sources)
    assert "Source →" in root
    assert '<a href="/topics/careers">careers</a>' in root  # bio internal link stays internal
    # JSON-LD awards use the normalized names (legacy strings and objects).
    ld = html.split("</head>")[0]
    assert "Leadership Award" in ld and "Legacy Award 2019" in ld


# --- Author bio ----------------------------------------------------------------------------

def test_author_bio_links_round_trip_and_prerender(client, app, editor_token):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    resp = client.post("/api/v1/authors", json={"name": "Bio Links", "status": "active", "bio": RICH_BIO}, headers=auth_headers(editor_token))
    assert resp.status_code == 201, resp.get_json()
    slug = resp.get_json()["data"]["slug"]
    data = client.get(f"/api/v1/authors/{slug}").get_json()["data"]["author"]
    assert _anchors(data["bio"][0]["text"]) == ["https://example.org/report", "/topics/careers"]
    assert _anchors(data["bio"][1]["items"][1]) == ["https://example.org/s"]
    html = client.get(f"/authors/{slug}").get_data(as_text=True)
    assert '<a href="https://example.org/s">Annual survey</a>' in html
    bad = client.post("/api/v1/authors", json={"name": "Bad", "bio": [{"type": "paragraph", "text": '<a href="javascript:x">x</a>'}]},
                      headers=auth_headers(editor_token))
    assert bad.status_code == 422 and "Biography, block 1 (Paragraph)" in str(bad.get_json())
