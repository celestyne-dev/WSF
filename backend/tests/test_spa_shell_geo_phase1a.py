"""AI Search / GEO Phase 1A — complete server SEO coverage for every public,
indexable route family (see spa_shell.py's module docstring).

Covers the routes Phase 1 had left on the generic shell (Organization/
Directory/Learning/Shop/Newsletter list + detail), the public singleton
pages that were falling into the single-segment Article lookup and
404ing, the newsletter unsubscribe-token route, and sitemap/server
parity.
"""
import json
import os
import re
import uuid
from datetime import datetime, timezone

import pytest

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


# --- helpers ------------------------------------------------------------


def _meta(html, attr, key):
    match = re.search(rf'<meta\s+(?:[^>]*?\s)?{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _title(html):
    match = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
    return match.group(1) if match else None


def _canonical(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html, re.IGNORECASE)
    return match.group(1) if match else None


def _json_ld(html, attr):
    matches = re.findall(rf"<script\b[^>]*{re.escape(attr)}[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL)
    assert len(matches) == 1, f"expected exactly one {attr} tag, found {len(matches)}"
    return json.loads(matches[0])


def _count(attr, html):
    return len(re.findall(rf"<script\b[^>]*{re.escape(attr)}", html))


def _get(client, path):
    resp = client.get(path)
    return resp.status_code, resp.get_data(as_text=True)


def _media(app, name, alt_text=None):
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename=f"{name}.jpg",
            stored_filename=f"{name}.jpg",
            file_path=f"/srv/private-storage/{name}.jpg",
            public_url=f"/media/originals/{name}.jpg",
            mime_type="image/jpeg",
            alt_text=alt_text,
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _org(app, slug, status="published", **fields):
    from app.models.people import Organization

    with app.app_context():
        org = Organization(slug=slug, name=fields.pop("name", "Kaziwave Labs"), status=status, description=[], **fields)
        db.session.add(org)
        db.session.commit()
        return org.id


def _listing(app, org_id, status="published", **fields):
    from app.models.directory import DirectoryListing

    with app.app_context():
        listing = DirectoryListing(
            organization_id=org_id,
            status=status,
            listing_type="business",
            ownership_classification="women_owned",
            classification_provenance="self_attested",
            verification_status="unverified",
            **fields,
        )
        db.session.add(listing)
        db.session.commit()
        return listing.id


def _instructor(app):
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="geo-instructor").first()
        if author is None:
            author = Author(slug="geo-instructor", name="GEO Instructor", status="active")
            db.session.add(author)
            db.session.commit()
        return author.id


def _program(app, slug, status="published", access_type="free", with_curriculum=False, **fields):
    from app.models.learning import LearningLesson, LearningModule, LearningProgram

    instructor_id = _instructor(app)
    with app.app_context():
        program = LearningProgram(
            slug=slug, title=fields.pop("title", "Leading With Purpose"), overview=[], status=status,
            access_type=access_type, primary_instructor_id=instructor_id, **fields,
        )
        db.session.add(program)
        db.session.flush()
        if with_curriculum:
            module = LearningModule(learning_program_id=program.id, title="Module One", sort_order=0)
            db.session.add(module)
            db.session.flush()
            db.session.add(LearningLesson(
                module_id=module.id, title="Lesson One", lesson_type="text",
                content=[{"type": "paragraph", "text": "PROTECTED-LESSON-BODY-TEXT"}],
                summary="Lesson summary", duration_minutes=5, sort_order=0,
                external_url="https://video.example.org/PROTECTED-VIDEO-URL",
            ))
        db.session.commit()
        return program.id


def _product(app, slug, status="active", **fields):
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=slug, name=fields.pop("name", "Negotiation Workbook"), status=status, description=[], **fields)
        db.session.add(product)
        db.session.commit()
        return product.id


def _issue(app, slug, status="sent", **fields):
    from app.models.newsletter import NewsletterIssue

    with app.app_context():
        subject = fields.pop("subject", "January Digest")
        issue = NewsletterIssue(
            slug=slug, title=fields.pop("title", subject), subject=subject, status=status,
            sent_at=datetime.now(timezone.utc) if status == "sent" else None, **fields,
        )
        db.session.add(issue)
        db.session.commit()
        return issue.id


