"""Author profile redesign: hero facts, section order, no counters,
education derived from credentials (shared fixture with the frontend)."""
import json
from pathlib import Path

from app.services.prerender import author_education, render_author_prerender

FIXTURE = Path(__file__).parent / "fixtures" / "author_education_cases.json"


def test_education_matches_shared_fixture():
    for case in json.loads(FIXTURE.read_text())["cases"]:
        assert author_education(case["credentials"]) == case["expected"]


def _payload(**extra):
    base = {
        "name": "Amara Diallo",
        "headline": "Career strategy for women in tech",
        "role": "Editor",
        "short_bio": "Amara writes about careers.",
        "location": "Nairobi",
        "country": {"name": "Kenya"},
        "credentials": [{"name": "MBA", "category": "Degree", "issuer": "Strathmore University"}],
        "topics": [{"slug": "careers", "name": "Careers"}],
        "bio": [{"type": "paragraph", "text": 'Read <a href="/topics/careers">careers</a> and <strong>more</strong>.'}],
        "website": "https://example.org",
    }
    base.update(extra)
    return base


AUTHORITY = {
    "counts": {"articles": 12, "resources": 2, "courses": 1},
    "learningPrograms": [{"slug": "lead", "title": "Lead"}],
    "resources": [{"slug": "kit", "title": "Kit"}],
    "latestArticles": [{"slug": "a1", "title": "A1"}],
}


def test_hero_facts_and_order():
    html = render_author_prerender(_payload(), AUTHORITY)
    for label in ("Location", "Role", "Education", "Areas of expertise"):
        assert f">{label}</dt>" in html
    assert "Nairobi, Kenya" in html and "MBA, Strathmore University" in html
    assert "Amara writes about careers." in html
    # No dominant counters in the hero.
    assert "font-serif text-3xl font-semibold leading-none" not in html
    order = [html.index(s) for s in ("<h1", 'id="author-about"', 'id="author-credentials"', 'id="author-learning"',
                                       'id="author-resources"', 'id="author-articles"')]
    assert order == sorted(order)
    assert "Browse all of Amara’s articles" in html and "12 articles" in html
    assert "rounded-media" in html and "rounded-lg border border-taupe-200" not in html
    # Bio links survive as real anchors.
    assert '<a href="/topics/careers">careers</a>' in html and "<strong>more</strong>" in html


def test_empty_facts_and_role_as_subtitle():
    html = render_author_prerender({"name": "Solo", "role": "Writer"})
    assert "<dl" not in html
    assert ">Writer</p>" in html
    assert ">Role</dt>" not in html


def test_classes_exist_in_react_source():
    src = (Path(__file__).resolve().parents[2] / "frontend/src/pages/AuthorProfilePage.jsx").read_text()
    from app.services import prerender as p
    for name in ("_AUTHOR_HERO_INNER", "_AUTHOR_HERO_GRID", "_AUTHOR_PORTRAIT", "_AUTHOR_INITIALS", "_AUTHOR_H1",
                 "_AUTHOR_SUBTITLE_LINE", "_AUTHOR_INTRO", "_AUTHOR_FACTS", "_AUTHOR_FACT_LABEL", "_AUTHOR_FACT_VALUE",
                 "_AUTHOR_TOPIC_LINK", "_AUTHOR_LINK", "_AUTHOR_BIO"):
        assert getattr(p, name) in src, name
