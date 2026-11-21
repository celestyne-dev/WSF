"""Server first paint = React's first frame (app/services/first_paint.py).

Two kinds of checks:
  * contract: the markup the server copies from React still exists in the
    React sources (class strings, tokens, image/placeholder resolution);
  * hard load of "/": the header and homepage the server sends have the
    real header (logo, primary navigation, search, account, Subscribe), the
    hero layout and media, the containers and card grids React renders,
    and the data each module starts from is the public API's own answer.
"""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.extensions import db
from app.services import first_paint as fp

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"
needs_frontend = pytest.mark.skipif(not FRONTEND_SRC.is_dir(), reason="frontend sources not present")


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _src(relative):
    return (FRONTEND_SRC / relative).read_text()


# --- contract with the React sources -----------------------------------------------------------

# Every class string the server copies, and the component it is copied from.
COPIED_CLASSES = {
    "components/layout/Header.jsx": [fp.HEADER_BAR, fp.HEADER_LOGO_WRAP, fp.HEADER_NAV, fp.HEADER_ACTIONS,
                                     fp.HEADER_SUBSCRIBE, fp.HEADER_MENU_BUTTON],
    "components/layout/AccountMenu.jsx": [fp.HEADER_ICON_BUTTON],
    "components/ui/SectionHeading.jsx": [fp.SECTION_HEADING_H2, fp.SECTION_HEADING_SUB, fp.VIEW_ALL,
                                         "flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between"],
    "components/cards/ArticleCard.jsx": [fp.LEAD_TITLE, fp.TITLE_LINK],
    "components/home/HeroModule.jsx": ["border-b border-taupe-200 bg-ivory py-10 sm:py-14",
                                       "container-editorial grid grid-cols-1 gap-10 lg:grid-cols-3",
                                       "flex flex-col gap-6 lg:border-l lg:border-taupe-200 lg:pl-10",
                                       "font-serif text-4xl font-semibold leading-tight text-charcoal sm:text-5xl"],
    "components/home/LatestStoriesModule.jsx": [fp.GRID_SECTION, fp.ARTICLE_GRID_4],
    "components/home/SeriesFeatureModule.jsx": [fp.CREAM_SECTION, fp.ARTICLE_GRID_3],
    "components/home/CareerPathwaysModule.jsx": [fp.PATHWAY_TILE],
    "components/home/NewsletterModule.jsx": ["border-t border-taupe-200 bg-charcoal py-16 text-ivory sm:py-20"],
    "components/home/FeaturedWomanModule.jsx": ["bg-plum-600 py-16 text-ivory sm:py-20", "aspect-[5/6] w-full max-w-md object-cover"],
}


@needs_frontend
@pytest.mark.parametrize("component", sorted(COPIED_CLASSES))
def test_copied_class_strings_exist_in_their_component(component):
    source = _src(component)
    for class_string in COPIED_CLASSES[component]:
        assert class_string in source, f"{component} no longer has {class_string!r}"


