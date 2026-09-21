import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "dashadmin@example.com",
    "password": "supersecret1",
    "first_name": "Dash",
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


def test_admin_dashboard_reflects_real_counts(client, admin_token):
    author = client.post(
        "/api/v1/authors",
        json={"name": "Dash Writer"},
        headers=auth_headers(admin_token),
    )
    author_slug = author.get_json()["data"]["slug"]

    client.post(
        "/api/v1/articles",
        json={"title": "A Draft Article", "authorSlug": author_slug, "status": "draft"},
        headers=auth_headers(admin_token),
    )
    published = client.post(
        "/api/v1/articles",
        json={
            "title": "A Published Article",
            "authorSlug": author_slug,
            "status": "published",
            "content": [{"type": "paragraph", "text": "Body text."}],
        },
        headers=auth_headers(admin_token),
    )
    assert published.status_code == 201

    dashboard = client.get("/api/v1/admin/dashboard", headers=auth_headers(admin_token))
    assert dashboard.status_code == 200
    data = dashboard.get_json()["data"]
    assert data["publishedArticles"] >= 1
    assert data["drafts"] >= 1
    assert "pageViewsTrend" in data
    assert len(data["pageViewsTrend"]) == 6
    assert "topArticlesThisMonth" in data


def test_admin_article_list_includes_all_statuses(client, admin_token):
    author = client.post("/api/v1/authors", json={"name": "Pipeline Writer"}, headers=auth_headers(admin_token))
    author_slug = author.get_json()["data"]["slug"]

    client.post(
        "/api/v1/articles",
        json={"title": "Pipeline Draft", "authorSlug": author_slug, "status": "draft"},
        headers=auth_headers(admin_token),
    )

    public_list = client.get("/api/v1/articles")
    assert not any(a["title"] == "Pipeline Draft" for a in public_list.get_json()["data"])

    admin_list = client.get("/api/v1/admin/articles", headers=auth_headers(admin_token))
    assert admin_list.status_code == 200
    assert any(a["title"] == "Pipeline Draft" for a in admin_list.get_json()["data"])

    filtered = client.get("/api/v1/admin/articles?status=draft", headers=auth_headers(admin_token))
    assert all(a["status"] == "draft" for a in filtered.get_json()["data"])


def test_admin_article_list_requires_permission(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "plainreader@example.com", "password": "supersecret1", "first_name": "P", "last_name": "R"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "plainreader@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.get("/api/v1/admin/articles", headers=auth_headers(token))
    assert resp.status_code == 403


def test_analytics_traffic_sources_and_subscriber_growth(client, admin_token):
    client.post("/api/v1/analytics/events", json={"eventName": "article_view", "acquisition": {"source": "linkedin"}})
    client.post("/api/v1/analytics/events", json={"eventName": "article_view", "acquisition": {"source": "linkedin"}})
    client.post("/api/v1/analytics/events", json={"eventName": "resource_download_click"})

    sources = client.get("/api/v1/analytics/traffic-sources", headers=auth_headers(admin_token))
    assert sources.status_code == 200
    names = {row["name"] for row in sources.get_json()["data"]}
    assert "linkedin" in names

    client.post("/api/v1/newsletter/subscribe", json={"email": "growth@example.com"})
    growth = client.get("/api/v1/analytics/subscriber-growth", headers=auth_headers(admin_token))
    assert growth.status_code == 200
    assert len(growth.get_json()["data"]) == 6
    assert sum(row["subscribers"] for row in growth.get_json()["data"]) >= 1