def _breadcrumb_names(html):
    return [item["name"] for item in _json_ld(html, "data-breadcrumb-structured-data")["itemListElement"]]


# --- list / landing pages --------------------------------------------------


LIST_PAGES = [
    ("/organizations", "Organizations | Women Shaping Futures",
     "Companies, foundations, universities, and institutions in the Women Shaping Futures network.", "Organizations"),
    ("/directory", "Business &amp; Professional Directory | Women Shaping Futures",
     "Discover women-owned, women-led, and women-founded businesses and professional organizations in the Women Shaping Futures network.", "Directory"),
    ("/learning", "Learning | Women Shaping Futures",
     "Courses, masterclasses, and learning programs on leadership, entrepreneurship, and career growth.", "Learning"),
    ("/shop", "Shop | Women Shaping Futures",
     "Digital products, guides, templates, and workbooks from Women Shaping Futures.", "Shop"),
    ("/newsletter", "WSF Weekly Newsletter | Women Shaping Futures",
     "Subscribe to WSF Weekly for stories, jobs, and opportunities delivered every Thursday.", "Newsletter"),
]


@pytest.mark.parametrize("path,title,description,crumb", LIST_PAGES)
def test_list_pages_have_full_server_seo(client, path, title, description, crumb):
    status, html = _get(client, path)
    assert status == 200
    assert _title(html) == title
    assert _meta(html, "name", "description") == description
    assert _meta(html, "name", "robots") == "index, follow"
    assert _canonical(html) == f"{SITE}{path}"
    assert _meta(html, "property", "og:url") == f"{SITE}{path}"
    assert _meta(html, "name", "twitter:card") == "summary_large_image"
    site = _json_ld(html, "data-site-structured-data")
    assert {d["@type"] for d in site} == {"WebSite", "Organization"}
    assert _breadcrumb_names(html) == ["Home", crumb]


# --- public singleton pages -------------------------------------------------


SINGLETONS = [
    ("/partnerships", "Partnerships | Women Shaping Futures"),
    ("/mentorship", "Mentorship | Women Shaping Futures"),
    ("/submit", "Submit Your Story | Women Shaping Futures"),
    ("/nominate", "Nominate a Woman | Women Shaping Futures"),
    ("/directory/submit", "Submit Your Business | Business &amp; Professional Directory | Women Shaping Futures"),
    ("/advertise", "Advertise | Women Shaping Futures"),
    ("/community", "Community | Women Shaping Futures"),
    ("/circle", "WSF Circle | Women Shaping Futures"),
]


@pytest.mark.parametrize("path,title", SINGLETONS)
def test_public_singletons_hard_load_200_with_metadata(client, path, title):
    status, html = _get(client, path)
    assert status == 200
    assert _title(html) == title
    assert _meta(html, "name", "robots") == "index, follow"
    assert _canonical(html) == f"{SITE}{path}"
    assert _count("data-site-structured-data", html) == 1
    # No visible breadcrumb on these pages, so none is invented.
    assert _count("data-breadcrumb-structured-data", html) == 0
    assert _count("data-article-structured-data", html) == 0


def test_singleton_does_not_resolve_as_article(client, app):
    # An article that happens to share a singleton's slug must not win
    # over the real React route (React matches /submit before /:slug).
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author(slug="geo-author", name="GEO Author", status="active")
        db.session.add(author)
        db.session.flush()
        db.session.add(Article(slug="submit", title="An Article Named Submit", status="published", author_id=author.id, content=[]))
        db.session.commit()
    status, html = _get(client, "/submit")
    assert status == 200
    assert _title(html) == "Submit Your Story | Women Shaping Futures"
    assert "An Article Named Submit" not in html


