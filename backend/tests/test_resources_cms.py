import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "resources-manager@example.com",
    "password": "supersecret1",
    "first_name": "Naliaka",
    "last_name": "Wafula",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "resources-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
}


def _register_with_role(client, app, payload, role_name):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        role = Role.query.filter_by(name=role_name).first()
        user.roles.append(role)
        db.session.commit()

    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def manager_token(client, app):
    return _register_with_role(client, app, MANAGER_PAYLOAD, "resources_manager")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_topic(app, slug="careers", name="Career"):
    from app.extensions import db
    from app.models.taxonomy import Topic

    with app.app_context():
        topic = Topic.query.filter_by(slug=slug).first()
        if topic is None:
            topic = Topic(slug=slug, name=name)
            db.session.add(topic)
            db.session.commit()
        return topic.slug


def _make_author(app, slug="amara-otieno", name="Amara Otieno"):
    from app.extensions import db
    from app.models.people import Author

    with app.app_context():
        author = Author.query.filter_by(slug=slug).first()
        if author is None:
            author = Author(slug=slug, name=name)
            db.session.add(author)
            db.session.commit()
        return author.slug


def _base_payload(**overrides):
    payload = {
        "name": "The Career Reset Workbook",
        "shortDescription": "A structured workbook for planning your next career move.",
        "description": [{"type": "paragraph", "text": "Forty pages of prompts, worksheets, and planning tools."}],
        "type": "Workbook",
        "accessType": "direct_download",
        "fileUrl": "https://cdn.example.com/career-reset-workbook.pdf",
        "fileFormat": "PDF",
        "price": 0,
        "currency": "USD",
        "status": "published",
    }
    payload.update(overrides)
    return payload


