"""Numbered-list continuation, CTA / Simple CTA blocks and Related reading:
sanitizing, the shared numbering rule and the server prerender."""
import json
import os

import pytest

from app.services.content_blocks import resolve_list_starts, safe_link_url, sanitize_content_blocks
from app.services.prerender import render_content_blocks

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "list_numbering_cases.json")
CASES = json.load(open(FIXTURE, encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_numbering_cases(case):
    assert resolve_list_starts(case["blocks"]) == case["expected"]


def test_lengthening_an_earlier_list_shifts_a_continuing_list():
    first = {"type": "list", "style": "number", "items": ["a", "b"]}
    later = {"type": "list", "style": "number", "numberingMode": "continue", "items": ["c"]}
    assert resolve_list_starts([first, later]) == [1, 3]
    first["items"].append("b2")
    assert resolve_list_starts([first, later]) == [1, 4]
    # Moving the continuing list above resets it to 1 (nothing before it).
    assert resolve_list_starts([later, first]) == [1, 1]


def test_continue_is_never_stored_as_a_number():
    [block] = sanitize_content_blocks([{"type": "list", "style": "number", "numberingMode": "continue", "startNumber": 9, "items": ["a"]}])
    assert block["numberingMode"] == "continue" and "startNumber" not in block


@pytest.mark.parametrize(
    "given, expected",
    [(25, 25), ("12", 12), (0, 1), (-3, 1), ("abc", 1), (None, 1), (True, 1), (10**7, 1)],
)
def test_custom_start_number_is_normalized(given, expected):
    [block] = sanitize_content_blocks([{"type": "list", "style": "number", "numberingMode": "custom", "startNumber": given, "items": ["a"]}])
    assert block["startNumber"] == expected


def test_bullet_lists_and_unknown_modes_drop_numbering_fields():
    bullet, unknown = sanitize_content_blocks([
        {"type": "list", "style": "bullet", "numberingMode": "custom", "startNumber": 4, "items": ["a"]},
        {"type": "list", "style": "number", "numberingMode": "sideways", "startNumber": 4, "items": ["a"]},
    ])
    assert "numberingMode" not in bullet and "startNumber" not in bullet
    assert "numberingMode" not in unknown and "startNumber" not in unknown


def test_legacy_list_is_unchanged_by_the_sanitizer():
    legacy = {"type": "list", "style": "number", "items": ["a", "b"]}
    assert sanitize_content_blocks([legacy]) == [legacy]


def test_prerender_writes_ol_start_for_continued_lists_and_filters_blank_items():
    html = render_content_blocks([
        {"type": "list", "style": "number", "items": [str(i) for i in range(1, 11)]},
        {"type": "paragraph", "text": "Between"},
        {"type": "list", "style": "number", "numberingMode": "continue", "items": ["a", " ", "b"]},
        {"type": "list", "style": "bullet", "items": ["x"]},
    ])
    assert html.count("<ol") == 2
    assert '<ol class=' in html  # the first list starts at 1: no start attribute
    assert '<ol start="11" class=' in html
    assert "<li> </li>" not in html and "<ul class=" in html


@pytest.mark.parametrize(
    "url, ok",
    [
        ("/career-hub", True),
        ("/topics/leadership?x=1#y", True),
        ("https://example.org/a", True),
        ("http://example.org", True),
        ("javascript:alert(1)", False),
        ("JaVaScRiPt:alert(1)", False),
        ("data:text/html,<script>", False),
        ("//evil.example", False),
        ("/admin/articles", False),
        ("/api/v1/x", False),
        ("/path with space", False),
        ("/ok\n", True),  # surrounding whitespace is stripped
        ("/a\x00b", False),
        ("mailto:hello@example.org", False),
        ("", False),
        (None, False),
    ],
)
def test_safe_link_url(url, ok):
    assert (safe_link_url(url) != "") is ok


def test_cta_block_is_reduced_to_known_plain_fields():
    [block] = sanitize_content_blocks([{
        "type": "cta",
        "eyebrow": "<b>Career Hub</b>",
        "title": "Build your <script>alert(1)</script>next move",
        "text": "Q&A <img src=x onerror=alert(1)>",
        "buttonLabel": "Explore",
        "buttonUrl": "javascript:alert(1)",
        "style": "neon",
        "align": "right",
        "className": "evil",
        "onclick": "alert(1)",
    }])
    assert block == {
        "type": "cta",
        "eyebrow": "Career Hub",
        "title": "Build your alert(1)next move",
        "text": "Q&A",
        "buttonLabel": "Explore",
        "buttonUrl": "",
        "style": "soft",
        "align": "left",
    }


def test_simple_button_keeps_mailto_and_drops_unsafe_urls():
    ok, bad, internal = sanitize_content_blocks([
        {"type": "button", "label": "Email us", "url": "mailto:hello@example.org", "external": "yes"},
        {"type": "button", "label": "<i>Bad</i>", "url": "data:text/html,x"},
        {"type": "button", "label": "Hub", "url": "/career-hub"},
    ])
    assert ok["url"] == "mailto:hello@example.org" and ok["external"] is False
    assert bad == {"type": "button", "label": "Bad", "url": ""}
    assert internal["url"] == "/career-hub"


def test_related_block_slugs_are_validated_and_capped():
    [block] = sanitize_content_blocks([{
        "type": "relatedBlock",
        "heading": "<b>Keep reading</b>",
        "articleSlugs": ["one", "one", "Bad Slug", "two", "three", "four", 5],
    }])
    assert block["articleSlugs"] == ["one", "two", "three"] and block["heading"] == "Keep reading"


def test_prerender_renders_visible_crawlable_ctas():
    html = render_content_blocks([
        {"type": "cta", "eyebrow": "Career Hub", "title": "Plan your next move", "text": "Tools & guides.",
         "buttonLabel": "Explore the Career Hub", "buttonUrl": "/career-hub", "style": "strong", "align": "center"},
        {"type": "cta", "title": "External", "buttonLabel": "Visit", "buttonUrl": "https://example.org/x"},
        {"type": "cta", "title": "Unsafe", "buttonLabel": "Click", "buttonUrl": "javascript:alert(1)"},
        {"type": "button", "label": "Read the guide", "url": "/resources"},
    ])
    assert "Plan your next move" in html and "Tools &amp; guides." in html
    assert '<a href="/career-hub" class="btn-light">Explore the Career Hub</a>' in html
    assert '<a href="https://example.org/x" rel="noopener noreferrer" class="btn-primary">Visit</a>' in html
    assert "javascript:" not in html and "Click</a>" not in html and "Unsafe" in html
    assert '<a href="/resources" class="btn-primary">Read the guide</a>' in html
    assert "target=" not in html
    assert "text-center" in html
    for hidden in ("hidden", "aria-hidden", "display:none"):
        assert hidden not in html