def test_advertise_uses_published_cms_seo_and_hero(client, app):
    from app.models.cms import AdvertisePage

    hero_id = _media(app, "advertise-hero", alt_text="Readers at a WSF event")
    with app.app_context():
        page = db.session.get(AdvertisePage, 1) or AdvertisePage(id=1)
        page.status = "published"
        page.seo = {"title": "Advertise With WSF", "description": "Custom advertise description.", "robots": "noindex, follow"}
        page.hero_media_id = hero_id
        db.session.add(page)
        db.session.commit()
    status, html = _get(client, "/advertise")
    assert status == 200
    assert _title(html) == "Advertise With WSF"
    assert _meta(html, "name", "description") == "Custom advertise description."
    assert _meta(html, "name", "robots") == "noindex, follow"
    assert _meta(html, "property", "og:image") == f"{SITE}/media/originals/advertise-hero.jpg"
    assert _meta(html, "property", "og:image:alt") == "Readers at a WSF event"
    assert _canonical(html) == f"{SITE}/advertise"


def test_community_draft_cms_row_falls_back_to_fixed_copy(client, app):
    from app.models.community import CommunityPage

    with app.app_context():
        page = db.session.get(CommunityPage, 1) or CommunityPage(id=1)
        page.status = "draft"
        page.seo = {"title": "DRAFT COMMUNITY SEO TITLE"}
        db.session.add(page)
        db.session.commit()
    status, html = _get(client, "/community")
    assert status == 200
    assert _title(html) == "Community | Women Shaping Futures"
    assert "DRAFT COMMUNITY SEO TITLE" not in html


# --- private routes keep their noindex behavior ----------------------------


@pytest.mark.parametrize("path,robots", [
    ("/login", "noindex, follow"),
    ("/account", "noindex, nofollow"),
    ("/account/membership", "noindex, nofollow"),
    ("/resources/checkout/callback", "noindex, nofollow"),
    ("/circle/checkout/callback", "noindex, nofollow"),
    ("/reset-password", "noindex, nofollow"),
])
def test_private_routes_stay_noindex(client, path, robots):
    status, html = _get(client, path)
    assert status == 200
    assert _meta(html, "name", "robots") == robots
    assert _count("data-site-structured-data", html) == 0


# --- Organization -----------------------------------------------------------


def test_organization_detail(client, app):
    logo_id = _media(app, "kaziwave-logo", alt_text="Kaziwave Labs logo")
    _org(app, "kaziwave", short_description="A fintech lab.", website="https://kaziwave.example.com", founded_year=2019, logo_media_id=logo_id)
    status, html = _get(client, "/organizations/kaziwave")
    assert status == 200
    assert _title(html) == "Kaziwave Labs | Women Shaping Futures"
    assert _meta(html, "name", "description") == "A fintech lab."
    assert _canonical(html) == f"{SITE}/organizations/kaziwave"
    assert _meta(html, "property", "og:image") == f"{SITE}/media/originals/kaziwave-logo.jpg"
    assert _meta(html, "property", "og:image:alt") == "Kaziwave Labs logo"
    org = _json_ld(html, "data-org-structured-data")
    assert org == {
        "@context": "https://schema.org", "@type": "Organization", "name": "Kaziwave Labs",
        "url": f"{SITE}/organizations/kaziwave", "sameAs": ["https://kaziwave.example.com"],
        "logo": f"{SITE}/media/originals/kaziwave-logo.jpg", "foundingDate": "2019",
    }
    assert _breadcrumb_names(html) == ["Home", "Organizations", "Kaziwave Labs"]
    assert _count("data-site-structured-data", html) == 1
    # Small logo — never preloaded.
    assert 'data-lcp-image-preload' not in html


def test_organization_seo_overrides_and_breadcrumb_uses_display_name(client, app):
    _org(app, "kaziwave", seo={"title": "Kaziwave SEO Title", "description": "SEO desc", "canonical": "https://example.org/kz", "robots": "noindex, follow"})
    status, html = _get(client, "/organizations/kaziwave")
    assert status == 200
    assert _title(html) == "Kaziwave SEO Title"
    assert _meta(html, "name", "description") == "SEO desc"
    assert _canonical(html) == "https://example.org/kz"
    assert _meta(html, "name", "robots") == "noindex, follow"
    assert _breadcrumb_names(html)[-1] == "Kaziwave Labs"


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_non_public_organization_404s_without_leak(client, app, status_value):
    _org(app, "secret-org", status=status_value, name="Secret Org Name", short_description="Secret description", seo={"title": "Secret SEO"})
    status, html = _get(client, "/organizations/secret-org")
    assert status == 404
    assert _meta(html, "name", "robots") == "noindex, follow"
    for leaked in ("Secret Org Name", "Secret description", "Secret SEO", "secret-org"):
        assert leaked not in html


