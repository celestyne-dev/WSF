"""AI Search / GEO Phase 3B2 — visible, semantic public content inside
#root for Author/Topic/Series/Directory/Product/Newsletter-issue detail
pages (app/services/prerender.py), proven on raw HTML only (no JS).
"""
import os
import re
from datetime import datetime, timezone

import pytest

from app.extensions import db

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")
SITE = "https://womenshapingfutures.org"


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


def _html(client, path):
    resp = client.get(path)
    return resp.status_code, resp.get_data(as_text=True)


def _root(html):
    match = re.search(r'<div id="root">(.*?)</div>\s*<script type="module"', html, re.DOTALL)
    return match.group(1) if match else ""


def _count_script(html, attr):
    return len(re.findall(rf"<script\b[^>]*{re.escape(attr)}", html))


def _canonical(html):
    match = re.search(r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']*)["\']', html)
    return match.group(1) if match else None


def _add(app, *objs):
    with app.app_context():
        db.session.add_all(objs)
        db.session.commit()
        return objs[0].id


def _body(text):
    return [{"type": "paragraph", "text": text}]


def _assert_valid(html, kind, title, text, canonical, entity_attr=None):
    root = _root(html)
    assert root.startswith(f'<main data-wsf-prerender="{kind}"')
    assert html.count("data-wsf-prerender=") == 1
    assert len(re.findall(r"<h1\b", root)) == 1
    assert re.search(rf"<h1[^>]*>{re.escape(title)}</h1>", root)
    assert text in root
    assert _canonical(html) == canonical
    assert _count_script(html, "data-breadcrumb-structured-data") == 1
    assert _count_script(html, "data-site-structured-data") == 1
    if entity_attr:
        assert _count_script(html, entity_attr) == 1
    lowered = root.lower()
    for hidden in (" hidden", "display:none", "visibility:hidden", 'aria-hidden="true"'):
        assert hidden not in lowered
    assert "<noscript" not in html.lower()
    return root


def _assert_404_no_leak(client, path, *secrets):
    status, html = _html(client, path)
    assert status == 404, path
    assert "data-wsf-prerender" not in html
    for secret in secrets:
        assert secret not in html, secret


# --- Author -------------------------------------------------------------------------


def test_author_prerender_and_linked_person_boundary(client, app):
    from app.models.people import Author, Person
    from app.models.taxonomy import Topic

    with app.app_context():
        draft_person = Person(slug="draft-person-slug", name="Draft Person Name", status="draft")
        topics = [Topic(slug="leadership", name="Leadership", status="published"),
                  Topic(slug="secret-topic", name="Secret Topic Name", status="archived")]
        db.session.add_all([draft_person, *topics])
        db.session.flush()
        author = Author(slug="amara-otieno", name="Amara Otieno", status="active", role="Senior Editor",
                        location="Nairobi", bio=_body("AUTHOR-BIO-TEXT"), website="https://amara.example.com",
                        social={"linkedin": "amara-o", "instagram": "amara_ig"}, person_id=draft_person.id)
        author.topics = topics
        db.session.add(author)
        db.session.commit()

    status, html = _html(client, "/authors/amara-otieno")
    assert status == 200
    root = _assert_valid(html, "author", "Amara Otieno", "AUTHOR-BIO-TEXT", f"{SITE}/authors/amara-otieno", "data-author-structured-data")
    for text in ("Senior Editor", "Nairobi", "Leadership", 'href="https://amara.example.com"',
                 'href="https://linkedin.com/in/amara-o"', 'href="https://instagram.com/amara_ig"'):
        assert text in root, text
    # The public AuthorSchema nulls an unpublished linked Person — so does the HTML.
    for secret in ("Draft Person Name", "draft-person-slug", "Secret Topic Name", "secret-topic"):
        assert secret not in html, secret


def test_author_linked_published_person_link(client, app):
    from app.models.people import Author, Person

    with app.app_context():
        person = Person(slug="public-person", name="Public Person", status="published")
        db.session.add(person)
        db.session.flush()
        db.session.add(Author(slug="linked-author", name="Linked Author", status="active", person_id=person.id))
        db.session.commit()
    _, html = _html(client, "/authors/linked-author")
    assert 'href="/people/public-person"' in _root(html)


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_non_active_author_404(client, app, status_value):
    from app.models.people import Author

    _add(app, Author(slug="inactive-author", name="Inactive Author Name", status=status_value, bio=_body("INACTIVE-BIO")))
    _assert_404_no_leak(client, "/authors/inactive-author", "Inactive Author Name", "INACTIVE-BIO")


