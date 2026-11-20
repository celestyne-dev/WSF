"""WSF Career Hub: the public discovery layer over existing Resources and
Learning programs — normalized cards, filters, sort, pagination, New This
Month, Circle-inclusive pricing, estimated time, formats, goals (via
Topic.career_goal), anonymous-only payloads, unchanged entitlements,
bounded query counts, SEO/sitemap/prerender, Career Pathways deep links
and the four Career Hub migrations."""
import importlib
import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa

from app.extensions import db

TODAY = date.today()
FIXTURE_INDEX_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "spa_index.html")


def _add(app, row):
    with app.app_context():
        db.session.add(row)
        db.session.commit()
        return row.id


def _topic(app, slug, goal=None, status="published", sort_order=0):
    from app.models.taxonomy import Topic

    return _add(app, Topic(slug=slug, name=slug.replace("-", " ").title(), status=status, career_goal=goal, sort_order=sort_order))


def _resource(app, slug, *, type="Guide", access="direct_download", status="published", published=None, featured=False,
              topics=(), prices=(), level="all_members", time=(None, None, None), summary="Short summary."):
    from app.models.resource import Resource, ResourcePrice
    from app.models.taxonomy import Topic

    with app.app_context():
        r = Resource(slug=slug, name=f"Resource {slug}", short_description=summary, status=status, description=[], type=type,
                     access_type=access, circle_access_level=level, featured=featured,
                     published_date=published if published is not None else TODAY - timedelta(days=40),
                     estimated_time_value=time[0], estimated_time_max_value=time[1], estimated_time_unit=time[2],
                     protected_file_path="secret/path.pdf", file_url="/media/secret.pdf")
        for t in topics:
            r.topics.append(db.session.get(Topic, t))
        for currency, minor in prices:
            r.prices.append(ResourcePrice(currency=currency, amount_minor=minor, enabled=True))
        db.session.add(r)
        db.session.commit()
        return r.id


def _program(app, slug, *, ptype="course", access="free", status="published", published=None, featured=False, topics=(),
             duration=(None, None), delivery="self_paced", product=None):
    from app.models.learning import LearningProgram
    from app.models.taxonomy import Topic

    with app.app_context():
        p = LearningProgram(slug=slug, title=f"Program {slug}", short_description="Learn.", status=status, program_type=ptype,
                            access_type=access, featured=featured, duration_value=duration[0], duration_unit=duration[1],
                            delivery_mode=delivery, product_id=product,
                            published_at=published or datetime.now(timezone.utc) - timedelta(days=40))
        for t in topics:
            p.topics.append(db.session.get(Topic, t))
        db.session.add(p)
        db.session.commit()
        return p.id


def _product(app, price=4500, currency="KES", status="active"):
    from app.models.commerce import Product

    return _add(app, Product(slug=f"prod-{uuid.uuid4().hex[:6]}", name="Course access", price=price, currency=currency, status=status,
                             description=[]))


def _get(client, **params):
    return client.get("/api/v1/career-hub", query_string=params)


def _slugs(resp):
    assert resp.status_code == 200, resp.get_json()
    return [c["slug"] for c in resp.get_json()["data"]]


def _settings(app, currencies=("USD", "KES")):
    from app.services.payment_settings import save_payment_settings

    app.config["PAYSTACK_ENABLED"] = True
    app.config["PAYSTACK_SECRET_KEY"] = "sk_test_x"
    app.config["PAYSTACK_ALLOWED_CURRENCIES"] = list(currencies)
    with app.app_context():
        save_payment_settings({"defaultCurrency": "KES", "enabledCurrencies": list(currencies),
                               "providers": {"paystack": {"enabled": True, "methods": {"card": True}}}})
        db.session.commit()


# --- results ------------------------------------------------------------------------