def test_unknown_paths_under_enhanced_prefixes_404(client):
    for path in ("/organizations/nope", "/learning/nope", "/shop/nope", "/newsletter/nope", "/directory/nope",
                 "/organizations/a/b", "/shop/a/b", "/learning/a/b", "/newsletter/unsubscribe"):
        status, _ = _get(client, path)
        assert status == 404, path


# --- Directory ----------------------------------------------------------------


def test_directory_detail(client, app):
    logo_id = _media(app, "dir-logo")
    org_id = _org(app, "amani-studio", name="Amani Studio", short_description="Org description.", logo_media_id=logo_id, website="https://amani.example.com")
    _listing(app, org_id, service_summary="Brand design for founders.", verification_notes="INTERNAL-VERIFICATION-NOTE",
             rejection_reason="INTERNAL-REJECTION-REASON")
    status, html = _get(client, "/directory/amani-studio")
    assert status == 200
    assert _title(html) == "Amani Studio | Business &amp; Professional Directory | Women Shaping Futures"
    assert _meta(html, "name", "description") == "Brand design for founders."
    assert _canonical(html) == f"{SITE}/directory/amani-studio"
    assert _meta(html, "property", "og:image") == f"{SITE}/media/originals/dir-logo.jpg"
    data = _json_ld(html, "data-directory-structured-data")
    assert data["@type"] == "Organization"
    assert data["description"] == "Brand design for founders."
    assert data["sameAs"] == ["https://amani.example.com"]
    assert _breadcrumb_names(html) == ["Home", "Directory", "Amani Studio"]
    assert "INTERNAL-VERIFICATION-NOTE" not in html and "INTERNAL-REJECTION-REASON" not in html


def test_directory_description_falls_back_to_org_short_description(client, app):
    org_id = _org(app, "amani-studio", short_description="Org description.")
    _listing(app, org_id)
    _, html = _get(client, "/directory/amani-studio")
    assert _meta(html, "name", "description") == "Org description."


@pytest.mark.parametrize("listing_status,org_status", [("pending", "published"), ("approved", "published"), ("rejected", "published"), ("archived", "published"), ("published", "draft"), ("published", "archived")])
def test_directory_requires_listing_and_org_public(client, app, listing_status, org_status):
    org_id = _org(app, "hidden-studio", status=org_status, name="Hidden Studio Name")
    _listing(app, org_id, status=listing_status, service_summary="Hidden summary")
    status, html = _get(client, "/directory/hidden-studio")
    assert status == 404
    assert "Hidden Studio Name" not in html and "Hidden summary" not in html


def test_directory_org_without_listing_404s(client, app):
    _org(app, "no-listing")
    assert _get(client, "/directory/no-listing")[0] == 404


# --- Learning -----------------------------------------------------------------


def test_learning_detail(client, app):
    hero_id = _media(app, "program-hero", alt_text="Workshop in session")
    _program(app, "leading", short_description="A six-week leadership course.", hero_media_id=hero_id)
    status, html = _get(client, "/learning/leading")
    assert status == 200
    assert _title(html) == "Leading With Purpose | Women Shaping Futures Learning"
    assert _meta(html, "name", "description") == "A six-week leadership course."
    assert _meta(html, "name", "robots") == "index, follow"
    assert _canonical(html) == f"{SITE}/learning/leading"
    assert _meta(html, "property", "og:image") == f"{SITE}/media/originals/program-hero.jpg"
    assert _breadcrumb_names(html) == ["Home", "Learning", "Leading With Purpose"]
    # No frontend structured-data hook exists for Learning — none invented.
    assert "data-learning-structured-data" not in html