def _sample_homepage_modules():
    media = {"public_url": "/media/o.webp", "alt_text": "Alt",
             "variants": {"thumbnail": {"url": "/media/t.webp", "width": 320, "height": 213},
                          "card": {"url": "/media/c.webp", "width": 640, "height": 427},
                          "large": {"url": "/media/l.webp", "width": 1280, "height": 853}}}
    article = {"id": 1, "slug": "a", "title": "A", "excerpt": "E", "publish_date": "2026-11-16T09:00:00+00:00",
               "reading_time": 4, "hero_media": media, "author": {"name": "Au"}, "topics": [{"slug": "t", "name": "T"}]}
    closing = {"closesOn": "2026-12-01", "daysLeft": 3, "closingSoon": True}
    return [
        {"id": 1, "type": "hero", "config": {"leadArticleSlug": "a"}, "cta_label": "Go", "cta_url": "/go",
         "initial_data": {"secondary": [article]}},
        {"id": 2, "type": "latest_stories", "heading": "Latest", "config": {}, "initial_data": {"articles": [article]}},
        {"id": 3, "type": "featured_woman", "heading": "Woman", "config": {"personSlug": "p"},
         "initial_data": {"person": {"slug": "p", "name": "P", "photo": media, "featured_quote": "Q", "title": "CEO"}}},
        {"id": 4, "type": "opportunities", "heading": "O", "config": {}, "initial_data": {"items": [
            {"slug": "o", "title": "O", "type": "Grant", "featured": True, "closing": closing, "organization": {"name": "Org", "logo": media}}]}},
        {"id": 5, "type": "resources", "heading": "R", "config": {}, "initial_data": {"items": [
            {"slug": "r", "name": "R", "accessType": "email_gate", "isFree": True, "featured": True, "format": {"label": "Guide"}}]}},
        {"id": 6, "type": "events", "heading": "Ev", "config": {}, "initial_data": {"items": [
            {"slug": "e", "title": "E", "type": "Workshop", "format": "virtual", "date": "2026-12-03", "cover_media": media}]}},
        {"id": 7, "type": "jobs", "heading": "J", "config": {}, "initial_data": {"items": [
            {"slug": "j", "title": "J", "company_name": "Co", "location": "Nairobi", "work_mode": "Remote",
             "published_date": "2026-11-10", "closing": closing}]}},
        {"id": 8, "type": "series_feature", "heading": "S", "config": {"seriesSlug": "s"},
         "initial_data": {"series": {"slug": "s", "name": "S", "description": "D"}, "articles": [article]}},
        {"id": 9, "type": "topic_collection", "heading": "T", "config": {"topicSlug": "t"},
         "initial_data": {"topic": {"slug": "t", "name": "T"}, "articles": [article]}},
        {"id": 10, "type": "newsletter", "heading": "Weekly", "subheading": "Sub", "config": {}, "initial_data": {"subscriberCount": 1200}},
        {"id": 11, "type": "community_cta", "heading": "Join", "config": {}, "media": media},
        {"id": 12, "type": "career_pathways", "heading": "Start", "config": {"eyebrow": "Paths"}, "cta_label": "All", "cta_url": "/career-hub",
         "resolved": {"cards": [{"title": "Jobs", "href": "/jobs", "linkType": "internal", "icon": "briefcase"}]}},
        {"id": 13, "type": "content_collection", "heading": "C", "config": {"entityType": "people"},
         "resolved": {"entityType": "people", "items": [{"slug": "p", "name": "P", "title": "T"}]}},
    ]


