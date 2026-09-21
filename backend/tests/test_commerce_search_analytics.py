import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "shopadmin@example.com",
    "password": "supersecret1",
    "first_name": "Shop",
    "last_name": "Admin",
}


@pytest.fixture()
def admin_token(client, app):
    from app.extensions import db
    from app.models.user import Role, User

    client.post("/api/v1/auth/register", json=ADMIN_PAYLOAD)
    with app.app_context():
        user = User.query.filter_by(email=ADMIN_PAYLOAD["email"]).first()
        role = Role.query.filter_by(name="admin").first()
        user.roles.append(role)
        db.session.commit()

    login = client.post(
        "/api/v1/auth/login", json={"email": ADMIN_PAYLOAD["email"], "password": ADMIN_PAYLOAD["password"]}
    )
    return login.get_json()["data"]["access_token"]


def test_product_create_and_guest_checkout(client, admin_token):
    product = client.post(
        "/api/v1/products",
        json={"name": "The Founder's CV Template", "price": 12, "currency": "USD"},
        headers=auth_headers(admin_token),
    )
    assert product.status_code == 201
    slug = product.get_json()["data"]["slug"]

    order = client.post(
        "/api/v1/orders",
        json={"email": "buyer@example.com", "items": [{"productSlug": slug, "quantity": 2}]},
    )
    assert order.status_code == 201
    body = order.get_json()["data"]
    assert body["total_amount"] == 24
    assert body["status"] == "pending_payment"
    order_uuid = body["uuid"]

    fetched = client.get(f"/api/v1/orders/{order_uuid}")
    assert fetched.status_code == 200

    denied_status_change = client.patch(f"/api/v1/orders/{order_uuid}/status", json={"status": "paid"})
    assert denied_status_change.status_code == 401  # no token at all

    marked_paid = client.patch(
        f"/api/v1/orders/{order_uuid}/status",
        json={"status": "paid", "paymentProvider": "mpesa", "paymentReference": "ABC123"},
        headers=auth_headers(admin_token),
    )
    assert marked_paid.status_code == 200
    assert marked_paid.get_json()["data"]["status"] == "paid"


def test_order_rejects_unknown_product(client):
    resp = client.post(
        "/api/v1/orders", json={"email": "buyer@example.com", "items": [{"productSlug": "does-not-exist"}]}
    )
    assert resp.status_code == 404


def test_search_finds_articles_and_people_by_type(client, admin_token):
    author = client.post(
        "/api/v1/authors", json={"name": "Amara Otieno"}, headers=auth_headers(admin_token)
    )
    author_slug = author.get_json()["data"]["slug"]
    client.post(
        "/api/v1/articles",
        json={
            "title": "How Women Are Redefining Leadership",
            "excerpt": "A look at the shift.",
            "authorSlug": author_slug,
            "status": "published",
            "content": [],
        },
        headers=auth_headers(admin_token),
    )
    client.post("/api/v1/people", json={"name": "Naliaka Wafula"}, headers=auth_headers(admin_token))

    everything = client.get("/api/v1/search?q=leadership")
    assert everything.status_code == 200
    types = {r["resultType"] for r in everything.get_json()["data"]["results"]}
    assert "Article" in types

    people_only = client.get("/api/v1/search?q=Naliaka&type=people")
    assert people_only.status_code == 200
    results = people_only.get_json()["data"]["results"]
    assert len(results) == 1
    assert results[0]["resultType"] == "Person"

    no_match = client.get("/api/v1/search?q=zzzznomatch")
    assert no_match.status_code == 200
    assert no_match.get_json()["data"]["results"] == []

    empty_query = client.get("/api/v1/search?q=")
    assert empty_query.status_code == 200
    assert empty_query.get_json()["data"]["results"] == []


def test_analytics_ingestion_and_summary(client, admin_token):
    for _ in range(3):
        resp = client.post(
            "/api/v1/analytics/events",
            json={"eventName": "article_view", "entityType": "Article", "entityId": "42"},
        )
        assert resp.status_code == 201

    denied = client.post("/api/v1/auth/register", json={
        "email": "notanalyst@example.com", "password": "supersecret1", "first_name": "N", "last_name": "A",
    })
    login = client.post(
        "/api/v1/auth/login", json={"email": "notanalyst@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]
    denied_resp = client.get("/api/v1/analytics/summary", headers=auth_headers(token))
    assert denied_resp.status_code == 403

    summary = client.get("/api/v1/analytics/summary", headers=auth_headers(admin_token))
    assert summary.status_code == 200
    data = summary.get_json()["data"]
    assert data[0]["eventName"] == "article_view"
    assert data[0]["count"] == 3
