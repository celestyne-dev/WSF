"""Published general Pages at /<slug>: real 200 with SEO, a one-shot page
bootstrap and a visible prerender; drafts and unknown slugs are a true 404
with nothing leaked."""
import json
import os
import re

import pytest

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


@pytest.fixture(autouse=True)
def _index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _page(app, slug, status="published", **extra):
    from app.extensions import db
    from app.models.page import Page

    with app.app_context():
        page = Page(key=slug, slug=slug, page_type="general", title=extra.pop("title", "Press Kit"), status=status,
                    subtitle=extra.pop("subtitle", "Logos, photos and facts."), content=extra.pop("content", [
                        {"type": "heading", "level": 2, "text": "Brand assets"},
                        {"type": "paragraph", "text": 'Email <a href="mailto:press@example.org">our team</a> or read <a href="/about">about us</a>.'},
                        {"type": "list", "style": "number", "items": ["<strong>Logo</strong> files", "Photos"]},
                    ]), **extra)
        db.session.add(page)
        db.session.commit()
        return page.id


def _bootstrap(html):
    match = re.search(r'<script type="application/json" data-wsf-bootstrap="page">(.*?)</script>', html, re.S)
    return json.loads(match.group(1)) if match else None


def _media(app, name):
    from app.extensions import db
    from app.models.media import Media

    with app.app_context():
        media = Media(original_filename=f"{name}.jpg", stored_filename=f"{name}.jpg", file_path=f"/srv/{name}.jpg",
                      public_url=f"/media/originals/{name}.jpg", mime_type="image/jpeg", alt_text=f"{name} alt")
        db.session.add(media)
        db.session.commit()
        return media.id


def test_published_page_hard_load(client, app):
    og = _media(app, "press-og")
    _page(app, "press-kit", seo={"title": "Press Kit | WSF", "description": "Media resources.", "robots": "index, follow",
                                 "ogImageMediaId": og})
    resp = client.get("/press-kit")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    head = html.split("</head>")[0]
    assert "<title>Press Kit | WSF</title>" in head
    assert 'name="description" content="Media resources."' in head
    assert 'rel="canonical" href="' in head and "/press-kit" in head
    assert 'name="robots" content="index, follow"' in head
    assert re.search(r'property="og:image" content="[^"]*/media/originals/press-og.jpg"', head)
    assert "/srv/" not in html
    assert '"@type": "BreadcrumbList"' in head and "Press Kit" in head
    # Visible body in the initial HTML.
    root = html.split('data-wsf-prerender="page"', 1)[1]
    assert "Press Kit</h1>" in root and "Logos, photos and facts." in root
    assert "Brand assets" in root and '<a href="mailto:press@example.org">our team</a>' in root
    assert '<a href="/about">about us</a>' in root and "<strong>Logo</strong> files" in root
    # One-shot bootstrap: the same payload GET /pages/public/<slug> returns.
    boot = _bootstrap(html)
    api = client.get("/api/v1/pages/public/press-kit").get_json()["data"]
    assert boot["key"] == "press-kit" and boot["data"]["title"] == api["title"] and boot["data"]["content"] == api["content"]
    assert boot["data"]["page_type"] == "general"
    assert "status" not in boot["data"] and "internal_name" not in boot["data"]


def test_seo_falls_back_to_title_and_subtitle(client, app):
    _page(app, "media-room", title="Media Room", subtitle="For journalists.")
    head = client.get("/media-room").get_data(as_text=True).split("</head>")[0]
    assert "<title>Media Room</title>" in head and 'content="For journalists."' in head


def test_draft_page_is_a_true_404_without_leaks(client, app):
    _page(app, "secret-plans", status="draft", title="Secret Plans", subtitle="Not yet", content=[{"type": "paragraph", "text": "PRIVATE-BODY"}])
    resp = client.get("/secret-plans")
    assert resp.status_code == 404
    html = resp.get_data(as_text=True)
    assert "Secret Plans" not in html and "PRIVATE-BODY" not in html and _bootstrap(html) is None
    assert client.get("/api/v1/pages/public/secret-plans").status_code == 404


def test_unknown_flat_slug_is_404(client):
    assert client.get("/no-owner-here").status_code == 404


def test_classes_exist_in_react_source():
    from pathlib import Path

    from app.services import prerender as p

    root = Path(__file__).resolve().parents[2] / "frontend/src/components/pages"
    src = (root / "InstitutionalPageHero.jsx").read_text() + (root / "InstitutionalPageShell.jsx").read_text()
    for name in ("_PAGE_HERO_BAND", "_PAGE_HERO_INNER", "_PAGE_H1", "_PAGE_DECK", "_PAGE_SHELL", "_PAGE_FIGURE", "_PAGE_HERO_IMG", "_PAGE_COLUMN"):
        assert getattr(p, name) in src, name


def test_hero_is_og_fallback_and_prerendered(client, app):
    hero = _media(app, "press-hero")
    _page(app, "hero-page", hero_media_id=hero)
    html = client.get("/hero-page").get_data(as_text=True)
    head, body = html.split("</head>")[0], html.split("</head>")[1]
    assert re.search(r'property="og:image" content="[^"]*/media/originals/press-hero.jpg"', head)
    root = body.split('data-wsf-prerender="page"', 1)[1]
    assert '<figure class="mb-14 border border-taupe-200 bg-cream lg:mb-16"><img src=' in root and 'alt="press-hero alt"' in root