class TestResults:
    def test_mixed_sources_published_only(self, client, app):
        _resource(app, "r-pub")
        _resource(app, "r-draft", status="draft")
        _resource(app, "r-future", status="scheduled", published=TODAY + timedelta(days=5))
        _resource(app, "r-sched-due", status="scheduled", published=TODAY - timedelta(days=1))
        _resource(app, "r-archived", status="archived")
        _program(app, "l-pub")
        _program(app, "l-draft", status="draft")
        resp = _get(client)
        assert set(_slugs(resp)) == {"r-pub", "r-sched-due", "l-pub"}
        types = {c["slug"]: c["sourceType"] for c in resp.get_json()["data"]}
        assert types == {"r-pub": "resource", "r-sched-due": "resource", "l-pub": "learning"}

    def test_normalized_card_shape_is_anonymous_and_safe(self, client, app):
        goal = _topic(app, "salary-negotiation", goal="earn_more")
        _resource(app, "know-your-worth", type="Playbook", access="premium", topics=(goal,), time=(45, 60, "minutes"),
                  prices=(("KES", 150000), ("USD", 1900)))
        _settings(app)
        card = _get(client).get_json()["data"][0]
        assert set(card) == {
            "id", "sourceType", "sourceId", "slug", "title", "summary", "image", "imageAlt", "format", "goal", "category",
            "estimatedTime", "access", "circle", "pricing", "publishedAt", "featured", "url",
        }
        assert card["format"] == {"key": "playbook", "slug": "playbook", "label": "Playbook"}
        assert card["goal"] == {"key": "earn_more", "slug": "earn-more", "label": "Earn more"}
        assert card["category"] == {"slug": "salary-negotiation", "name": "Salary Negotiation"}
        assert card["estimatedTime"]["label"] == "45–60 min"
        assert card["url"] == "/resources/know-your-worth"
        body = json.dumps(card)
        for secret in ("protected_file_path", "secret/path.pdf", "/media/secret.pdf", "viewerCanAccess", "file_path"):
            assert secret not in body

    def test_search_title_and_summary(self, client, app):
        _resource(app, "negotiate", summary="Ask for more money with confidence.")
        _program(app, "leadership-101")
        _resource(app, "other")
        assert _slugs(_get(client, q="confidence")) == ["negotiate"]
        assert _slugs(_get(client, q="LEADERSHIP-101")) == ["leadership-101"]
        assert _slugs(_get(client, q="nothing-matches-this")) == []


# --- filters --------------------------------------------------------------------------


class TestFilters:
    def test_goal_filter_via_topic_mapping_and_topic_alias(self, client, app):
        promo = _topic(app, "promotion", goal="get_promoted")
        salary = _topic(app, "salary-negotiation", goal="earn_more")
        _topic(app, "hidden", goal="get_promoted", status="draft")
        _resource(app, "r-promo", topics=(promo,))
        _program(app, "l-promo", topics=(promo,))
        _resource(app, "r-salary", topics=(salary,))
        _resource(app, "r-none")
        assert set(_slugs(_get(client, goal="get-promoted"))) == {"r-promo", "l-promo"}
        assert _slugs(_get(client, goal="salary-negotiation")) == ["r-salary"]
        assert _get(client, goal="not-a-goal").status_code == 422
        assert _get(client, goal="hidden").status_code == 422  # draft topic is not an alias

    def test_draft_topic_goal_never_matches(self, client, app):
        draft = _topic(app, "drafty", goal="networking", status="draft")
        _resource(app, "r-draft-topic", topics=(draft,))
        assert _slugs(_get(client, goal="networking")) == []

    def test_format_filter_across_sources(self, client, app):
        _resource(app, "r-challenge", type="Challenge")
        _program(app, "l-challenge", ptype="challenge")
        _resource(app, "r-workbook", type="Workbook")
        _program(app, "l-course", ptype="course")
        assert set(_slugs(_get(client, format="challenge"))) == {"r-challenge", "l-challenge"}
        assert _slugs(_get(client, format="workbook")) == ["r-workbook"]
        assert _slugs(_get(client, format="course")) == ["l-course"]
        assert _slugs(_get(client, format="learning-series")) == []
        assert _get(client, format="video").status_code == 422

    def test_access_filter_semantics(self, client, app):
        for access in ("direct_download", "email_gate", "member_only", "external_link", "circle_only", "premium"):
            _resource(app, f"r-{access.replace('_', '-')}", access=access)
        _program(app, "l-free", access="free")
        _program(app, "l-circle", access="circle_only")
        _program(app, "l-product", access="product", product=_product(app))
        _program(app, "l-external", access="external")
        assert set(_slugs(_get(client, access="free"))) == {"r-direct-download", "r-email-gate", "r-member-only", "r-external-link", "l-free"}
        assert set(_slugs(_get(client, access="circle"))) == {"r-circle-only", "l-circle"}
        assert set(_slugs(_get(client, access="premium"))) == {"r-premium", "l-product"}
        assert "l-external" in _slugs(_get(client, pageSize=24))
        assert _get(client, access="everything").status_code == 422

    def test_multiple_filters_combine(self, client, app):
        lead = _topic(app, "lead", goal="leadership")
        _program(app, "match", ptype="course", access="free", topics=(lead,))
        _program(app, "wrong-access", ptype="course", access="circle_only", topics=(lead,))
        _resource(app, "wrong-format", type="Guide", topics=(lead,))
        assert _slugs(_get(client, goal="leadership", format="course", access="free")) == ["match"]

    @pytest.mark.parametrize("params", [{"sort": "most-read"}, {"page": 0}, {"pageSize": 99}, {"page": "x"}])
    def test_invalid_params_rejected(self, client, app, params):
        resp = _get(client, **params)
        assert resp.status_code == 422 and resp.get_json()["error"]["code"] == "invalid_filter"