def test_learning_description_fallback_chain_and_seo(client, app):
    _program(app, "subtitle-only", title="Subtitle Program", subtitle="The subtitle")
    _, html = _get(client, "/learning/subtitle-only")
    assert _meta(html, "name", "description") == "The subtitle"
    _program(app, "title-only", title="Title Only Program")
    _, html = _get(client, "/learning/title-only")
    assert _meta(html, "name", "description") == "Title Only Program"
    _program(app, "with-seo", seo={"title": "SEO T", "description": "SEO D", "canonical": "https://example.org/c", "robots": "noindex, nofollow"})
    _, html = _get(client, "/learning/with-seo")
    assert _title(html) == "SEO T"
    assert _canonical(html) == "https://example.org/c"
    # LearningProgramDetailPage passes no robots — server mirrors that.
    assert _meta(html, "name", "robots") == "index, follow"


def test_circle_only_learning_shell_never_contains_protected_curriculum(client, app):
    _program(app, "circle-course", access_type="circle_only", with_curriculum=True, short_description="Members-only course.")
    status, html = _get(client, "/learning/circle-course")
    assert status == 200
    assert _meta(html, "name", "description") == "Members-only course."
    for protected in ("PROTECTED-LESSON-BODY-TEXT", "PROTECTED-VIDEO-URL", "video.example.org", "Lesson One", "Module One"):
        assert protected not in html
    assert "data-wsf-bootstrap" not in html


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_non_public_learning_program_404s(client, app, status_value):
    _program(app, "draft-course", status=status_value, title="Unreleased Course Title")
    status, html = _get(client, "/learning/draft-course")
    assert status == 404
    assert "Unreleased Course Title" not in html


# --- Shop ---------------------------------------------------------------------


def test_product_detail(client, app):
    from app.models.commerce import ProductCategory

    cover_id = _media(app, "workbook-cover", alt_text="Workbook cover")
    with app.app_context():
        category = ProductCategory(slug="guides", name="Guides")
        db.session.add(category)
        db.session.commit()
        category_id = category.id
    _product(
        app, "workbook", short_description="Plan your next raise.", cover_media_id=cover_id, sku="WB-1", category_id=category_id,
        price=1500, sale_price=1200, currency="KES", purchase_url="https://pay.example.com/wb", shipping_notes="INTERNAL-SHIPPING-NOTE",
    )
    status, html = _get(client, "/shop/workbook")
    assert status == 200
    assert _title(html) == "Negotiation Workbook | Women Shaping Futures Shop"
    assert _meta(html, "name", "description") == "Plan your next raise."
    assert _canonical(html) == f"{SITE}/shop/workbook"
    assert _meta(html, "property", "og:image") == f"{SITE}/media/originals/workbook-cover.jpg"
    data = _json_ld(html, "data-product-structured-data")
    assert data == {
        "@context": "https://schema.org", "@type": "Product", "name": "Negotiation Workbook",
        "description": "Plan your next raise.", "image": f"{SITE}/media/originals/workbook-cover.jpg",
        "sku": "WB-1", "category": "Guides", "url": f"{SITE}/shop/workbook",
        "offers": {"@type": "Offer", "url": "https://pay.example.com/wb", "price": 1200, "priceCurrency": "KES",
                   "availability": "https://schema.org/InStock"},
    }
    assert _breadcrumb_names(html) == ["Home", "Shop", "Negotiation Workbook"]
    assert "INTERNAL-SHIPPING-NOTE" not in html
    assert "/srv/private-storage" not in html
    # Priority product image is preloaded, like the frontend's <img priority>.
    assert 'data-lcp-image-preload="true"' in html


def test_unavailable_product_visible_with_out_of_stock_offer(client, app):
    _product(app, "sold-out", status="unavailable", price=500)
    status, html = _get(client, "/shop/sold-out")
    assert status == 200
    assert _json_ld(html, "data-product-structured-data")["offers"]["availability"] == "https://schema.org/OutOfStock"


def test_hidden_price_product_has_no_offer(client, app):
    _product(app, "hidden-price", price=999, price_visible=False)
    _, html = _get(client, "/shop/hidden-price")
    data = _json_ld(html, "data-product-structured-data")
    assert "offers" not in data
    assert "999" not in html


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_non_public_product_404s(client, app, status_value):
    _product(app, "secret-product", status=status_value, name="Secret Product Name")
    status, html = _get(client, "/shop/secret-product")
    assert status == 404
    assert "Secret Product Name" not in html


# --- Newsletter -----------------------------------------------------------------