def test_resource_create_requires_permission(client):
    resp = client.post("/api/v1/resources", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_resource_create_requires_permission_even_with_account(client, no_permission_token):
    resp = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_resource_create_update_and_slug_uniqueness(client, manager_token):
    create = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(manager_token))
    assert create.status_code == 201
    resource = create.get_json()["data"]
    assert resource["slug"]

    dupe = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(manager_token))
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != resource["slug"]

    update = client.put(
        f"/api/v1/resources/{resource['slug']}",
        json=_base_payload(name="The Career Reset Workbook, Revised"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["name"] == "The Career Reset Workbook, Revised"


def test_resource_explicit_slug_conflict_rejected(client, manager_token):
    first = client.post(
        "/api/v1/resources", json=_base_payload(slug="my-guide"), headers=auth_headers(manager_token)
    )
    assert first.status_code == 201

    conflict = client.post(
        "/api/v1/resources", json=_base_payload(slug="my-guide"), headers=auth_headers(manager_token)
    )
    assert conflict.status_code == 409


def test_draft_resource_not_publicly_visible(client, manager_token):
    resp = client.post(
        "/api/v1/resources", json=_base_payload(status="draft"), headers=auth_headers(manager_token)
    )
    slug = resp.get_json()["data"]["slug"]

    anon = client.get(f"/api/v1/resources/{slug}")
    assert anon.status_code == 404

    as_editor = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
    assert as_editor.status_code == 200
    assert as_editor.get_json()["data"]["status"] == "draft"


def test_draft_resource_excluded_from_public_listing(client, manager_token):
    client.post("/api/v1/resources", json=_base_payload(status="draft", name="Hidden Draft"), headers=auth_headers(manager_token))
    client.post("/api/v1/resources", json=_base_payload(status="published", name="Visible One"), headers=auth_headers(manager_token))

    listing = client.get("/api/v1/resources")
    names = {r["name"] for r in listing.get_json()["data"]}
    assert "Visible One" in names
    assert "Hidden Draft" not in names


def test_published_resource_publicly_visible(client, manager_token):
    resp = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(manager_token))
    slug = resp.get_json()["data"]["slug"]

    anon = client.get(f"/api/v1/resources/{slug}")
    assert anon.status_code == 200
    assert anon.get_json()["data"]["status"] == "published"


def test_resource_publish_requires_description(client, manager_token):
    resp = client.post(
        "/api/v1/resources", json=_base_payload(description=[], status="published"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_resource_invalid_access_settings_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/resources",
        json=_base_payload(accessType="external_link", externalUrl=None, fileUrl=None),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_resource_invalid_file_format_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/resources", json=_base_payload(fileFormat="EXE"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_resource_topic_relationship(client, app, manager_token):
    topic_slug = _make_topic(app)
    resp = client.post(
        "/api/v1/resources", json=_base_payload(topicSlugs=[topic_slug]), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert [t["slug"] for t in data["topics"]] == [topic_slug]


def test_resource_unknown_topic_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/resources", json=_base_payload(topicSlugs=["does-not-exist"]), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 404


def test_resource_author_relationship(client, app, manager_token):
    author_slug = _make_author(app)
    resp = client.post(
        "/api/v1/resources", json=_base_payload(authorSlug=author_slug), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["author"]["slug"] == author_slug
    assert data["author_id"] is not None


def test_resource_author_name_fallback_without_author(client, manager_token):
    resp = client.post(
        "/api/v1/resources", json=_base_payload(authorName="WSF Editorial Team"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["author"] is None
    assert data["author_name"] == "WSF Editorial Team"


def test_resource_filtering_by_topic_type_and_featured(client, app, manager_token):
    topic_slug = _make_topic(app, slug="leadership", name="Leadership")
    client.post(
        "/api/v1/resources",
        json=_base_payload(name="Leadership Workbook", topicSlugs=[topic_slug], type="Workbook", featured=True),
        headers=auth_headers(manager_token),
    )
    client.post(
        "/api/v1/resources", json=_base_payload(name="Unrelated Checklist", type="Checklist"), headers=auth_headers(manager_token)
    )

    by_topic = client.get(f"/api/v1/resources?topic={topic_slug}")
    names = {r["name"] for r in by_topic.get_json()["data"]}
    assert names == {"Leadership Workbook"}

    by_type = client.get("/api/v1/resources?type=Checklist")
    names = {r["name"] for r in by_type.get_json()["data"]}
    assert names == {"Unrelated Checklist"}

    featured = client.get("/api/v1/resources?featured=true")
    names = {r["name"] for r in featured.get_json()["data"]}
    assert "Leadership Workbook" in names
    assert "Unrelated Checklist" not in names


def test_resource_search_by_keyword(client, manager_token):
    client.post("/api/v1/resources", json=_base_payload(name="Salary Negotiation Checklist"), headers=auth_headers(manager_token))
    client.post("/api/v1/resources", json=_base_payload(name="Interview Preparation Guide"), headers=auth_headers(manager_token))

    resp = client.get("/api/v1/resources?q=Salary")
    names = {r["name"] for r in resp.get_json()["data"]}
    assert names == {"Salary Negotiation Checklist"}


def test_resource_pagination(client, manager_token):
    for i in range(5):
        client.post(
            "/api/v1/resources", json=_base_payload(name=f"Resource {i}"), headers=auth_headers(manager_token)
        )

    resp = client.get("/api/v1/resources?page=1&per_page=2")
    body = resp.get_json()
    assert len(body["data"]) == 2
    assert body["meta"]["total"] == 5
    assert body["meta"]["total_pages"] == 3


def test_free_resource_direct_download_access(client, manager_token):
    resp = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(manager_token))
    slug = resp.get_json()["data"]["slug"]
    assert resp.get_json()["data"]["is_free"] is True

    access = client.post(f"/api/v1/resources/{slug}/access")
    assert access.status_code == 200
    assert access.get_json()["data"]["url"]

    fetched = client.get(f"/api/v1/resources/{slug}")
    assert fetched.get_json()["data"]["download_count"] == 1


def test_email_gated_resource_creates_lead_without_forcing_newsletter(client, app, manager_token):
    resp = client.post(
        "/api/v1/resources",
        json=_base_payload(name="LinkedIn Personal Brand Guide", accessType="email_gate"),
        headers=auth_headers(manager_token),
    )
    slug = resp.get_json()["data"]["slug"]
    assert resp.get_json()["data"]["requires_email"] is True

    no_email = client.post(f"/api/v1/resources/{slug}/access", json={})
    assert no_email.status_code == 422

    access = client.post(
        f"/api/v1/resources/{slug}/access",
        json={"email": "reader@example.com", "firstName": "Jordan", "newsletterConsent": False},
    )
    assert access.status_code == 201
    assert access.get_json()["data"]["url"]

    with app.app_context():
        from app.models.newsletter import NewsletterSubscriber
        from app.models.resource import ResourceLead

        assert ResourceLead.query.filter_by(email="reader@example.com").first() is not None
        assert NewsletterSubscriber.query.filter_by(email="reader@example.com").first() is None


def test_email_gated_resource_consent_subscribes_to_newsletter(client, app, manager_token):
    resp = client.post(
        "/api/v1/resources", json=_base_payload(accessType="email_gate"), headers=auth_headers(manager_token)
    )
    slug = resp.get_json()["data"]["slug"]

    client.post(
        f"/api/v1/resources/{slug}/access",
        json={"email": "consenting@example.com", "newsletterConsent": True},
    )

    with app.app_context():
        from app.models.newsletter import NewsletterSubscriber

        subscriber = NewsletterSubscriber.query.filter_by(email="consenting@example.com").first()
        assert subscriber is not None
        assert subscriber.status == "active"


def test_premium_resource_access_not_available(client, manager_token):
    resp = client.post(
        "/api/v1/resources",
        json=_base_payload(
            name="Women Founders Business Planning Toolkit", accessType="premium", price=4900, fileUrl=None
        ),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["is_free"] is False

    access = client.post(f"/api/v1/resources/{data['slug']}/access")
    assert access.status_code == 403
    assert access.get_json()["error"]["code"] == "premium_unavailable"


def test_external_link_resource_access(client, manager_token):
    resp = client.post(
        "/api/v1/resources",
        json=_base_payload(accessType="external_link", fileUrl=None, externalUrl="https://example.com/external-resource"),
        headers=auth_headers(manager_token),
    )
    slug = resp.get_json()["data"]["slug"]

    access = client.post(f"/api/v1/resources/{slug}/access")
    assert access.status_code == 200
    assert access.get_json()["data"]["url"] == "https://example.com/external-resource"


def test_resource_safe_delete_blocked_when_linked_to_product(client, app, manager_token):
    created = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(manager_token))
    resource = created.get_json()["data"]

    with app.app_context():
        from app.extensions import db
        from app.models.commerce import Product
        from app.services.slugs import generate_unique_slug

        product = Product(name="Wraps the resource", resource_id=resource["id"], price=0, currency="USD")
        product.slug = generate_unique_slug(Product, product.name)
        db.session.add(product)
        db.session.commit()

    delete_resp = client.delete(f"/api/v1/resources/{resource['slug']}", headers=auth_headers(manager_token))
    assert delete_resp.status_code == 409


def test_resource_delete_allowed_when_unreferenced(client, manager_token):
    created = client.post("/api/v1/resources", json=_base_payload(), headers=auth_headers(manager_token))
    slug = created.get_json()["data"]["slug"]

    delete_resp = client.delete(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
    assert delete_resp.status_code == 200

    fetched = client.get(f"/api/v1/resources/{slug}")
    assert fetched.status_code == 404