# --- sort + pagination -----------------------------------------------------------------


class TestSortAndPagination:
    def test_newest_featured_and_recently_added(self, client, app):
        _resource(app, "old", published=TODAY - timedelta(days=30))
        _program(app, "newer", published=datetime.now(timezone.utc) - timedelta(days=2))
        _resource(app, "newest", published=TODAY)
        _resource(app, "featured-old", published=TODAY - timedelta(days=90), featured=True)
        assert _slugs(_get(client, sort="newest")) == ["newest", "newer", "old", "featured-old"]
        assert _slugs(_get(client, sort="featured"))[0] == "featured-old"
        assert _slugs(_get(client, sort="recently-added"))[0] == "featured-old"  # created last

    def test_pagination_bounds_and_meta(self, client, app):
        for i in range(7):
            _resource(app, f"r{i}", published=TODAY - timedelta(days=i))
        for i in range(6):
            _program(app, f"l{i}", published=datetime.now(timezone.utc) - timedelta(days=i, hours=12))
        first = _get(client, pageSize=5)
        assert first.get_json()["meta"] == {"page": 1, "per_page": 5, "total": 13, "total_pages": 3}
        seen = []
        for page in (1, 2, 3):
            seen += _slugs(_get(client, pageSize=5, page=page))
        assert len(seen) == 13 and len(set(seen)) == 13
        assert _slugs(_get(client, pageSize=5, page=4)) == []
        assert len(_slugs(_get(client, pageSize=5, page=1, access="free"))) == 5


# --- New This Month ------------------------------------------------------------------------


class TestNewThisMonth:
    def test_current_month_only_newest_first_bounded(self, client, app):
        from app.services.career_hub import new_this_month

        today = date(2026, 3, 15)
        _resource(app, "march-early", published=date(2026, 3, 1))
        _resource(app, "march-mid", published=date(2026, 3, 14))
        _resource(app, "feb-end", published=date(2026, 2, 28))
        _resource(app, "march-future", status="scheduled", published=date(2026, 3, 20))
        _resource(app, "march-draft", status="draft", published=date(2026, 3, 10))
        _program(app, "march-course", published=datetime(2026, 3, 2, 9, tzinfo=timezone.utc))
        _program(app, "feb-course", published=datetime(2026, 2, 28, 23, 59, tzinfo=timezone.utc))
        with app.app_context():
            slugs = [c["slug"] for c in new_this_month(today=today)]
        assert slugs == ["march-mid", "march-course", "march-early"]
        with app.app_context():
            assert len(new_this_month(today=today, limit=2)) == 2

    def test_month_boundary_first_day(self, client, app):
        from app.services.career_hub import new_this_month

        _resource(app, "first", published=date(2026, 4, 1))
        _resource(app, "last-of-prev", published=date(2026, 3, 31))
        with app.app_context():
            assert [c["slug"] for c in new_this_month(today=date(2026, 4, 1))] == ["first"]

    def test_meta_endpoint_empty_when_nothing_new(self, client, app):
        _resource(app, "old-one", published=TODAY - timedelta(days=70))
        meta = client.get("/api/v1/career-hub/meta").get_json()["data"]
        assert meta["newThisMonth"] == []
        assert [g["slug"] for g in meta["goals"]][:2] == ["find-a-job", "get-promoted"]
        assert {"playbook", "challenge", "course"} <= {f["slug"] for f in meta["formats"]}
        assert [a["slug"] for a in meta["access"]] == ["free", "circle", "premium"]
        assert "most-read" not in [s["slug"] for s in meta["sorts"]]
        for word in ("video", "audio", "podcast", "recording"):
            assert word not in json.dumps(meta["formats"]).lower()


