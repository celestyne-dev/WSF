"""Analytics Dashboard / Reporting tests — see app/services/analytics_reports.py
and app/api/v1/analytics.py. Covers ingestion validation, date-range
handling, real-data aggregation for every report section, RBAC
(analytics.view/.commercial/.export), CTR semantics, multi-currency
handling, deleted-entity resilience, and privacy (no member/mentee/
subscriber identity ever appears in an aggregate response).
"""
from datetime import date

import pytest

from app.extensions import db

from tests.conftest import auth_headers


def _register_with_role(client, app, email, role_name):
    from app.models.user import Role, User

    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "supersecret1", "first_name": "T", "last_name": "U"},
    )
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        role = Role.query.filter_by(name=role_name).first()
        if role:
            user.roles.append(role)
            db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "supersecret1"})
    return login.get_json()["data"]["access_token"]


def _track(client, event_name, **kwargs):
    payload = {"eventName": event_name}
    payload.update(kwargs)
    return client.post("/api/v1/analytics/events", json=payload)


class TestIngestionValidation:
    def test_unknown_event_name_rejected(self, client):
        resp = _track(client, "totally_made_up_event")
        assert resp.status_code == 422

    def test_known_event_name_accepted(self, client):
        resp = _track(client, "article_view", payload={"articleSlug": "x"})
        assert resp.status_code == 201

    def test_oversized_payload_rejected(self, client):
        resp = _track(client, "article_view", payload={"x": "y" * 5000})
        assert resp.status_code == 422

    def test_ingestion_never_blocks_on_missing_optional_fields(self, client):
        resp = _track(client, "search_performed")
        assert resp.status_code == 201


