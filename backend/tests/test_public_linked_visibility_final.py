"""GEO final public-visibility hardening — Sponsors, Products, Directory.

Companion to test_public_linked_visibility.py: the anonymous Job, Article,
Product, Directory and sponsor-placement payloads (and the raw HTML built
from them) never reveal an internal or non-public linked Sponsor
campaign, Resource, DirectoryCategory or Organization; staff/CMS
responses keep the full relation.
"""
import json
import os
from datetime import date, timedelta

import pytest

from app.extensions import db
from tests.conftest import auth_headers

FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


@pytest.fixture(autouse=True)
def _fixture_index(app):
    app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH


@pytest.fixture()
def staff(client, app):
    from app.models.user import Role, User

    payload = {"email": "final-visibility@example.com", "password": "supersecret1", "first_name": "Fin",
               "last_name": "Al", "country_code": "US"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="super_admin").first())
        db.session.commit()
    token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
    return auth_headers(token)


def _add(app, *objs):
    with app.app_context():
        db.session.add_all(objs)
        db.session.commit()
        return [o.id for o in objs]


def _get(client, path, headers=None):
    resp = client.get(path, headers=headers or {})
    assert resp.status_code == 200, (path, resp.status_code)
    return resp.get_json()["data"], resp.get_data(as_text=True)


def _raw(client, path):
    resp = client.get(path)
    assert resp.status_code == 200, path
    return resp.get_data(as_text=True)


def _orgs(app):
    from app.models.people import Organization

    return dict(zip(("pub", "draft"), _add(
        app,
        Organization(slug="sponsor-pub-org", name="Sponsor Public Org", status="published", description=[]),
        Organization(slug="secret-sponsor-org-slug", name="Secret Sponsor Draft Org", status="draft", description=[]),
    )))


def _sponsor(app, org_id, campaign, **fields):
    from app.models.commerce import Sponsor

    defaults = dict(status="active", public_visible=True, tier="SECRET-TIER-GOLD", internal_reference="SECRET-INTERNAL-REF",
                    commercial_notes="SECRET-COMMERCIAL-NOTES", internal_notes="SECRET-INTERNAL-NOTES", estimated_value=999999,
                    currency="KES", disclosure_label="Sponsored by")
    defaults.update(fields)
    return _add(app, Sponsor(campaign_name=campaign, organization_id=org_id, **defaults))[0]


SPONSOR_SECRETS = ("SECRET-TIER-GOLD", "SECRET-INTERNAL-REF", "SECRET-COMMERCIAL-NOTES", "SECRET-INTERNAL-NOTES", "999999")


def _assert_absent(text, *needles):
    for needle in needles:
        assert needle not in text, needle


# --- Job Sponsor ----------------------------------------------------------------------------


INELIGIBLE = [
    dict(status="draft"),
    dict(status="paused"),
    dict(status="active", public_visible=False),
    dict(status="active", ends_at=date.today() - timedelta(days=1)),
    dict(status="active", starts_at=date.today() + timedelta(days=10)),
]


@pytest.mark.parametrize("sponsor_fields", INELIGIBLE + [dict(status="active")])
def test_job_public_payload_never_carries_sponsor_record(client, app, staff, sponsor_fields):
    from app.models.opportunity import Job
    from app.services.saved_items import fetch_public_content

    orgs = _orgs(app)
    sponsor_id = _sponsor(app, orgs["draft"], "SECRET-JOB-CAMPAIGN", **sponsor_fields)
    job_id = _add(app, Job(slug="sponsored-role", title="Sponsored Role", company_name="Kaziwave", status="published",
                           sponsored=True, sponsor_id=sponsor_id))[0]

    data, text = _get(client, "/api/v1/jobs/sponsored-role")
    assert "sponsor" not in data and "sponsor_id" not in data
    assert data["sponsored"] is True and data["company_name"] == "Kaziwave"
    _assert_absent(text, "SECRET-JOB-CAMPAIGN", "secret-sponsor-org-slug", *SPONSOR_SECRETS)
    _, list_text = _get(client, "/api/v1/jobs")
    _assert_absent(list_text, "SECRET-JOB-CAMPAIGN", "secret-sponsor-org-slug", *SPONSOR_SECRETS)
    html = _raw(client, "/jobs/sponsored-role")
    _assert_absent(html, "SECRET-JOB-CAMPAIGN", "secret-sponsor-org-slug", *SPONSOR_SECRETS)
    with app.app_context():
        saved = json.dumps(fetch_public_content("job", job_id), default=str)
    assert '"sponsor_id"' not in saved and '"sponsor":' not in saved
    _assert_absent(saved, *SPONSOR_SECRETS)

    # The staff editor still gets the Sponsor selection.
    staff_data, _ = _get(client, "/api/v1/jobs/sponsored-role", staff)
    assert staff_data["sponsor_id"] == sponsor_id