# --- Circle inclusion + pricing ------------------------------------------------------------


class TestCircleInclusionAndPricing:
    def test_labels_follow_real_entitlement_rules(self, client, app):
        _settings(app)
        _resource(app, "premium", access="premium", prices=(("KES", 150000), ("USD", 1900)))
        _resource(app, "circle-all", access="circle_only")
        _resource(app, "circle-yearly", access="circle_only", level="yearly_members")
        _resource(app, "free", access="direct_download")
        _program(app, "course-circle", access="circle_only")
        _program(app, "course-product", access="product", product=_product(app, price=4500, currency="KES"))
        cards = {c["slug"]: c for c in _get(client, pageSize=24).get_json()["data"]}
        assert cards["premium"]["circle"] == {"included": True, "scope": "all", "label": "Included with WSF Circle"}
        assert cards["premium"]["access"]["level"] == "premium"
        assert {p["currency"] for p in cards["premium"]["pricing"]["prices"]} == {"KES", "USD"}
        assert cards["premium"]["pricing"]["defaultCurrency"] == "KES" and cards["premium"]["pricing"]["oneTime"] is True
        kes = next(p for p in cards["premium"]["pricing"]["prices"] if p["currency"] == "KES")
        assert kes["formatted"].startswith("KES") and "1,500" in kes["formatted"]
        assert cards["circle-all"]["circle"]["label"] == "Included with WSF Circle"
        assert cards["circle-yearly"]["circle"] == {"included": True, "scope": "yearly_level", "label": "Included with Yearly & Lifetime WSF Circle"}
        assert cards["circle-yearly"]["access"]["level"] == "circle"
        assert cards["free"]["circle"]["included"] is False and cards["free"]["pricing"] is None
        assert cards["course-circle"]["circle"]["included"] is True
        # A WSF-owned digital product program is included with Lifetime
        # (never with Monthly/Yearly). It carries NO price: a normal Product
        # purchase does not unlock Learning in this launch.
        assert cards["course-product"]["circle"] == {"included": True, "scope": "lifetime", "label": "Included with Lifetime WSF Circle"}
        assert cards["course-product"]["pricing"] is None
        assert cards["course-product"]["access"] == {"level": "premium", "label": "Premium"}

    def test_inclusion_claims_match_check_resource_access(self, client, app):
        """The display claim must agree with the authorization rule for a
        plain (monthly) active Circle member."""
        from app.models.circle import CirclePlan, CircleSubscription
        from app.models.resource import Resource
        from app.models.user import User
        from app.services.career_hub import build_resource_card
        from app.services.resource_access import check_resource_access
        from app.utils.responses import ApiError

        client.post("/api/v1/auth/register", json={"email": "m@example.com", "password": "supersecret1", "first_name": "M", "last_name": "M"})
        for access, level in (("premium", "all_members"), ("circle_only", "all_members"), ("circle_only", "yearly_members"), ("member_only", "all_members")):
            _resource(app, f"chk-{access}-{level}".replace("_", "-"), access=access, level=level)
        with app.app_context():
            plan = CirclePlan(slug="m", name="Monthly", billing_interval="monthly", price=0, currency="USD", status="active")
            db.session.add(plan)
            db.session.flush()
            user = User.query.filter_by(email="m@example.com").first()
            db.session.add(CircleSubscription(user_id=user.id, plan_id=plan.id, status="active", source="manual",
                                              current_period_end=datetime.now(timezone.utc) + timedelta(days=10)))
            db.session.commit()
            for resource in Resource.query.filter(Resource.slug.like("chk-%")).all():
                card = build_resource_card(resource, None)
                try:
                    check_resource_access(resource, user)
                    granted = True
                except ApiError:
                    granted = False
                if resource.access_type == "member_only":
                    continue  # free with an account; never claimed as a Circle benefit
                assert card["circle"]["included"] is True
                assert granted == (card["circle"]["scope"] == "all"), resource.slug

    def test_estimated_time_labels(self, client, app):
        from app.services.career_hub import format_estimated_time

        cases = {(10, None, "minutes"): "10 min", (30, 45, "minutes"): "30–45 min", (1, None, "hours"): "1 hour",
                 (2, None, "hours"): "2 hours", (7, None, "days"): "7 days", (14, None, "days"): "14 days",
                 (4, None, "weeks"): "4 weeks", (None, None, "self_paced"): "Self-paced", (None, None, None): None}
        for args, label in cases.items():
            assert format_estimated_time(*args) == label
        _program(app, "four-weeks", duration=(4, "weeks"))
        _program(app, "self", delivery="self_paced")
        _program(app, "live", delivery="live_online")
        cards = {c["slug"]: c for c in _get(client).get_json()["data"]}
        assert cards["four-weeks"]["estimatedTime"]["label"] == "4 weeks"
        assert cards["self"]["estimatedTime"]["label"] == "Self-paced"
        assert cards["live"]["estimatedTime"] is None