class TestDateRangeHandling:
    def test_default_range_is_last_30_days(self, client, app, admin_token):
        resp = client.get("/api/v1/analytics/overview", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        body = resp.get_json()["data"]["range"]
        start = date.fromisoformat(body["start"])
        end = date.fromisoformat(body["end"])
        assert (end - start).days == 29

    def test_end_before_start_rejected(self, client, admin_token):
        resp = client.get(
            "/api/v1/analytics/overview?start=2026-05-01&end=2026-01-01", headers=auth_headers(admin_token)
        )
        assert resp.status_code == 422

    def test_unbounded_range_rejected(self, client, admin_token):
        resp = client.get(
            "/api/v1/analytics/overview?start=2020-01-01&end=2026-01-01", headers=auth_headers(admin_token)
        )
        assert resp.status_code == 422

    def test_custom_range_is_honored(self, client, admin_token):
        resp = client.get(
            "/api/v1/analytics/overview?start=2026-01-01&end=2026-01-07", headers=auth_headers(admin_token)
        )
        assert resp.status_code == 200
        assert resp.get_json()["data"]["range"] == {"start": "2026-01-01", "end": "2026-01-07"}


class TestOverviewAggregation:
    def test_metrics_reflect_real_tracked_events(self, client, admin_token):
        for _ in range(3):
            _track(client, "article_view", payload={"articleSlug": "real-article"})
        resp = client.get("/api/v1/analytics/overview", headers=auth_headers(admin_token))
        metrics = resp.get_json()["data"]["metrics"]
        assert metrics["articleViews"] == 3
        assert metrics["contentViews"] == 3

    def test_no_events_yields_zero_not_fabricated_numbers(self, client, admin_token):
        resp = client.get(
            "/api/v1/analytics/overview?start=2020-06-01&end=2020-06-07", headers=auth_headers(admin_token)
        )
        metrics = resp.get_json()["data"]["metrics"]
        assert all(v == 0 for v in metrics.values())

    def test_comparison_omitted_without_compare_flag(self, client, admin_token):
        resp = client.get("/api/v1/analytics/overview", headers=auth_headers(admin_token))
        assert resp.get_json()["data"]["comparison"] is None

    def test_comparison_change_is_null_for_zero_baseline_never_fake_percent(self, client, admin_token):
        _track(client, "article_view", payload={"articleSlug": "x"})
        resp = client.get("/api/v1/analytics/overview?compare=true", headers=auth_headers(admin_token))
        changes = resp.get_json()["data"]["comparison"]["changes"]
        assert changes["articleViews"] is None


class TestContentPerformance:
    def test_top_articles_ranked_by_real_view_events(self, client, app, admin_token):
        author = client.post("/api/v1/authors", json={"name": "A B"}, headers=auth_headers(admin_token))
        author_slug = author.get_json()["data"]["slug"]
        client.post(
            "/api/v1/articles",
            json={
                "title": "Popular Piece",
                "authorSlug": author_slug,
                "status": "published",
                "content": [{"type": "paragraph", "text": "x"}],
            },
            headers=auth_headers(admin_token),
        )
        with app.app_context():
            from app.models.article import Article

            slug = Article.query.filter_by(title="Popular Piece").first().slug
        for _ in range(5):
            _track(client, "article_view", payload={"articleSlug": slug})

        resp = client.get("/api/v1/analytics/content", headers=auth_headers(admin_token))
        body = resp.get_json()["data"]
        assert body["results"][0]["slug"] == slug
        assert body["results"][0]["views"] == 5
        assert body["results"][0]["url"] == f"/{slug}"

    def test_deleted_article_view_count_survives_without_crashing(self, client, admin_token):
        for _ in range(2):
            _track(client, "article_view", payload={"articleSlug": "never-existed-slug"})
        resp = client.get("/api/v1/analytics/content", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        row = next(r for r in resp.get_json()["data"]["results"] if r["slug"] == "never-existed-slug")
        assert row["title"] == "Deleted content"
        assert row["url"] is None
        assert row["views"] == 2

    def test_invalid_sort_rejected(self, client, admin_token):
        resp = client.get("/api/v1/analytics/content?sort=not_a_real_sort", headers=auth_headers(admin_token))
        assert resp.status_code == 422


class TestSearchAnalytics:
    def test_zero_result_search_counted_correctly(self, client, admin_token):
        _track(client, "search_performed", payload={"query": "leadership", "resultCount": 3})
        _track(client, "search_performed", payload={"query": "zzzznomatch", "resultCount": 0})
        resp = client.get("/api/v1/analytics/search-report", headers=auth_headers(admin_token))
        body = resp.get_json()["data"]
        assert body["totalSearches"] == 2
        assert body["zeroResultSearches"] == 1

    def test_top_queries_reflect_real_search_events(self, client, admin_token):
        for _ in range(4):
            _track(client, "search_performed", payload={"query": "mentorship", "resultCount": 2})
        resp = client.get("/api/v1/analytics/search-report", headers=auth_headers(admin_token))
        top = resp.get_json()["data"]["topQueries"]
        assert top[0]["query"] == "mentorship"
        assert top[0]["count"] == 4

    def test_never_builds_personalized_search_profile(self, client, admin_token):
        # The response is aggregate-only — no session_id or user identity
        # anywhere in the payload.
        _track(client, "search_performed", payload={"query": "x", "resultCount": 1}, sessionId="abc-session")
        resp = client.get("/api/v1/analytics/search-report", headers=auth_headers(admin_token))
        assert "abc-session" not in resp.get_data(as_text=True)


class TestNewsletterAnalytics:
    def test_new_subscriber_counted_in_range(self, client, app, admin_token):
        client.post("/api/v1/newsletter/subscribe", json={"email": "new@example.com", "consent": True})
        resp = client.get("/api/v1/analytics/newsletter", headers=auth_headers(admin_token))
        assert resp.get_json()["data"]["newSubscribers"] >= 1

    def test_no_email_open_or_click_metrics_without_a_provider(self, client, admin_token):
        resp = client.get("/api/v1/analytics/newsletter", headers=auth_headers(admin_token))
        body = resp.get_json()["data"]
        assert "openRate" not in body
        assert "clickThroughRate" not in body


class TestCareersAnalytics:
    def test_job_apply_click_never_labeled_a_completed_application(self, client, admin_token):
        _track(client, "job_apply_click", payload={"jobSlug": "x"})
        resp = client.get("/api/v1/analytics/careers", headers=auth_headers(admin_token))
        body = resp.get_json()["data"]
        assert body["jobs"]["applyClicks"] == 1
        assert "applications" not in resp.get_data(as_text=True).lower()

    def test_resource_download_click_distinct_from_real_download(self, client, admin_token):
        _track(client, "resource_download_click", payload={"resourceSlug": "x"})
        resp = client.get("/api/v1/analytics/careers", headers=auth_headers(admin_token))
        body = resp.get_json()["data"]
        assert body["resources"]["downloadClicks"] == 1
        assert body["resources"]["downloads"] == 0


class TestCommunityProgramsPrivacy:
    def test_response_never_contains_member_identity(self, client, app, admin_token):
        from app.models.community import Member

        with app.app_context():
            db.session.add(Member(first_name="Priva", last_name="Cy", email="privacy-check@example.com", status="active"))
            db.session.commit()
        resp = client.get("/api/v1/analytics/community-programs", headers=auth_headers(admin_token))
        text = resp.get_data(as_text=True)
        assert "privacy-check@example.com" not in text
        assert "Priva" not in text

    def test_aggregate_counts_are_real(self, client, admin_token):
        resp = client.get("/api/v1/analytics/community-programs", headers=auth_headers(admin_token))
        body = resp.get_json()["data"]
        assert "mentorship" in body
        assert "community" in body
        assert isinstance(body["mentorship"]["activeMatches"], int)


class TestCommercialAnalyticsAndCTR:
    def test_sponsor_ctr_computed_from_real_clicks_and_impressions(self, client, app, admin_token):
        from app.models.commerce import Sponsor
        from app.models.people import Organization

        with app.app_context():
            org = Organization(slug="ctr-org", name="CTR Org", status="published", description=[])
            db.session.add(org)
            db.session.commit()
            sponsor = Sponsor(campaign_name="CTR Campaign", organization_id=org.id, status="active")
            db.session.add(sponsor)
            db.session.commit()
            sponsor_id = sponsor.id
        for _ in range(10):
            _track(client, "sponsor_impression", entityType="Sponsor", entityId=str(sponsor_id))
        for _ in range(2):
            _track(client, "sponsor_click", entityType="Sponsor", entityId=str(sponsor_id))

        resp = client.get("/api/v1/analytics/commercial", headers=auth_headers(admin_token))
        row = next(r for r in resp.get_json()["data"]["sponsors"] if r["sponsor"] == "CTR Campaign")
        assert row["impressions"] == 10
        assert row["clicks"] == 2
        assert row["ctr"] == 20.0

    def test_zero_impression_ctr_is_null_not_division_error(self, client, app, admin_token):
        from app.models.commerce import Sponsor
        from app.models.people import Organization

        with app.app_context():
            org = Organization(slug="zero-org", name="Zero Org", status="published", description=[])
            db.session.add(org)
            db.session.commit()
            sponsor = Sponsor(campaign_name="Zero Impressions", organization_id=org.id, status="active")
            db.session.add(sponsor)
            db.session.commit()
            sponsor_id = sponsor.id
        _track(client, "sponsor_click", entityType="Sponsor", entityId=str(sponsor_id))

        resp = client.get("/api/v1/analytics/commercial", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        row = next(r for r in resp.get_json()["data"]["sponsors"] if r["sponsor"] == "Zero Impressions")
        assert row["ctr"] is None

    def test_multi_currency_revenue_never_summed_together(self, client, app, admin_token):
        from app.models.commerce import Order

        with app.app_context():
            db.session.add(
                Order(
                    email="a@example.com", order_status="completed", payment_status="paid",
                    subtotal_amount=100, total_amount=100, currency="USD",
                )
            )
            db.session.add(
                Order(
                    email="b@example.com", order_status="completed", payment_status="paid",
                    subtotal_amount=5000, total_amount=5000, currency="KES",
                )
            )
            db.session.commit()
        resp = client.get("/api/v1/analytics/commercial", headers=auth_headers(admin_token))
        by_currency = {row["currency"]: row for row in resp.get_json()["data"]["orders"]["byCurrency"]}
        assert by_currency["USD"]["completedTotal"] == 100
        assert by_currency["KES"]["completedTotal"] == 5000

    def test_cancelled_order_excluded_from_revenue(self, client, app, admin_token):
        from app.models.commerce import Order

        with app.app_context():
            db.session.add(
                Order(
                    email="c@example.com", order_status="cancelled", payment_status="unpaid",
                    subtotal_amount=999, total_amount=999, currency="USD",
                )
            )
            db.session.commit()
        resp = client.get("/api/v1/analytics/commercial", headers=auth_headers(admin_token))
        by_currency = {row["currency"]: row for row in resp.get_json()["data"]["orders"]["byCurrency"]}
        # The cancelled order must not appear (or must not inflate an
        # existing USD total) — check no 999 total exists anywhere.
        assert all(row["completedTotal"] != 999 for row in resp.get_json()["data"]["orders"]["byCurrency"])


class TestRBAC:
    def test_no_permission_denied_general_analytics(self, client, app):
        token = _register_with_role(client, app, "noperm@example.com", None)
        resp = client.get("/api/v1/analytics/overview", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_analyst_can_view_general_analytics(self, client, app):
        token = _register_with_role(client, app, "analyst@example.com", "analyst")
        resp = client.get("/api/v1/analytics/overview", headers=auth_headers(token))
        assert resp.status_code == 200

    def test_analyst_denied_commercial_analytics(self, client, app):
        token = _register_with_role(client, app, "analyst2@example.com", "analyst")
        resp = client.get("/api/v1/analytics/commercial", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_partnerships_manager_can_view_commercial_analytics(self, client, app):
        token = _register_with_role(client, app, "pm@example.com", "partnerships_manager")
        resp = client.get("/api/v1/analytics/commercial", headers=auth_headers(token))
        assert resp.status_code == 200

    def test_partnerships_manager_denied_general_analytics(self, client, app):
        token = _register_with_role(client, app, "pm2@example.com", "partnerships_manager")
        resp = client.get("/api/v1/analytics/overview", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_export_requires_export_permission(self, client, app):
        token = _register_with_role(client, app, "editor-noexport@example.com", "editor")
        resp = client.get("/api/v1/analytics/export/content", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_analyst_can_export(self, client, app):
        token = _register_with_role(client, app, "analyst3@example.com", "analyst")
        resp = client.get("/api/v1/analytics/export/content", headers=auth_headers(token))
        assert resp.status_code == 200

    def test_sponsor_export_requires_both_export_and_commercial(self, client, app):
        # Analyst has export but not commercial.
        token = _register_with_role(client, app, "analyst4@example.com", "analyst")
        resp = client.get("/api/v1/analytics/export/sponsors", headers=auth_headers(token))
        assert resp.status_code == 403


class TestExportSafety:
    def test_content_export_is_csv(self, client, admin_token):
        resp = client.get("/api/v1/analytics/export/content", headers=auth_headers(admin_token))
        assert resp.status_code == 200
        assert "text/csv" in resp.headers["Content-Type"]
        assert "attachment" in resp.headers["Content-Disposition"]

    def test_search_export_query_field_is_formula_injection_safe(self, client, admin_token):
        _track(client, "search_performed", payload={"query": "=cmd|'/c calc'!A1", "resultCount": 0})
        resp = client.get("/api/v1/analytics/export/search", headers=auth_headers(admin_token))
        text = resp.get_data(as_text=True)
        # The dangerous leading character must be neutralized (prefixed),
        # never passed through raw into the CSV cell.
        assert "\n'=cmd" in text or ",'=cmd" in text


@pytest.fixture()
def admin_token(client, app):
    return _register_with_role(client, app, "analytics-admin@example.com", "admin")