# --- Topic / Series -----------------------------------------------------------------------


def test_topic_prerender(client, app):
    from app.models.taxonomy import Topic

    _add(app, Topic(slug="money", name="Money", status="published", description="TOPIC-DESCRIPTION-TEXT"))
    status, html = _html(client, "/topics/money")
    assert status == 200
    _assert_valid(html, "topic", "Money", "TOPIC-DESCRIPTION-TEXT", f"{SITE}/topics/money")


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_nonpublic_topic_and_series_404(client, app, status_value):
    from app.models.taxonomy import Series, Topic

    _add(app, Topic(slug="hidden-topic", name="Hidden Topic Name", status=status_value, description="HIDDEN-TOPIC-DESC"))
    _add(app, Series(slug="hidden-series", name="Hidden Series Name", status=status_value, description="HIDDEN-SERIES-DESC"))
    _assert_404_no_leak(client, "/topics/hidden-topic", "Hidden Topic Name", "HIDDEN-TOPIC-DESC")
    _assert_404_no_leak(client, "/series/hidden-series", "Hidden Series Name", "HIDDEN-SERIES-DESC")


def test_series_prerender_and_unpublished_sponsor_boundary(client, app):
    from app.models.people import Organization
    from app.models.taxonomy import Series

    with app.app_context():
        sponsor = Organization(slug="hidden-sponsor", name="Hidden Sponsor Org", status="draft", description=[])
        db.session.add(sponsor)
        db.session.flush()
        db.session.add(Series(slug="founder-stories", name="Founder Stories", status="published", subtitle="Builders in their words",
                              description="SERIES-DESCRIPTION-TEXT", sponsor_organization_id=sponsor.id))
        db.session.commit()
    status, html = _html(client, "/series/founder-stories")
    assert status == 200
    root = _assert_valid(html, "series", "Founder Stories", "SERIES-DESCRIPTION-TEXT", f"{SITE}/series/founder-stories")
    assert "Builders in their words" in root
    assert "Hidden Sponsor Org" not in html and "hidden-sponsor" not in html


# --- Directory ----------------------------------------------------------------------------------


def _org(app, slug, status="published", **fields):
    from app.models.people import Organization

    return _add(app, Organization(slug=slug, name=fields.pop("name", "Amani Studio"), status=status, description=[], **fields))


def _listing(app, org_id, status="published", **fields):
    from app.models.directory import DirectoryListing

    return _add(app, DirectoryListing(organization_id=org_id, status=status, listing_type="business",
                                      ownership_classification="women_owned", classification_provenance="self_attested",
                                      verification_status=fields.pop("verification_status", "unverified"), **fields))


def test_directory_prerender_and_private_boundary(client, app):
    from app.models.directory import DirectorySubmission

    org_id = _org(app, "amani-studio", industry="Design", location="Kigali", website="https://amani.example.com")
    listing_id = _listing(app, org_id, verification_status="verified", service_summary="DIRECTORY-SUMMARY-TEXT",
                          key_services=["Brand identity"], service_modes=["remote", "in_person"],
                          public_contact_email="hello@amani.example.com", public_contact_phone="+250 700 000 000",
                          verification_notes="PRIVATE-VERIFICATION-NOTE", rejection_reason="PRIVATE-REJECTION")
    _add(app, DirectorySubmission(reference="WSF-DIR-2026-000001", status="converted", business_name="Amani Studio",
                                  business_name_normalized="amani studio", listing_type="business",
                                  ownership_classification="women_owned", submitter_name="Private Submitter Name",
                                  submitter_email="submitter-private@example.com", resulting_listing_id=listing_id))
    status, html = _html(client, "/directory/amani-studio")
    assert status == 200
    root = _assert_valid(html, "directory", "Amani Studio", "DIRECTORY-SUMMARY-TEXT", f"{SITE}/directory/amani-studio",
                         "data-directory-structured-data")
    for text in ("Business", "Design", "Kigali", "Women-owned", "Verified by WSF", "Brand identity", "Remote, In person",
                 'href="mailto:hello@amani.example.com"', "+250 700 000 000", 'href="https://amani.example.com"'):
        assert text in root, text
    for secret in ("PRIVATE-VERIFICATION-NOTE", "PRIVATE-REJECTION", "Private Submitter Name", "submitter-private@example.com",
                   "WSF-DIR-2026-000001"):
        assert secret not in html, secret


def test_nonpublic_directory_listing_404(client, app):
    org_id = _org(app, "pending-studio", name="Pending Studio Name")
    _listing(app, org_id, status="pending", service_summary="PENDING-SUMMARY")
    _assert_404_no_leak(client, "/directory/pending-studio", "Pending Studio Name", "PENDING-SUMMARY")