# --- protection unchanged -----------------------------------------------------------------


class TestProtectionUnchanged:
    def test_gated_content_still_protected(self, client, app):
        _resource(app, "gated", access="circle_only")
        _resource(app, "paid", access="premium")
        assert _get(client).status_code == 200
        for slug, code in (("gated", (401,)), ("paid", (401,))):
            resp = client.post(f"/api/v1/resources/{slug}/access", json={})
            assert resp.status_code in code

    def test_detail_payloads_expose_metadata_only(self, client, app):
        _resource(app, "detail", access="premium", type="Scripts", time=(None, None, "self_paced"))
        _program(app, "detail-course", access="circle_only", ptype="challenge", duration=(7, "days"))
        r = client.get("/api/v1/resources/detail").get_json()["data"]
        assert r["format"]["label"] == "Scripts" and r["estimatedTime"]["label"] == "Self-paced"
        assert r["circleInclusion"]["label"] == "Included with WSF Circle"
        l = client.get("/api/v1/learning/detail-course").get_json()["data"]
        assert l["format"]["label"] == "Challenge" and l["estimatedTime"]["label"] == "7 days"
        assert l["circleInclusion"]["included"] is True


# --- Studio metadata validation --------------------------------------------------------------


class TestStudioMetadata:
    @pytest.fixture()
    def admin_headers(self, client, app):
        from app.models.user import Role, User
        from tests.conftest import auth_headers

        payload = {"email": "hub-admin@example.com", "password": "supersecret1", "first_name": "H", "last_name": "A"}
        client.post("/api/v1/auth/register", json=payload)
        with app.app_context():
            user = User.query.filter_by(email=payload["email"]).first()
            user.roles.append(Role.query.filter_by(name="admin").first())
            db.session.commit()
        token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
        return auth_headers(token)

    @pytest.mark.parametrize("time, ok", [
        ({}, True), ({"estimatedTimeUnit": "self_paced"}, True), ({"estimatedTimeValue": 30, "estimatedTimeUnit": "minutes"}, True),
        ({"estimatedTimeValue": 30, "estimatedTimeMaxValue": 45, "estimatedTimeUnit": "minutes"}, True),
        ({"estimatedTimeValue": 30}, False), ({"estimatedTimeUnit": "minutes"}, False),
        ({"estimatedTimeValue": 3, "estimatedTimeUnit": "self_paced"}, False),
        ({"estimatedTimeValue": 45, "estimatedTimeMaxValue": 30, "estimatedTimeUnit": "minutes"}, False),
        ({"estimatedTimeValue": 2, "estimatedTimeUnit": "fortnights"}, False),
    ])
    def test_resource_estimated_time_validation(self, client, app, admin_headers, time, ok):
        body = {"name": "Timed", "type": "Playbook", "status": "draft", **time}
        resp = client.post("/api/v1/resources", json=body, headers=admin_headers)
        assert (resp.status_code == 201) is ok, resp.get_json()
        if ok:
            data = resp.get_json()["data"]
            assert data.get("estimated_time_unit", data.get("estimatedTimeUnit")) == time.get("estimatedTimeUnit")

    def test_new_formats_and_learning_challenge_saved(self, client, app, admin_headers):
        for fmt in ("Playbook", "Scripts", "Challenge", "Assessment", "Research", "Other"):
            assert client.post("/api/v1/resources", json={"name": fmt, "type": fmt}, headers=admin_headers).status_code == 201
        assert client.post("/api/v1/resources", json={"name": "V", "type": "Podcast"}, headers=admin_headers).status_code == 422

    def test_topic_career_goal_round_trip(self, client, app, admin_headers):
        resp = client.post("/api/v1/admin/taxonomy/topics", json={"name": "Promotions", "status": "published", "careerGoal": "get_promoted"}, headers=admin_headers)
        assert resp.status_code == 201, resp.get_json()
        topic_id = resp.get_json()["data"]["id"]
        assert resp.get_json()["data"]["career_goal"] == "get_promoted"
        upd = client.put(f"/api/v1/admin/taxonomy/topics/{topic_id}", json={"careerGoal": None}, headers=admin_headers)
        assert upd.status_code == 200 and upd.get_json()["data"]["career_goal"] is None
        assert client.put(f"/api/v1/admin/taxonomy/topics/{topic_id}", json={"careerGoal": "fly"}, headers=admin_headers).status_code == 422


