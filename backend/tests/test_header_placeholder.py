"""The static first-paint header placeholder spa_shell puts before #root on
prerendered public pages, so the page doesn't move down when React mounts
its (fixed-height) header."""
import os
import re

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _author(app):
    from app.models.people import Author

    with app.app_context():
        db.session.add(Author(slug="placeholder-author", name="Placeholder Author", status="active",
                              bio=[{"type": "paragraph", "text": "Bio."}]))
        db.session.commit()


def _placeholder(html):
    match = re.search(r'<header data-wsf-header-placeholder="true"[^>]*>(.*?)</header>\s*<div id="root">', html, re.S)
    return match


def test_prerendered_page_reserves_the_header_height(client, app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    _author(app)
    html = client.get("/authors/placeholder-author").get_data(as_text=True)
    assert html.count('data-wsf-header-placeholder="true"') == 1 and html.count("data-wsf-header-placeholder-style") == 1
    match = _placeholder(html)
    assert match, "placeholder must sit directly before #root"
    assert 'class="fixed inset-x-0 top-0 z-40 border-b border-taupe-200 bg-ivory"' in match.group(0)
    # The header height is reserved inside the prerender (so #root never moves).
    assert "#root>[data-wsf-prerender]::before" in html and "height:65px" in html and "height:69px" in html
    assert "h-16" in match.group(0) and "lg:h-[68px]" in match.group(0)
    inner = match.group(1)
    assert 'href="/"' in inner and "Women Shaping" in inner
    # The real header's first state (first_paint.render_header): primary
    # navigation, search, account and Subscribe as plain links; never a
    # fake button that needs JavaScript, and never the page's H1.
    assert '<nav aria-label="Primary"' in inner
    assert 'href="/search"' in inner and 'href="/login"' in inner and ">Subscribe</a>" in inner
    for absent in ("<button", "<h1"):
        assert absent not in inner, absent
    # #root content is unchanged (still starts with the prerender <main>).
    root = html.split('<div id="root">', 1)[1]
    assert root.startswith('<main data-wsf-prerender="author"')


def test_configured_logo_is_used(client, app):
    from app.models.media import Media
    from app.services.site_settings import get_site_identity_raw, save_site_identity

    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    _author(app)
    with app.app_context():
        media = Media(original_filename="logo.png", stored_filename="stored-logo.png", file_path="uploads/brand/logo.png",
                      public_url="/media/logo.png", mime_type="image/png")
        db.session.add(media)
        db.session.flush()
        save_site_identity({**get_site_identity_raw(), "site_name": "Women Shaping Futures", "logo_media_id": media.id})
        db.session.commit()
    inner = _placeholder(client.get("/authors/placeholder-author").get_data(as_text=True)).group(1)
    assert '<img src="/media/logo.png" alt="Women Shaping Futures" class="h-8 w-auto sm:h-9">' in inner
    assert "uploads/brand" not in inner and "Stories &middot;" not in inner


def test_no_placeholder_without_a_prerender(client, app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
    for path in ("/authors/nobody", "/admin", "/login"):
        html = client.get(path).get_data(as_text=True)
        has_prerender = "data-wsf-prerender" in html
        assert ("data-wsf-header-placeholder" in html) == has_prerender, path