# --- Article Sponsor --------------------------------------------------------------------------


def _article(app, sponsor_id, **fields):
    from app.models.article import Article
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug="final-author").first() or Author(slug="final-author", name="Final Author", status="active")
        db.session.add(author)
        db.session.flush()
        db.session.add(Article(slug=fields.pop("slug", "sponsored-story"), title="Sponsored Story", status="published",
                               author_id=author.id, content=[{"type": "paragraph", "text": "Body."}],
                               is_sponsored=True, sponsor_id=sponsor_id, **fields))
        db.session.commit()


@pytest.mark.parametrize("sponsor_fields", INELIGIBLE)
def test_ineligible_article_sponsor_never_public(client, app, staff, sponsor_fields):
    orgs = _orgs(app)
    sponsor_id = _sponsor(app, orgs["pub"], "SECRET-ARTICLE-CAMPAIGN", public_name_override="Secret Ineligible Public Name", **sponsor_fields)
    _article(app, sponsor_id, sponsor={"name": "Freeform Sponsor", "disclosure": "Freeform disclosure text"})

    data, text = _get(client, "/api/v1/articles/sponsored-story")
    assert data["sponsorRecord"] is None and "sponsor_id" not in data
    assert data["sponsor"] == {"name": "Freeform Sponsor", "disclosure": "Freeform disclosure text"}
    _assert_absent(text, "SECRET-ARTICLE-CAMPAIGN", "Secret Ineligible Public Name", *SPONSOR_SECRETS)
    html = _raw(client, "/sponsored-story")  # API-identical bootstrap + prerender + JSON-LD
    _assert_absent(html, "SECRET-ARTICLE-CAMPAIGN", "Secret Ineligible Public Name", *SPONSOR_SECRETS)
    assert "Freeform disclosure text" in html
    staff_data, _ = _get(client, "/api/v1/articles/sponsored-story", staff)
    assert staff_data["sponsorRecord"]["campaign_name"] == "SECRET-ARTICLE-CAMPAIGN"


def test_eligible_article_sponsor_minimal_shape_and_org_rule(client, app):
    orgs = _orgs(app)
    sponsor_pub = _sponsor(app, orgs["pub"], "SECRET-CAMPAIGN-A", public_name_override="Acme Partners")
    sponsor_draft_org = _sponsor(app, orgs["draft"], "SECRET-CAMPAIGN-B", public_name_override="Beta Partners")
    _article(app, sponsor_pub, slug="story-a")
    _article(app, sponsor_draft_org, slug="story-b")

    data, text = _get(client, "/api/v1/articles/story-a")
    assert data["sponsorRecord"] == {
        "publicName": "Acme Partners", "disclosure_label": "Sponsored by",
        "organization": {"slug": "sponsor-pub-org", "name": "Sponsor Public Org"},
    }
    _assert_absent(text, "SECRET-CAMPAIGN-A", *SPONSOR_SECRETS)
    assert "Acme Partners" in _raw(client, "/story-a")

    data, text = _get(client, "/api/v1/articles/story-b")
    # The eligible campaign stays public by its own public name; its
    # unpublished Organization profile does not.
    assert data["sponsorRecord"]["publicName"] == "Beta Partners" and data["sponsorRecord"]["organization"] is None
    html = _raw(client, "/story-b")
    _assert_absent(text + html, "secret-sponsor-org-slug", "Secret Sponsor Draft Org", "SECRET-CAMPAIGN-B", *SPONSOR_SECRETS)
    assert "Beta Partners" in html


# --- Product → Resource -------------------------------------------------------------------------