# --- Product ---------------------------------------------------------------------------------------


def test_product_prerender_never_exposes_linked_resource_delivery(client, app):
    from app.models.commerce import Product, ProductCategory
    from app.models.resource import Resource, ResourcePurchase
    from app.models.user import User

    with app.app_context():
        resource = Resource(slug="linked-kit", name="Linked Kit", status="published", access_type="premium", price=1500, currency="KES",
                            file_url="https://files.example.com/SECRET-PRODUCT-FILE.pdf",
                            external_url="https://external.example.com/SECRET-PRODUCT-EXTERNAL",
                            protected_file_path="/srv/protected/SECRET-PRODUCT-PATH.pdf")
        category = ProductCategory(slug="guides", name="Guides")
        buyer = User(email="product-buyer@example.com", first_name="Product", last_name="Buyername", country_code="US", password_hash="x")
        db.session.add_all([resource, category, buyer])
        db.session.flush()
        db.session.add(ResourcePurchase(user_id=buyer.id, resource_id=resource.id, payment_reference="PRODUCT-PAY-REF-SECRET", status="active"))
        db.session.add(Product(slug="negotiation-workbook", name="Negotiation Workbook", status="active", type="digital",
                               short_description="Plan your next raise.", description=_body("PRODUCT-BODY-TEXT"),
                               price=1500, sale_price=1200, currency="KES", resource_id=resource.id, category_id=category.id,
                               purchase_url="https://pay.example.com/workbook", sku="INTERNAL-SKU-123",
                               shipping_notes="INTERNAL-SHIPPING-NOTE"))
        db.session.commit()
    status, html = _html(client, "/shop/negotiation-workbook")
    assert status == 200
    root = _assert_valid(html, "product", "Negotiation Workbook", "PRODUCT-BODY-TEXT", f"{SITE}/shop/negotiation-workbook",
                         "data-product-structured-data")
    for text in ("Guides", "Plan your next raise.", "KES 1,200.00", "KES 1,500.00", "Available", 'href="https://pay.example.com/workbook"'):
        assert text in root, text
    assert "INTERNAL-SKU-123" not in root and "INTERNAL-SHIPPING-NOTE" not in root
    for secret in ("SECRET-PRODUCT-FILE", "SECRET-PRODUCT-EXTERNAL", "SECRET-PRODUCT-PATH", "/srv/protected", "files.example.com",
                   "PRODUCT-PAY-REF-SECRET", "product-buyer@example.com", "Buyername"):
        assert secret not in html, secret


def test_hidden_price_product_shows_no_price(client, app):
    from app.models.commerce import Product

    _add(app, Product(slug="quiet-price", name="Quiet Price", status="active", description=_body("QUIET-BODY"), price=98765, price_visible=False))
    _, html = _html(client, "/shop/quiet-price")
    assert "98,765" not in html and "98765" not in html


@pytest.mark.parametrize("status_value", ["draft", "archived"])
def test_nonpublic_product_404(client, app, status_value):
    from app.models.commerce import Product

    _add(app, Product(slug="secret-product", name="Secret Product Name", status=status_value, description=_body("SECRET-PRODUCT-BODY")))
    _assert_404_no_leak(client, "/shop/secret-product", "Secret Product Name", "SECRET-PRODUCT-BODY")


# --- Newsletter (privacy critical) ----------------------------------------------------------------------