# --- Career Pathways deep links ------------------------------------------------------------


class TestCareerPathwayDeepLinks:
    def test_route_validation_keeps_query_and_blocks_private_paths(self):
        from marshmallow import ValidationError

        from app.services.navigation import validate_route_url

        for ok in ("/career-hub?goal=get-promoted", "/career-hub?goal=leadership&format=course", "/career-hub#new", "/career-hub"):
            assert validate_route_url(ok) == ok
        for bad in ("/admin?x=1", "/ADMIN#y", "/api?z", "/api/v1/career-hub?x", "//evil.example?x", "/career hub",
                    "/career-hub?x=\\evil", "javascript:alert(1)", "career-hub?goal=x", "/admin/", "/a\x00b"):
            with pytest.raises(ValidationError):
                validate_route_url(bad)

    def test_pathway_card_with_query_saves_and_resolves(self, client, app):
        from tests.test_homepage_pathways_collections import _admin_token
        from tests.conftest import auth_headers

        headers = auth_headers(_admin_token(client, app))
        cards = [{"title": "Get promoted", "destinationType": "route", "url": "/career-hub?goal=get-promoted"},
                 {"title": "Salary", "destinationType": "route", "url": "/career-hub?goal=salary-negotiation&format=playbook"}]
        resp = client.put("/api/v1/admin/homepage", json={"modules": [{"type": "career_pathways", "config": {"cards": cards}}]}, headers=headers)
        assert resp.status_code == 200, resp.get_json()
        resolved = client.get("/api/v1/public/homepage").get_json()["data"][0]["resolved"]["cards"]
        assert [c["href"] for c in resolved] == ["/career-hub?goal=get-promoted", "/career-hub?goal=salary-negotiation&format=playbook"]
        bad = [{"title": "A", "destinationType": "route", "url": "/admin?goal=x"}, cards[0]]
        assert client.put("/api/v1/admin/homepage", json={"modules": [{"type": "career_pathways", "config": {"cards": bad}}]}, headers=headers).status_code == 422


