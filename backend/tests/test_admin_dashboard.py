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
def partnerships_manager_token(client, app):
    payload = {
        "email": "pm-analytics@example.com",
        "password": "supersecret1",
        "first_name": "Partnerships",
        "last_name": "Manager",
    }
    return _register_with_role(client, app, payload, "partnerships_manager")


@pytest.fixture()
def analyst_token(client, app):
    # "analyst" holds analytics.view (and analytics.export) — the actual
    # permission every Analytics endpoint below checks, unlike
    # partnerships_manager's analytics.commercial.
    payload = {
        "email": "analyst-analytics@example.com",
        "password": "supersecret1",
        "first_name": "An",
        "last_name": "Alyst",
    }
    return _register_with_role(client, app, payload, "analyst")


class TestAnalyticsCommercialPermissionBoundary:
    """analytics.commercial (held by partnerships_manager) is reserved for
    a commercial-analytics view that does not exist yet — every endpoint
    the Analytics admin page actually calls checks analytics.view only
    (see app/api/v1/admin.py's AdminDashboardResource and
    app/api/v1/analytics.py). This documents that truthfully: a role
    holding analytics.commercial but not analytics.view gets a real 403
    from every one of those endpoints, which is exactly why the frontend
    Analytics nav/route gate (constants/adminNav.js) no longer lists
    analytics.commercial as an alternate way in — see that file's comment
    and app/services/rbac.py's comment on the partnerships_manager role.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/admin/dashboard",
            "/api/v1/analytics/summary",
            "/api/v1/analytics/traffic-sources",
            "/api/v1/analytics/subscriber-growth",
        ],
    )
    def test_partnerships_manager_is_rejected_by_every_analytics_endpoint(self, client, partnerships_manager_token, path):
        resp = client.get(path, headers=auth_headers(partnerships_manager_token))
        assert resp.status_code == 403

    def test_partnerships_manager_retains_its_own_legitimate_permissions(self, client, partnerships_manager_token):
        # The fix must never remove partnerships.manage/directory.manage —
        # only the misleading route to a page that always 403s.
        resp = client.get("/api/v1/partnerships/inquiries", headers=auth_headers(partnerships_manager_token))
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "path",
        [
            "/api/v1/admin/dashboard",
            "/api/v1/analytics/summary",
            "/api/v1/analytics/traffic-sources",
            "/api/v1/analytics/subscriber-growth",
        ],
    )
    def test_a_role_holding_the_real_permission_still_has_access(self, client, analyst_token, path):
        resp = client.get(path, headers=auth_headers(analyst_token))
        assert resp.status_code == 200