def test_newsletter_issue_prerender_and_subscriber_privacy(client, app):
    from app.models.article import Article
    from app.models.newsletter import NewsletterIssue, NewsletterSubscriber
    from app.models.people import Author

    with app.app_context():
        author = Author(slug="nl-author", name="NL", status="active")
        db.session.add(author)
        db.session.flush()
        db.session.add_all([
            Article(slug="live-story", title="Live Story", status="published", author_id=author.id, content=[]),
            Article(slug="pulled-story", title="Pulled Story", status="archived", author_id=author.id, content=[]),
            NewsletterSubscriber(email="subscriber-private@example.com", first_name="Subscriberfirstname",
                                 country_code="KE", status="active", unsubscribe_token="UNSUB-TOKEN-SECRET-123"),
            NewsletterIssue(
                slug="jan-digest", title="INTERNAL-EDITOR-TITLE", subject="January Digest", status="sent", issue_number=12,
                sent_at=datetime(2026, 1, 15, 9, 0, tzinfo=timezone.utc), preheader="Preheader text", summary="Summary text",
                audience_filter={"segment": "AUDIENCE-SECRET"}, provider="PROVIDER-SECRET",
                provider_campaign_id="CAMPAIGN-ID-SECRET", provider_message_id="MESSAGE-ID-SECRET",
                content=[
                    {"type": "paragraph", "text": "NEWSLETTER-BODY-TEXT"},
                    {"type": "articleCard", "articleSlug": "live-story", "title": "Live Story", "excerpt": "Read this."},
                    {"type": "articleCard", "articleSlug": "pulled-story", "title": "Pulled Story", "excerpt": ""},
                    {"type": "button", "label": "Join WSF Circle", "url": "https://womenshapingfutures.org/circle"},
                    {"type": "button", "label": "Bad button", "url": "javascript:alert(1)"},
                    {"type": "footerNote", "text": "You received this because you subscribed. {{unsubscribe_url}}"},
                ],
            ),
        ])
        db.session.commit()

    status, html = _html(client, "/newsletter/jan-digest")
    assert status == 200
    root = _assert_valid(html, "newsletter", "January Digest", "NEWSLETTER-BODY-TEXT", f"{SITE}/newsletter/jan-digest")
    assert "WSF Weekly #12" in root
    assert '<time datetime="2026-01-15T09:00:00+00:00">January 15, 2026</time>' in root
    assert 'href="/live-story"' in root and "Pulled Story" in root and 'href="/pulled-story"' not in root
    assert 'href="https://womenshapingfutures.org/circle"' in root
    assert "javascript:" not in root.lower()
    # The literal merge placeholder is static text — never evaluated or replaced with a token.
    assert "{{unsubscribe_url}}" in root
    for secret in ("subscriber-private@example.com", "Subscriberfirstname", "UNSUB-TOKEN-SECRET-123", "AUDIENCE-SECRET",
                   "PROVIDER-SECRET", "CAMPAIGN-ID-SECRET", "MESSAGE-ID-SECRET", "INTERNAL-EDITOR-TITLE"):
        assert secret not in html, secret


@pytest.mark.parametrize("status_value", ["draft", "scheduled", "archived"])
def test_unsent_newsletter_issue_404(client, app, status_value):
    from app.models.newsletter import NewsletterIssue

    _add(app, NewsletterIssue(slug="future-issue", title="T", subject="Secret Future Subject", status=status_value,
                              content=_body("SECRET-FUTURE-BODY")))
    _assert_404_no_leak(client, "/newsletter/future-issue", "Secret Future Subject", "SECRET-FUTURE-BODY")


# --- escaping / redirects / untouched families ----------------------------------------------------------------


def test_hostile_text_is_escaped(client, app):
    from app.models.taxonomy import Series

    _add(app, Series(slug="hostile-series", name="<script>alert(1)</script>Series", status="published",
                     subtitle="<img src=x onerror=alert(1)>", description="<a href=\"javascript:alert(2)\">x</a>"))
    _, html = _html(client, "/series/hostile-series")
    root = _root(html)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;Series" in root
    assert "&lt;img src=x onerror=alert(1)&gt;" in root
    assert "<script" not in root and "<img" not in root
    assert not re.search(r"<[a-z][^>]*\son[a-z]+\s*=", root, re.IGNORECASE)
    assert not re.search(r"""href\s*=\s*["']?javascript:""", root, re.IGNORECASE)


@pytest.mark.parametrize("entity_type,prefix,make", [
    ("author", "authors", lambda: __import__("app.models.people", fromlist=["Author"]).Author(slug="new-author", name="New Author", status="active", bio=_body("NEW-AUTHOR-BIO"))),
    ("topic", "topics", lambda: __import__("app.models.taxonomy", fromlist=["Topic"]).Topic(slug="new-author", name="New Topic", status="published", description="NEW-TOPIC-DESC")),
    ("series", "series", lambda: __import__("app.models.taxonomy", fromlist=["Series"]).Series(slug="new-author", name="New Series", status="published", description="NEW-SERIES-DESC")),
])
def test_entity_redirects_still_301_without_body(client, app, entity_type, prefix, make):
    from app.models.entity_redirect import EntityRedirect

    _add(app, make())
    _add(app, EntityRedirect(entity_type=entity_type, from_slug="old-slug", to_slug="new-author"))
    resp = client.get(f"/{prefix}/old-slug")
    assert resp.status_code == 301
    assert resp.headers["Location"].endswith(f"/{prefix}/new-author")
    body = resp.get_data(as_text=True)
    assert "data-wsf-prerender" not in body
    for text in ("NEW-AUTHOR-BIO", "NEW-TOPIC-DESC", "NEW-SERIES-DESC"):
        assert text not in body