# --- SEO -------------------------------------------------------------------------------------


class TestSeo:
    def test_shell_metadata_prerender_and_canonical(self, client, app):
        app.config["SPA_INDEX_PATH"] = FIXTURE_INDEX_PATH
        _resource(app, "seo-tool", published=TODAY)
        html = client.get("/career-hub?goal=get-promoted&format=workbook").get_data(as_text=True)
        assert "WSF Career Hub" in re.search(r"<title>(.*?)</title>", html, re.S).group(1)
        canonical = re.search(r'<link[^>]+rel="canonical"[^>]*>', html).group(0)
        assert canonical.endswith('/career-hub">') or 'href="' in canonical and "?" not in canonical
        assert "?goal" not in canonical
        assert 'property="og:title"' in html and 'name="description"' in html
        root = html.split('data-wsf-prerender="career-hub"', 1)[1]
        assert "Practical tools for your next career move." in root
        assert "/resources/seo-tool" in root and "/career-hub?goal=get-promoted" in root

    def test_sitemap_lists_one_career_hub_url(self, client, app):
        xml = client.get("/sitemap.xml").get_data(as_text=True)
        assert xml.count("/career-hub</loc>") == 1
        assert "career-hub?" not in xml


# --- query counts ----------------------------------------------------------------------------


def _count(app, fn):
    from sqlalchemy import event

    statements = []
    listener = lambda *args: statements.append(args[2])  # noqa: E731
    event.listen(db.engine, "before_cursor_execute", listener)
    try:
        fn()
    finally:
        event.remove(db.engine, "before_cursor_execute", listener)
    return len(statements)


class TestQueryCounts:
    def _seed(self, app, n):
        _settings(app)
        topic = _topic(app, "promo", goal="get_promoted")
        for i in range(n):
            _resource(app, f"qr{i}", type="Workbook", access="premium" if i % 2 else "circle_only", topics=(topic,),
                      prices=(("KES", 100000), ("USD", 900)), published=TODAY - timedelta(days=i))
            _program(app, f"ql{i}", access="product" if i % 2 else "free", topics=(topic,), product=_product(app),
                     published=datetime.now(timezone.utc) - timedelta(days=i))

    def test_constant_queries_regardless_of_page_size(self, client, app):
        from app.services.career_hub import career_hub_meta, parse_filters, search_career_hub

        self._seed(app, 14)
        with app.app_context():
            counts = {}
            for size in (1, 4, 24):
                db.session.expire_all()
                counts[size] = _count(app, lambda: search_career_hub(parse_filters({"pageSize": size})))
            db.session.expire_all()
            filtered = _count(app, lambda: search_career_hub(parse_filters({"pageSize": 24, "goal": "get-promoted", "format": "workbook"})))
            db.session.expire_all()
            learning = _count(app, lambda: search_career_hub(parse_filters({"pageSize": 24, "format": "course"})))
            db.session.expire_all()
            meta = _count(app, lambda: career_hub_meta())
        # A 1-item page loads one source; 4 and 24 items both mix Resources
        # and Learning — same statement count, so nothing runs per card.
        assert counts[1] <= counts[4] == counts[24] <= 16, counts
        assert filtered <= 16 and learning <= 16 and meta <= 16, (filtered, learning, meta)


# --- migrations --------------------------------------------------------------------------------