@needs_frontend
def test_every_rendered_class_token_exists_in_the_react_sources():
    """Tailwind only generates classes it finds in frontend/src, so a token
    the server uses that React no longer uses would render unstyled."""
    corpus = " ".join(p.read_text() for p in FRONTEND_SRC.rglob("*.jsx"))
    corpus += " ".join(p.read_text() for p in FRONTEND_SRC.rglob("*.js"))
    lead = _sample_homepage_modules()[0]["initial_data"]["secondary"][0]
    html = fp.render_homepage(_sample_homepage_modules(), lead) + fp.render_header({"menus": {}}, pathname="/")
    tokens = {t for value in re.findall(r'class="([^"]*)"', html) for t in value.split()}
    lucide = {t for t in tokens if t.startswith("lucide")}  # lucide-react's own icon classes
    missing = sorted(t for t in tokens - lucide if not re.search(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", corpus))
    assert missing == []


def test_media_resolution_matches_the_shared_fixture():
    """tests/fixtures/first_paint_media.json is generated from utils/media.js;
    frontend/src/utils/firstPaintContract.test.js checks the JS side."""
    fixture = json.loads((Path(__file__).parent / "fixtures" / "first_paint_media.json").read_text())
    for case in fixture["placeholders"]:
        assert fp.svg_placeholder("placeholder", case["width"], case["height"], case["tone"]) == case["src"]
    for case in fixture["media"]:
        media = {"variants": case["media"]["variants"], "public_url": case["media"]["mediaPath"]}
        assert fp.resolve_media(media, case["variant"], case["width"], case["height"]) == (case["src"], case["srcSet"])


def test_media_img_mirrors_media_image_attributes():
    img = fp.media_img({"variants": {"card": {"url": "/media/c.webp", "width": 640}, "thumbnail": {"url": "/media/t.webp", "width": 320}}},
                       variant="card", alt='A "b"', width=800, height=533, sizes="50vw", class_name="x")
    assert img == ('<img src="/media/c.webp" srcset="/media/t.webp 320w, /media/c.webp 640w" sizes="50vw" alt="A &quot;b&quot;" '
                   'width="800" height="533" loading="lazy" decoding="async" class="x">')
    hero = fp.media_img(None, width=1400, height=933, priority=True)
    assert 'loading="eager" fetchpriority="high"' in hero and 'sizes="100vw"' in hero and 'height="933"' in hero


def test_formatting_matches_the_frontend_helpers():
    assert fp.format_short_date("2026-11-16T23:30:00+00:00") == "Nov 16"
    assert fp.format_short_date(None) == ""
    assert fp.long_date("2026-12-01") == "1 December 2026"
    assert fp.short_date("2026-12-01", 2026) == "1 Dec" and fp.short_date("2027-01-05", 2026) == "5 Jan 2027"
    assert fp.closing_label({"closesOn": "2026-12-01", "daysLeft": 0}) == "Closes today"
    assert fp.closing_label({"closesOn": "2026-12-01", "daysLeft": 1}) == "Closes tomorrow"
    assert fp.closing_label(None) == ""
    assert fp._js_num(1234567) == "1,234,567" and fp._js_num(1500.5) == "1,500.5" and fp._js_num(2.0) == "2"
    assert fp._js_round(2.5) == 3 and fp._js_round(0.5) == 1  # Math.round, not banker's rounding
    assert fp.format_currency(0) == "Free" and fp.format_currency(2500, "USD") == "USD 2,500"
    assert fp.format_salary({"salary_min": 1000, "salary_max": 2000, "currency": "KES", "salary_period": "month"}) == "KES 1,000–2,000/month"
    assert fp.format_funding({"funding_min": 5, "funding_max": 5, "currency": "USD"}) == "USD 5"
    assert fp.reading_time({"reading_time": None}) == 1


def _nav(*items, secondary=()):
    def item(label, url, children=()):
        return {"label": label, "url": url, "itemType": "route", "linkType": "internal",
                "children": [item(*c) for c in children], "style": "standard"}
    return {"menus": {"primary": {"items": [item(*i) for i in items]}, "secondary": {"items": [item(*i) for i in secondary]}}}


def test_header_entries_follow_the_mega_menu_rules():
    nav = _nav(("Stories", "/topics"), ("People", "/people"), ("Opportunities", "/opportunities"), ("Jobs", "/jobs"),
               ("Resources", "/resources"), ("Community", "/community"), ("Circle", "/circle"),
               secondary=[("Newsletter", "/newsletter"), ("Press", "/press")])
    entries = fp.header_entries(nav)
    # /jobs folds into Opportunities (more than MIN_TOP_LEVEL entries remain)
    assert [e["label"] for e in entries] == ["Stories", "People", "Opportunities", "Resources", "Community", "Circle"]
    assert [e["menu"] for e in entries] == [True, True, True, True, True, False]
    html = fp.render_header(nav, pathname="/jobs/some-role")
    opportunities = re.search(r'<a href="/opportunities"[^>]*>', html).group(0)
    assert "after:bg-burgundy-600" in opportunities  # the active section is marked as in React
    assert "aria-current" not in opportunities  # a menu trigger is never "current page"


# --- hard load of "/" ---------------------------------------------------------------------------


def _seed_homepage(app, with_media=True):
    from app.models.article import Article
    from app.models.cms import HomepageModule, Menu, MenuItem
    from app.models.media import Media, MediaVariant
    from app.models.people import Author

    with app.app_context():
        primary, secondary = Menu(key="primary"), Menu(key="secondary")
        db.session.add_all([primary, secondary])
        db.session.flush()
        for i, (label, url) in enumerate([("Stories", "/topics"), ("People", "/people"), ("Opportunities", "/opportunities"),
                                          ("Resources", "/resources"), ("WSF Circle", "/circle"), ("Community", "/community")]):
            db.session.add(MenuItem(menu_id=primary.id, label=label, item_type="route", url=url, sort_order=i))
        db.session.add(MenuItem(menu_id=secondary.id, label="Newsletter", item_type="route", url="/newsletter", sort_order=0))
        media_id = None
        if with_media:
            media = Media(original_filename="a.png", stored_filename="a.webp", file_path="x/a.webp", public_url="/media/originals/a.webp",
                          mime_type="image/webp", width=2400, height=1600, alt_text="Lead photo")
            db.session.add(media)
            db.session.flush()
            for name, w in (("thumbnail", 320), ("card", 640), ("medium", 960), ("large", 1280), ("hero", 1920)):
                db.session.add(MediaVariant(media_id=media.id, variant=name, file_path=f"x/a-{name}.webp",
                                            public_url=f"/media/a-{name}.webp", width=w, height=round(w * 2 / 3)))
            media_id = media.id
        author = Author(slug="fp-author", name="FP Author", status="active")
        db.session.add(author)
        db.session.flush()
        now = datetime.now(timezone.utc)
        for i, slug in enumerate(["lead-story", "second-story", "third-story"]):
            db.session.add(Article(slug=slug, title=slug.replace("-", " ").title(), status="published", author_id=author.id,
                                   excerpt=f"{slug} excerpt.", content=[], hero_media_id=media_id if i == 0 else None,
                                   publish_date=now - timedelta(days=i + 1)))
        db.session.add_all([
            HomepageModule(type="hero", enabled=True, sort_order=0,
                           config={"leadArticleSlug": "lead-story", "secondaryArticleSlugs": ["second-story"]}),
            HomepageModule(type="latest_stories", enabled=True, sort_order=1, heading="Latest Stories", config={"itemCount": 4}),
            HomepageModule(type="featured_woman", enabled=True, sort_order=2, heading="Woman", config={"personSlug": "nobody"}),
        ])
        db.session.commit()


def _bootstrap(html, kind):
    match = re.search(rf'<script type="application/json" data-wsf-bootstrap="{kind}">(.*?)</script>', html, re.DOTALL)
    return json.loads(match.group(1)) if match else None


def test_hard_load_header_is_the_real_header(client, app):
    _seed_homepage(app)
    html = client.get("/").get_data(as_text=True)
    header = re.search(r"<header data-wsf-header-placeholder.*?</header>", html, re.DOTALL).group(0)
    assert 'class="fixed inset-x-0 top-0 z-40 border-b border-taupe-200 bg-ivory"' in header
    assert f'class="{fp.HEADER_BAR}"' in header  # h-16 / lg:h-[68px], like Header.jsx
    assert 'href="/"' in header  # logo
    nav = re.search(r'<nav aria-label="Primary" class="([^"]*)">(.*?)</nav>', header, re.DOTALL)
    assert nav.group(1) == fp.HEADER_NAV
    assert re.findall(r">([^<>]+)<svg", nav.group(2)) == ["Stories", "People", "Opportunities", "Resources", "Community"]
    assert ">WSF Circle</a>" in nav.group(2)
    assert 'aria-label="Search"' in header and 'aria-label="Sign in or create an account"' in header
    assert re.search(r'<a href="/newsletter" class="[^"]*md:inline-flex">Subscribe</a>', header)
    assert "lucide-menu" in header  # mobile menu icon
    assert "data-wsf-header-placeholder-style" in html  # 65px / 69px reserve


def test_hard_load_homepage_matches_the_react_layout(client, app):
    _seed_homepage(app)
    html = client.get("/").get_data(as_text=True)
    root = re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL).group(1)
    assert root.startswith('<main data-wsf-prerender="home" class="flex-1"><noscript>')  # no-JS nav first
    assert '</noscript><div><section ' in root  # then HomePage.jsx's <div> of modules
    assert 'max-w-reading' not in root  # not the generic article column
    # Hero: the lead story layout family, its image and an H1.
    assert '<section class="border-b border-taupe-200 bg-ivory py-10 sm:py-14">' in root
    assert '<div class="container-editorial grid grid-cols-1 gap-10 lg:grid-cols-3">' in root
    assert len(re.findall(r"<h1\b", root)) == 1 and re.search(r"<h1 class=\"[^\"]*\"><a href=\"/lead-story\"", root)
    hero_img = re.search(r'<img src="/media/a-large.webp" srcset="([^"]*)" sizes="\(min-width: 1024px\) 66vw, 100vw"[^>]*>', root)
    assert hero_img and 'fetchpriority="high"' in hero_img.group(0) and 'alt="Lead photo"' in hero_img.group(0)
    assert hero_img.group(1).startswith("/media/a-thumbnail.webp 320w") and hero_img.group(1).endswith("/media/a-hero.webp 1920w")
    # The LCP preload asks for the same image the hero renders.
    preload = re.search(r'<link rel="preload" as="image" href="([^"]*)"', html)
    assert preload and preload.group(1).endswith("/media/a-large.webp")
    # Secondary story as a horizontal card, latest stories as the 4-column grid.
    assert '<article class="group flex gap-4 sm:gap-5">' in root and 'href="/second-story"' in root
    assert f'<div class="{fp.ARTICLE_GRID_4}">' in root and root.count('<article class="group flex flex-col">') == 3
    # A featured woman whose person is not public renders nothing, as in React.
    assert "Woman" not in root


def test_homepage_modules_start_from_the_public_api_answer(client, app):
    _seed_homepage(app)
    html = client.get("/").get_data(as_text=True)
    modules = {m["type"]: m for m in _bootstrap(html, "homepage")["modules"]}
    api = client.get("/api/v1/articles?per_page=4").get_json()["data"]
    assert [a["slug"] for a in modules["latest_stories"]["initial_data"]["articles"]] == [a["slug"] for a in api]
    assert [a["slug"] for a in modules["hero"]["initial_data"]["secondary"]] == ["second-story"]
    # A 404 is passed on as "nothing to show" so the component does not refetch.
    assert modules["featured_woman"]["initial_data"] == {"person": None}
    # Bootstraps come after the visible content.
    assert html.index('<div id="root">') < html.index('data-wsf-bootstrap="homepage"')


def test_shell_bootstrap_on_every_html_page(client, app):
    _seed_homepage(app, with_media=False)
    for path in ("/", "/jobs", "/about-us-not-a-page"):
        response = client.get(path)
        html = response.get_data(as_text=True)
        shell = _bootstrap(html, "shell")
        assert shell is not None, path
        assert shell["key"] == "shell"
        assert client.get("/api/v1/public/navigation").get_json()["data"] == shell["data"]["navigation"]
        assert client.get("/api/v1/public/settings").get_json()["data"] == shell["data"]["settings"]
        assert client.get("/api/v1/public/footer").get_json()["data"] == shell["data"]["footer"]


def test_without_javascript_navigation_stays_reachable(client, app):
    _seed_homepage(app, with_media=False)
    html = client.get("/").get_data(as_text=True)
    noscript = re.search(r'<noscript><nav aria-label="Site sections".*?</nav></noscript>', html, re.DOTALL)
    assert noscript and 'href="/opportunities"' in noscript.group(0)
    # The inert mobile menu icon is decorative, never a fake button.
    header = re.search(r"<header data-wsf-header-placeholder.*?</header>", html, re.DOTALL).group(0)
    assert "<button" not in header