@pytest.mark.parametrize("resource_status", ["published", "draft", "archived"])
def test_product_never_exposes_linked_resource_identity(client, app, staff, resource_status):
    from app.models.commerce import Product
    from app.models.resource import Resource

    resource_id = _add(app, Resource(slug="secret-linked-resource-slug", name="Secret Linked Resource", status=resource_status,
                                     access_type="premium", price=100, currency="KES",
                                     file_url="https://files.example.com/SECRET-DELIVERY.pdf"))[0]
    _add(app, Product(slug="workbook", name="Workbook", status="active", description=[], price=100, resource_id=resource_id))

    data, text = _get(client, "/api/v1/products/workbook")
    assert "resource" not in data and "resource_id" not in data
    _, list_text = _get(client, "/api/v1/products")
    html = _raw(client, "/shop/workbook")
    _assert_absent(text + list_text + html, "secret-linked-resource-slug", "Secret Linked Resource", "SECRET-DELIVERY")
    staff_data, _ = _get(client, "/api/v1/products/workbook", staff)
    assert staff_data["resource_id"] == resource_id and staff_data["resource"]["slug"] == "secret-linked-resource-slug"


# --- Directory categories -------------------------------------------------------------------------


def test_directory_public_categories_and_filter(client, app, staff):
    from app.models.directory import DirectoryCategory, DirectoryListing
    from app.models.people import Organization

    with app.app_context():
        org = Organization(slug="amani-studio", name="Amani Studio", status="published", description=[])
        cats = [DirectoryCategory(slug="design", name="Design", status="published"),
                DirectoryCategory(slug="secret-draft-category", name="Secret Draft Category", status="draft"),
                DirectoryCategory(slug="secret-archived-category", name="Secret Archived Category", status="archived")]
        db.session.add_all([org, *cats])
        db.session.flush()
        listing = DirectoryListing(organization_id=org.id, status="published", listing_type="business",
                                   ownership_classification="women_owned", classification_provenance="self_attested",
                                   verification_status="unverified")
        listing.categories = cats
        db.session.add(listing)
        db.session.commit()
        listing_id = listing.id

    secrets = ("secret-draft-category", "Secret Draft Category", "secret-archived-category", "Secret Archived Category")
    data, text = _get(client, "/api/v1/directory/amani-studio")
    assert [c["slug"] for c in data["categories"]] == ["design"]
    items, list_text = _get(client, "/api/v1/directory")
    assert [c["slug"] for c in items[0]["categories"]] == ["design"]
    html = _raw(client, "/directory/amani-studio")
    assert "Design" in html
    _assert_absent(text + list_text + html, *secrets)
    categories, _ = _get(client, "/api/v1/directory/categories")
    assert [c["slug"] for c in categories] == ["design"]

    # A non-published category slug can't be used as a public filter.
    assert _get(client, "/api/v1/directory?category=secret-draft-category")[0] == []
    assert len(_get(client, "/api/v1/directory?category=design")[0]) == 1

    staff_data, _ = _get(client, f"/api/v1/directory/admin/listings/{listing_id}", staff)
    assert sorted(c["slug"] for c in staff_data["categories"]) == ["design", "secret-archived-category", "secret-draft-category"]


# --- Public sponsor placements (audit fix) ------------------------------------------------------------


def test_public_sponsor_placement_hides_unpublished_org_profile(client, app):
    from app.models.commerce import SponsorPlacement
    from app.models.media import Media
    from app.models.people import Organization

    with app.app_context():
        logo = Media(original_filename="o.png", stored_filename="o.png", file_path="/tmp/o.png",
                     public_url="/media/originals/secret-org-logo.png", mime_type="image/png")
        db.session.add(logo)
        db.session.flush()
        org = Organization(slug="secret-placement-org", name="Secret Placement Org", status="draft", description=[], logo_media_id=logo.id)
        db.session.add(org)
        db.session.commit()
        org_id = org.id
    sponsor_id = _sponsor(app, org_id, "Placement Campaign", public_name_override="Visible Campaign Name")
    _add(app, SponsorPlacement(sponsor_id=sponsor_id, placement_key="homepage_featured"))

    data, text = _get(client, "/api/v1/sponsors/public?placement=homepage_featured")
    assert len(data) == 1 and data[0]["publicName"] == "Visible Campaign Name"  # campaign itself stays
    assert data[0]["organization"] is None
    _assert_absent(text, "secret-placement-org", "Secret Placement Org")
    # The campaign logo (falling back to the Organization's logo) is part of
    # the campaign's own presentation and is unchanged — see
    # test_sponsors_cms.py::test_logo_falls_back_to_organization_logo.
    assert data[0]["logo"]["public_url"] == "/media/originals/secret-org-logo.png"