class TestCareerHubMigrations:
    def test_chain_and_single_head(self):
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        chain = [("d1a4e7b2c9f3", "c5e2a9d4f1b8"), ("e2b5f8c3d0a4", "d1a4e7b2c9f3"), ("f3c6a9d4e1b5", "e2b5f8c3d0a4"),
                 ("a4d7b0e5f2c6", "f3c6a9d4e1b5"), ("b5e8c1f6a3d7", "a4d7b0e5f2c6")]
        config = Config()
        config.set_main_option("script_location", os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations"))
        script = ScriptDirectory.from_config(config)
        heads = script.get_heads()
        assert len(heads) == 1
        ancestry = {rev.revision for rev in script.iterate_revisions(heads[0], "base")}
        for revision, down in chain:
            assert revision in ancestry and script.get_revision(revision).down_revision == down

    def test_resource_format_and_learning_type_widen_and_restore(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        engine = sa.create_engine("sqlite://")
        fmt = importlib.import_module("migrations.versions.d1a4e7b2c9f3_resource_career_formats")
        lp = importlib.import_module("migrations.versions.f3c6a9d4e1b5_learning_challenge_type")
        with engine.begin() as conn:
            conn.execute(sa.text(f"CREATE TABLE resources (id INTEGER PRIMARY KEY, type VARCHAR(50), CONSTRAINT ck_resources_type CHECK ({fmt._check(fmt._PREVIOUS)}))"))
            conn.execute(sa.text(f"CREATE TABLE learning_programs (id INTEGER PRIMARY KEY, program_type VARCHAR(30) NOT NULL, CONSTRAINT ck_learning_programs_type CHECK ({lp._check(lp._PREVIOUS)}))"))
            conn.execute(sa.text("INSERT INTO resources (type) VALUES ('Guide'), (NULL)"))
            conn.execute(sa.text("INSERT INTO learning_programs (program_type) VALUES ('course')"))
            with Operations.context(MigrationContext.configure(conn)):
                fmt.upgrade()
                lp.upgrade()
            conn.execute(sa.text("INSERT INTO resources (type) VALUES ('Playbook')"))
            conn.execute(sa.text("INSERT INTO learning_programs (program_type) VALUES ('challenge')"))
            for module in (fmt, lp):
                with pytest.raises(RuntimeError):
                    with Operations.context(MigrationContext.configure(conn)):
                        module.downgrade()
            conn.execute(sa.text("DELETE FROM resources WHERE type = 'Playbook'"))
            conn.execute(sa.text("DELETE FROM learning_programs WHERE program_type = 'challenge'"))
            with Operations.context(MigrationContext.configure(conn)):
                fmt.downgrade()
                lp.downgrade()
            assert conn.execute(sa.text("SELECT type FROM resources ORDER BY id")).scalars().all() == ["Guide", None]
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(sa.text("INSERT INTO resources (type) VALUES ('Playbook')"))

    def test_estimated_time_and_career_goal_columns_add_and_drop(self):
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        engine = sa.create_engine("sqlite://")
        est = importlib.import_module("migrations.versions.e2b5f8c3d0a4_resource_estimated_time")
        goal = importlib.import_module("migrations.versions.a4d7b0e5f2c6_topic_career_goal")
        with engine.begin() as conn:
            conn.execute(sa.text("CREATE TABLE resources (id INTEGER PRIMARY KEY, name TEXT)"))
            conn.execute(sa.text("CREATE TABLE topics (id INTEGER PRIMARY KEY, name TEXT)"))
            conn.execute(sa.text("INSERT INTO resources (name) VALUES ('kept')"))
            conn.execute(sa.text("INSERT INTO topics (name) VALUES ('kept')"))
            with Operations.context(MigrationContext.configure(conn)):
                est.upgrade()
                goal.upgrade()
            assert conn.execute(sa.text("SELECT estimated_time_unit FROM resources")).scalar() is None
            assert conn.execute(sa.text("SELECT career_goal FROM topics")).scalar() is None
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(sa.text("INSERT INTO resources (name, estimated_time_unit) VALUES ('x', 'self_paced')"))
                conn.execute(sa.text("INSERT INTO resources (name, estimated_time_value, estimated_time_unit) VALUES ('y', 5, 'self_paced')"))
        with engine.begin() as conn:
            with pytest.raises(sa.exc.IntegrityError):
                conn.execute(sa.text("INSERT INTO topics (name, career_goal) VALUES ('z', 'fly')"))
        with engine.begin() as conn:
            with Operations.context(MigrationContext.configure(conn)):
                goal.downgrade()
                est.downgrade()
            assert conn.execute(sa.text("SELECT name FROM resources")).scalars().all() == ["kept", "x"]
            cols = [r[1] for r in conn.execute(sa.text("PRAGMA table_info(topics)")).all()]
            assert "career_goal" not in cols