def test_sent_newsletter_issue_visible(client, app):
    cover_id = _media(app, "issue-cover")
    _issue(app, "jan-digest", preheader="This week's best stories.", cover_media_id=cover_id,
           audience_filter={"segment": "SECRET-AUDIENCE"}, provider_campaign_id="SECRET-CAMPAIGN-ID")
    status, html = _get(client, "/newsletter/jan-digest")
    assert status == 200
    assert _title(html) == "January Digest | WSF Weekly Archive"
    assert _meta(html, "name", "description") == "This week&#x27;s best stories."
    assert _canonical(html) == f"{SITE}/newsletter/jan-digest"
    assert _meta(html, "property", "og:image") == f"{SITE}/media/originals/issue-cover.jpg"
    assert _breadcrumb_names(html) == ["Home", "Newsletter", "January Digest"]
    assert "SECRET-AUDIENCE" not in html and "SECRET-CAMPAIGN-ID" not in html


def test_newsletter_description_fallbacks(client, app):
    _issue(app, "summary-only", subject="Summary Issue", summary="The summary")
    assert _meta(_get(client, "/newsletter/summary-only")[1], "name", "description") == "The summary"
    _issue(app, "subject-only", subject="Subject Only Issue")
    assert _meta(_get(client, "/newsletter/subject-only")[1], "name", "description") == "Subject Only Issue"


@pytest.mark.parametrize("status_value", ["draft", "scheduled", "archived"])
def test_unsent_newsletter_issue_404s_without_leak(client, app, status_value):
    _issue(app, "future-issue", status=status_value, subject="Unsent Subject Line")
    status, html = _get(client, "/newsletter/future-issue")
    assert status == 404
    assert "Unsent Subject Line" not in html


def test_unsubscribe_token_route_is_reachable_noindex_and_token_free(client):
    token = f"tok-{uuid.uuid4().hex}"
    status, html = _get(client, f"/newsletter/unsubscribe/{token}")
    assert status == 200
    assert _title(html) == "Unsubscribe | Women Shaping Futures"
    assert _meta(html, "name", "robots") == "noindex, nofollow"
    assert token not in html
    assert _canonical(html) is None
    assert _meta(html, "property", "og:url") is None
    assert "application/ld+json" not in html


def test_unsubscribe_route_is_never_an_issue_lookup(client, app):
    # Even an issue literally slugged "unsubscribe" doesn't hijack it.
    _issue(app, "unsubscribe", subject="Issue Named Unsubscribe")
    status, html = _get(client, "/newsletter/unsubscribe/abc123")
    assert status == 200
    assert "Issue Named Unsubscribe" not in html


# --- no duplicates / sitemap parity ---------------------------------------------


def test_no_duplicate_structured_data_tags_on_detail(client, app):
    _org(app, "dup-check")
    _, html = _get(client, "/organizations/dup-check")
    for attr in ("data-site-structured-data", "data-breadcrumb-structured-data", "data-org-structured-data"):
        assert _count(attr, html) == 1
    assert len(re.findall(r"<title>", html)) == 1
    assert len(re.findall(r'rel=["\']canonical', html)) == 1


def test_every_sitemap_url_hard_loads_200(client, app):
    org_id = _org(app, "sitemap-org")
    _listing(app, org_id)
    _program(app, "sitemap-course")
    _product(app, "sitemap-product")
    _product(app, "sitemap-unavailable", status="unavailable")
    _issue(app, "sitemap-issue")

    from app.services.sitemap import collect_public_sitemap_entries

    with app.app_context():
        locs = [entry["loc"] for entry in collect_public_sitemap_entries()]
    for expected in ("/organizations/sitemap-org", "/directory/sitemap-org", "/learning/sitemap-course",
                     "/shop/sitemap-product", "/shop/sitemap-unavailable", "/newsletter/sitemap-issue",
                     "/advertise", "/partnerships", "/community", "/circle", "/mentorship", "/submit",
                     "/nominate", "/directory/submit"):
        assert expected in locs
    for loc in locs:
        status, html = _get(client, loc)
        assert status == 200, loc
        assert _meta(html, "name", "robots") is not None, loc
        assert _count("data-site-structured-data", html) == 1, loc
