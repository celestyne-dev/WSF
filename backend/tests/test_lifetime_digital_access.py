"""WSF Circle Lifetime as the highest digital tier: central tier helpers,
Lifetime access to every WSF digital Resource and eligible WSF Learning
(including product-linked programs, without any Product checkout/Order),
Product exclusions, viewer-specific labels, Founding Lifetime capacity and
snapshot, membership badges, and regressions for Monthly/Yearly."""
import threading
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.extensions import db
from tests.conftest import auth_headers
from tests.test_circle_lifetime import (
    USER,
    _checkout,
    _current,
    _enable_paystack,
    _mock_init,
    _payment,
    _plan,
    _register,
    _subscription,
    _success,
    _user,
)
from tests.test_learning_circle_access import _make_program


def _member(app, client, interval, **sub_fields):
    """Register USER and give her an active membership on a new plan of
    `interval` (None = no membership). Returns (token, user_id)."""
    token = _register(client, USER)
    uid = _user(app).id
    if interval:
        plan_id, _ = _plan(app, interval=interval, prices=(("USD", 1500),))
        end = None if interval == "lifetime" else datetime.now(timezone.utc) + timedelta(days=20)
        _subscription(app, uid, plan_id, current_period_end=end, **sub_fields)
    return token, uid


def _product(app, type="digital", status="active"):
    from app.models.commerce import Product

    with app.app_context():
        product = Product(slug=f"prod-{uuid.uuid4().hex[:6]}", name="Program access", price=4500, currency="KES",
                          status=status, type=type, description=[])
        db.session.add(product)
        db.session.commit()
        return product.id


def _resource(app, slug, access="premium", level="all_members"):
    from app.models.resource import Resource

    with app.app_context():
        r = Resource(slug=slug, name=slug, status="published", description=[], access_type=access, circle_access_level=level,
                     external_url="https://example.org/x" if access == "external_link" else None,
                     file_url="/media/resources/file.pdf" if access != "external_link" else None)
        db.session.add(r)
        db.session.commit()
        return r.id


def _orders(app):
    from app.models.commerce import Order

    with app.app_context():
        return Order.query.count()


# --- tier helpers -------------------------------------------------------------------


class TestTierHelpers:
    @pytest.mark.parametrize("interval, tier", [(None, None), ("monthly", "monthly"), ("yearly", "yearly"), ("lifetime", "lifetime")])
    def test_circle_tier_and_lifetime_helper(self, client, app, interval, tier):
        from app.models.user import User
        from app.services.circle import circle_tier, has_lifetime_circle_access, has_yearly_circle_access

        _token, uid = _member(app, client, interval)
        with app.app_context():
            user = db.session.get(User, uid)
            assert circle_tier(user) == tier
            assert has_lifetime_circle_access(user) is (tier == "lifetime")
            assert has_yearly_circle_access(user) is (tier in ("yearly", "lifetime"))

    @pytest.mark.parametrize("status", ["pending", "past_due", "revoked", "cancelled", "expired"])
    def test_non_granting_lifetime_rows_are_not_lifetime(self, client, app, status):
        from app.models.user import User
        from app.services.circle import circle_tier, has_lifetime_circle_access

        _token, uid = _member(app, client, "lifetime", status=status)
        with app.app_context():
            user = db.session.get(User, uid)
            assert circle_tier(user) is None and has_lifetime_circle_access(user) is False

    def test_tier_includes_scope(self):
        from app.services.circle import tier_includes_scope

        assert [tier_includes_scope(t, "all") for t in (None, "monthly", "yearly", "lifetime")] == [False, True, True, True]
        assert [tier_includes_scope(t, "yearly_level") for t in (None, "monthly", "yearly", "lifetime")] == [False, False, True, True]
        assert [tier_includes_scope(t, "lifetime") for t in (None, "monthly", "yearly", "lifetime")] == [False, False, False, True]


# --- Resources ------------------------------------------------------------------------


class TestLifetimeResources:
    @pytest.mark.parametrize("access, level", [
        ("direct_download", "all_members"), ("email_gate", "all_members"), ("member_only", "all_members"),
        ("circle_only", "all_members"), ("circle_only", "yearly_members"), ("premium", "all_members"),
        ("external_link", "all_members"),
    ])
    def test_lifetime_accesses_every_resource_type(self, client, app, access, level):
        token, _uid = _member(app, client, "lifetime")
        _resource(app, "r", access=access, level=level)
        resp = client.post("/api/v1/resources/r/access", json={}, headers=auth_headers(token))
        # Entitlement granted: never 401/403. (A premium/Circle file still
        # requires a protected upload — "not_configured" — security unchanged.)
        assert resp.status_code not in (401, 403), resp.get_json()
        assert resp.status_code in (200, 201) or resp.get_json()["error"]["code"] == "not_configured"
        detail = client.get("/api/v1/resources/r", headers=auth_headers(token)).get_json()["data"]
        assert detail["viewerCanAccess"] is True
        if access in ("circle_only", "premium"):
            assert detail["viewerMembershipLabel"] == "Included with your Lifetime membership"
        # No purchase/order is ever created for membership access.
        assert _orders(app) == 0

    def test_email_gate_records_lead_from_account_without_consent(self, client, app):
        from app.models.resource import ResourceLead

        token, _uid = _member(app, client, "lifetime")
        _resource(app, "gate", access="email_gate")
        assert client.post("/api/v1/resources/gate/access", json={}, headers=auth_headers(token)).status_code in (200, 201)
        with app.app_context():
            lead = ResourceLead.query.one()
            assert lead.email == USER["email"] and lead.newsletter_consent is False

    @pytest.mark.parametrize("interval", [None, "monthly", "yearly"])
    def test_non_lifetime_still_needs_the_email_form(self, client, app, interval):
        token, _uid = _member(app, client, interval)
        _resource(app, "gate", access="email_gate")
        assert client.post("/api/v1/resources/gate/access", json={}, headers=auth_headers(token)).status_code == 422

    def test_unpublished_resource_stays_hidden_from_lifetime(self, client, app):
        from app.models.resource import Resource

        token, _uid = _member(app, client, "lifetime")
        _resource(app, "draft", access="premium")
        with app.app_context():
            Resource.query.filter_by(slug="draft").one().status = "draft"
            db.session.commit()
        assert client.post("/api/v1/resources/draft/access", json={}, headers=auth_headers(token)).status_code == 404

    def test_protected_file_path_never_exposed(self, client, app):
        from app.models.resource import Resource

        token, _uid = _member(app, client, "lifetime")
        _resource(app, "prot", access="premium")
        with app.app_context():
            Resource.query.filter_by(slug="prot").one().protected_file_path = "vault/secret.pdf"
            db.session.commit()
        body = client.get("/api/v1/resources/prot", headers=auth_headers(token)).get_data(as_text=True)
        assert "vault/secret.pdf" not in body

    @pytest.mark.parametrize("interval, yearly_ok, label", [
        ("monthly", False, "Included with your WSF Circle membership"),
        ("yearly", True, "Included with your WSF Circle membership"),
    ])
    def test_monthly_and_yearly_unchanged(self, client, app, interval, yearly_ok, label):
        token, _uid = _member(app, client, interval)
        _resource(app, "prem", access="premium")
        _resource(app, "bonus", access="circle_only", level="yearly_members")
        assert client.post("/api/v1/resources/prem/access", json={}, headers=auth_headers(token)).status_code not in (401, 403)
        assert (client.post("/api/v1/resources/bonus/access", json={}, headers=auth_headers(token)).status_code not in (401, 403)) is yearly_ok
        assert client.get("/api/v1/resources/prem", headers=auth_headers(token)).get_json()["data"]["viewerMembershipLabel"] == label

    def test_anonymous_payload_has_no_viewer_label(self, client, app):
        _resource(app, "anon", access="premium")
        assert client.get("/api/v1/resources/anon").get_json()["data"]["viewerMembershipLabel"] is None


# --- Learning -----------------------------------------------------------------------------


def _enroll(client, token, program_id):
    return client.post("/api/v1/learning-enrollments", json={"program_id": program_id}, headers=auth_headers(token))


class TestLifetimeLearning:
    @pytest.mark.parametrize("ptype", ["course", "masterclass", "program", "learning_series", "challenge"])
    @pytest.mark.parametrize("access", ["free", "circle_only", "product"])
    def test_lifetime_enrolls_and_reads_curriculum_without_purchase(self, client, app, ptype, access):
        token, _uid = _member(app, client, "lifetime")
        extra = {"product_id": _product(app)} if access == "product" else {}
        program_id, lesson_ids = _make_program(app, lesson_count=1, access_type=access, program_type=ptype, **extra)
        resp = _enroll(client, token, program_id)
        assert resp.status_code in (200, 201), resp.get_json()
        enrollment_id = resp.get_json()["data"]["enrollment"]["id"]
        curriculum = client.get(f"/api/v1/learning-enrollments/{enrollment_id}/curriculum", headers=auth_headers(token))
        assert curriculum.status_code == 200
        assert "Secret lesson body." in curriculum.get_data(as_text=True)
        done = client.post(f"/api/v1/learning-enrollments/{enrollment_id}/lessons/{lesson_ids[0]}/complete", headers=auth_headers(token))
        assert done.status_code == 200
        assert _orders(app) == 0  # no fake order/payment

    def test_product_program_detail_label_for_lifetime(self, client, app):
        from app.models.learning import LearningProgram

        token, _uid = _member(app, client, "lifetime")
        program_id, _ = _make_program(app, access_type="product", product_id=_product(app))
        with app.app_context():
            slug = db.session.get(LearningProgram, program_id).slug
        data = client.get(f"/api/v1/learning/{slug}", headers=auth_headers(token)).get_json()["data"]
        assert data["viewerCanAccess"] is True and data["viewerMembershipLabel"] == "Included with your Lifetime membership"
        anon = client.get(f"/api/v1/learning/{slug}").get_json()["data"]
        assert anon["viewerCanAccess"] is False and anon["viewerMembershipLabel"] is None
        assert anon["circleInclusion"] == {"included": True, "scope": "lifetime", "label": "Included with Lifetime WSF Circle"}

    @pytest.mark.parametrize("interval", [None, "monthly", "yearly"])
    def test_product_program_still_requires_purchase_below_lifetime(self, client, app, interval):
        token, _uid = _member(app, client, interval)
        program_id, _ = _make_program(app, access_type="product", product_id=_product(app))
        resp = _enroll(client, token, program_id)
        assert resp.status_code == 422 and resp.get_json()["error"]["code"] == "product_enrollment"

    @pytest.mark.parametrize("ptype", ["service", "physical", "other"])
    def test_non_digital_product_programs_excluded(self, client, app, ptype):
        token, _uid = _member(app, client, "lifetime")
        program_id, _ = _make_program(app, access_type="product", product_id=_product(app, type=ptype))
        assert _enroll(client, token, program_id).status_code == 422

    def test_partner_and_external_programs_excluded(self, client, app):
        from app.models.people import Organization

        token, _uid = _member(app, client, "lifetime")
        with app.app_context():
            org = Organization(slug="partner-org", name="Partner", status="published")
            db.session.add(org)
            db.session.commit()
            org_id = org.id
        partner_id, _ = _make_program(app, access_type="product", product_id=_product(app), provider_organization_id=org_id)
        external_id, _ = _make_program(app, access_type="external", external_url="https://partner.example.org/enrol")
        assert _enroll(client, token, partner_id).status_code == 422
        assert _enroll(client, token, external_id).status_code == 422

    def test_product_program_without_linked_product_excluded(self, client, app):
        token, _uid = _member(app, client, "lifetime")
        program_id, _ = _make_program(app, access_type="product")
        assert _enroll(client, token, program_id).status_code == 422

    def test_revoked_lifetime_loses_product_program_curriculum(self, client, app):
        from app.models.circle import CircleSubscription

        token, uid = _member(app, client, "lifetime")
        program_id, _ = _make_program(app, access_type="product", product_id=_product(app))
        enrollment_id = _enroll(client, token, program_id).get_json()["data"]["enrollment"]["id"]
        with app.app_context():
            sub = CircleSubscription.query.filter_by(user_id=uid).one()
            sub.status = "revoked"
            db.session.commit()
        resp = client.get(f"/api/v1/learning-enrollments/{enrollment_id}/curriculum", headers=auth_headers(token))
        assert resp.status_code == 403

    def test_future_content_included_automatically(self, client, app):
        """A program created after the membership started is included with
        no per-member entitlement rows."""
        token, _uid = _member(app, client, "lifetime")
        later_id, _ = _make_program(app, access_type="product", product_id=_product(app))
        assert _enroll(client, token, later_id).status_code in (200, 201)

    def test_new_lessons_remain_accessible(self, client, app):
        from app.models.learning import LearningLesson, LearningModule

        token, _uid = _member(app, client, "lifetime")
        program_id, _ = _make_program(app, access_type="product", product_id=_product(app))
        enrollment_id = _enroll(client, token, program_id).get_json()["data"]["enrollment"]["id"]
        with app.app_context():
            module = LearningModule.query.filter_by(learning_program_id=program_id).first()
            db.session.add(LearningLesson(module_id=module.id, title="New lesson", lesson_type="text",
                                          content=[{"type": "paragraph", "text": "Freshly added."}], sort_order=9))
            db.session.commit()
        body = client.get(f"/api/v1/learning-enrollments/{enrollment_id}/curriculum", headers=auth_headers(token)).get_data(as_text=True)
        assert "Freshly added." in body


# --- Products stay protected ---------------------------------------------------------------


class TestProductsProtected:
    def test_lifetime_gets_no_product_or_order_side_effects(self, client, app):
        from app.models.commerce import Product

        token, _uid = _member(app, client, "lifetime")
        physical = _product(app, type="physical")
        _product(app, type="digital")
        with app.app_context():
            product = db.session.get(Product, physical)
            resp = client.get(f"/api/v1/products/{product.slug}", headers=auth_headers(token))
        assert resp.status_code == 200
        body = resp.get_json()["data"]
        assert "viewerMembershipLabel" not in body and body.get("price") == 4500
        assert _orders(app) == 0

    def test_lifetime_unlock_is_learning_program_scoped(self, client, app):
        """The product is linked to program A; program B (no link) and the
        bare Product itself are not unlocked."""
        from app.models.learning import LearningProgram
        from app.models.user import User
        from app.services.learning_access import can_access_program_content

        token, uid = _member(app, client, "lifetime")
        product_id = _product(app)
        a_id, _ = _make_program(app, access_type="product", product_id=product_id)
        b_id, _ = _make_program(app, access_type="product")
        with app.app_context():
            user = db.session.get(User, uid)
            assert can_access_program_content(db.session.get(LearningProgram, a_id), user) is True
            assert can_access_program_content(db.session.get(LearningProgram, b_id), user) is False


# --- Career Hub viewer state -----------------------------------------------------------------


class TestCareerHubViewer:
    def _seed(self, app):
        from tests.test_career_hub import _program as hub_program, _resource as hub_resource

        hub_resource(app, "hub-premium", access="premium")
        hub_resource(app, "hub-bonus", access="circle_only", level="yearly_members")
        hub_resource(app, "hub-free", access="direct_download")
        hub_program(app, "hub-paid-course", access="product", product=_product(app))
        hub_program(app, "hub-shop-service", access="product", product=_product(app, type="service"))

    def _cards(self, client, token=None):
        headers = auth_headers(token) if token else {}
        return {c["slug"]: c for c in client.get("/api/v1/career-hub", query_string={"pageSize": 24}, headers=headers).get_json()["data"]}

    def test_anonymous_cards_have_no_viewer_key(self, client, app):
        self._seed(app)
        cards = self._cards(client)
        assert all("viewer" not in c for c in cards.values())
        assert cards["hub-paid-course"]["circle"]["label"] == "Included with Lifetime WSF Circle"
        assert cards["hub-shop-service"]["circle"]["included"] is False

    def test_lifetime_sees_included_labels(self, client, app):
        self._seed(app)
        token, _uid = _member(app, client, "lifetime")
        cards = self._cards(client, token)
        for slug in ("hub-premium", "hub-bonus", "hub-paid-course"):
            assert cards[slug]["viewer"] == {"included": True, "label": "Included with your Lifetime membership"}, slug
        assert cards["hub-free"]["viewer"]["included"] is False
        assert cards["hub-shop-service"]["viewer"]["included"] is False

    @pytest.mark.parametrize("interval, bonus", [("monthly", False), ("yearly", True)])
    def test_monthly_yearly_labels_accurate(self, client, app, interval, bonus):
        self._seed(app)
        token, _uid = _member(app, client, interval)
        cards = self._cards(client, token)
        assert cards["hub-premium"]["viewer"]["label"] == "Included with your WSF Circle membership"
        assert cards["hub-bonus"]["viewer"]["included"] is bonus
        assert cards["hub-paid-course"]["viewer"]["included"] is False

    def test_query_count_constant_for_lifetime_viewer(self, client, app):
        from sqlalchemy import event

        from tests.test_career_hub import TestQueryCounts

        TestQueryCounts()._seed(app, 14)
        token, _uid = _member(app, client, "lifetime")
        counts = {}
        for label, headers, size in (("anon-4", {}, 4), ("anon-24", {}, 24), ("life-4", auth_headers(token), 4), ("life-24", auth_headers(token), 24)):
            # Each case runs twice; the second run excludes one-time loads
            # (e.g. the authenticated user row) so only per-page work counts.
            for _run in range(2):
                statements = []
                listener = lambda *args: statements.append(args[2])  # noqa: E731
                with app.app_context():
                    event.listen(db.engine, "before_cursor_execute", listener)
                try:
                    assert client.get("/api/v1/career-hub", query_string={"pageSize": size}, headers=headers).status_code == 200
                finally:
                    with app.app_context():
                        event.remove(db.engine, "before_cursor_execute", listener)
            counts[label] = len(statements)
        assert counts["anon-4"] == counts["anon-24"], counts
        assert counts["life-4"] == counts["life-24"], counts
        assert counts["life-24"] - counts["anon-24"] <= 4, counts  # auth + one tier lookup, not per card


# --- Founding capacity ------------------------------------------------------------------------


def _other_user(client, app, n):
    payload = {"email": f"founding{n}@example.com", "password": "supersecret1", "first_name": "F", "last_name": str(n)}
    token = _register(client, payload)
    from app.models.user import User

    with app.app_context():
        return token, User.query.filter_by(email=payload["email"]).first().id


def _verify(client, app, token, reference):
    with patch("app.services.circle_payments.verify_transaction", return_value=_success(_payment(app, reference))):
        return client.get(f"/api/v1/circle/payments/{reference}", headers=auth_headers(token))


class TestFoundingCapacity:
    def test_unlimited_plan_reports_no_limit(self, client, app):
        _plan(app, interval="lifetime")
        plan = client.get("/api/v1/circle/plans").get_json()["data"][0]
        assert plan["availability"] == {"limited": False, "maxMembers": None, "remaining": None, "full": False}
        assert plan["isFounding"] is False

    def test_remaining_seats_and_full_state(self, client, app):
        plan_id, slug = _plan(app, interval="lifetime", max_members=2, is_founding=True)
        _t1, u1 = _other_user(client, app, 1)
        _subscription(app, u1, plan_id)
        plan = client.get("/api/v1/circle/plans").get_json()["data"][0]
        assert plan["isFounding"] is True and plan["availability"] == {"limited": True, "maxMembers": 2, "remaining": 1, "full": False}
        _t2, u2 = _other_user(client, app, 2)
        _subscription(app, u2, plan_id)
        assert client.get("/api/v1/circle/plans").get_json()["data"][0]["availability"]["full"] is True

    def test_full_plan_blocks_checkout(self, client, app):
        _enable_paystack(app)
        plan_id, slug = _plan(app, interval="lifetime", max_members=1, is_founding=True)
        _t1, u1 = _other_user(client, app, 1)
        _subscription(app, u1, plan_id)
        token = _register(client, USER)
        resp, init = _checkout(client, token, slug)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "plan_full"
        assert resp.get_json()["error"]["message"] == "This founding offer is full."
        init.assert_not_called()

    def test_in_flight_checkout_holds_the_final_seat(self, client, app):
        _enable_paystack(app)
        plan_id, slug = _plan(app, interval="lifetime", max_members=1, is_founding=True)
        t1, _u1 = _other_user(client, app, 1)
        assert _checkout(client, t1, slug)[0].status_code in (200, 201)
        t2, _u2 = _other_user(client, app, 2)
        resp, init = _checkout(client, t2, slug)
        assert resp.status_code == 409 and resp.get_json()["error"]["code"] == "plan_full"

    def test_final_seat_activation_and_founding_snapshot(self, client, app):
        from app.models.circle import CirclePlan

        _enable_paystack(app)
        plan_id, slug = _plan(app, interval="lifetime", max_members=1, is_founding=True)
        token = _register(client, USER)
        resp, init = _checkout(client, token, slug)
        reference = init.call_args.kwargs["reference"]
        assert _verify(client, app, token, reference).get_json()["data"]["membershipActivated"] is True
        sub = _current(app, _user(app).id)
        assert sub.founding_lifetime is True and sub.current_period_end is None
        # Renaming/un-flagging the plan later never removes the snapshot.
        with app.app_context():
            plan = db.session.get(CirclePlan, plan_id)
            plan.name = "Lifetime (renamed)"
            plan.is_founding = False
            db.session.commit()
        me = client.get("/api/v1/circle/me", headers=auth_headers(token)).get_json()["data"]
        assert me["subscription"]["memberBadge"] == "Founding Lifetime Member"
        # Duplicate callback stays idempotent.
        assert _verify(client, app, token, reference).get_json()["data"]["status"] == "consumed"

    def test_full_plan_blocks_activation_of_a_verified_payment(self, client, app):
        _enable_paystack(app)
        plan_id, slug = _plan(app, interval="lifetime", max_members=1, is_founding=True)
        token = _register(client, USER)
        resp, init = _checkout(client, token, slug)
        reference = init.call_args.kwargs["reference"]
        # Someone else takes the last seat (e.g. staff) before verification.
        _t1, u1 = _other_user(client, app, 1)
        _subscription(app, u1, plan_id)
        data = _verify(client, app, token, reference).get_json()["data"]
        assert data["membershipActivated"] is False and data["status"] == "verified"
        assert _current(app, _user(app).id) is None

    def test_concurrent_final_seat_only_one_wins(self, client, app):
        from app.models.circle import CirclePayment, CircleSubscription
        from app.services.circle_payments import consume_verified_circle_payment

        plan_id, _slug = _plan(app, interval="lifetime", max_members=1, is_founding=True)
        references = []
        for n in (1, 2):
            _t, uid = _other_user(client, app, n)
            with app.app_context():
                ref = f"wsfcircle-{uuid.uuid4().hex}"
                db.session.add(CirclePayment(reference=ref, user_id=uid, plan_id=plan_id, amount_subunits=29900, currency="USD",
                                             billing_interval="lifetime", customer_email=f"founding{n}@example.com", status="verified",
                                             provider_snapshot={"status": "success"}))
                db.session.commit()
            references.append(ref)
        outcomes = []
        barrier = threading.Barrier(2)

        def worker(ref):
            with app.app_context():
                barrier.wait()
                try:
                    outcomes.append(consume_verified_circle_payment(ref)["outcome"])
                finally:
                    db.session.remove()

        threads = [threading.Thread(target=worker, args=(r,)) for r in references]
        for t in threads:
            t.start()
        for t in threads:
            t.join(30)
        assert sorted(outcomes) == ["consumed", "membership_conflict"], outcomes
        with app.app_context():
            assert CircleSubscription.query.filter_by(plan_id=plan_id).count() == 1

    def test_revoked_membership_frees_a_seat(self, client, app):
        from app.models.circle import CircleSubscription

        plan_id, _slug = _plan(app, interval="lifetime", max_members=1)
        _t1, u1 = _other_user(client, app, 1)
        sub_id = _subscription(app, u1, plan_id)
        assert client.get("/api/v1/circle/plans").get_json()["data"][0]["availability"]["full"] is True
        with app.app_context():
            db.session.get(CircleSubscription, sub_id).status = "revoked"
            db.session.commit()
        assert client.get("/api/v1/circle/plans").get_json()["data"][0]["availability"]["remaining"] == 1

    def test_founding_only_on_lifetime_and_capacity_validation(self, client, app, admin_headers):
        bad = client.post("/api/v1/circle/plans", json={"name": "F", "billingInterval": "yearly", "currency": "USD", "isFounding": True}, headers=admin_headers)
        assert bad.status_code == 422
        assert client.post("/api/v1/circle/plans", json={"name": "Z", "currency": "USD", "maxMembers": 0}, headers=admin_headers).status_code == 422
        ok = client.post("/api/v1/circle/plans", json={"name": "Founding", "billingInterval": "lifetime", "currency": "USD",
                                                       "isFounding": True, "maxMembers": 100}, headers=admin_headers)
        assert ok.status_code == 201 and ok.get_json()["data"]["max_members"] == 100
        slug = ok.get_json()["data"]["slug"]
        cleared = client.patch(f"/api/v1/circle/plans/{slug}", json={"maxMembers": None}, headers=admin_headers)
        assert cleared.status_code == 200 and cleared.get_json()["data"]["max_members"] is None

    def test_admin_cannot_oversell_and_snapshot_on_manual_create(self, client, app, admin_headers):
        plan_id, _slug = _plan(app, interval="lifetime", max_members=1, is_founding=True)
        _register(client, USER)
        resp = client.post("/api/v1/circle/subscriptions", json={"email": USER["email"], "planId": plan_id, "status": "active", "source": "manual"}, headers=admin_headers)
        assert resp.status_code == 201 and resp.get_json()["data"]["founding_lifetime"] is True
        assert resp.get_json()["data"]["memberBadge"] == "Founding Lifetime Member"
        _t, _u = _other_user(client, app, 9)
        again = client.post("/api/v1/circle/subscriptions", json={"email": "founding9@example.com", "planId": plan_id, "status": "active", "source": "manual"}, headers=admin_headers)
        assert again.status_code == 409 and again.get_json()["error"]["code"] == "plan_full"


@pytest.fixture()
def admin_headers(client, app):
    from app.models.user import Role, User

    payload = {"email": "founding-admin@example.com", "password": "supersecret1", "first_name": "A", "last_name": "D"}
    client.post("/api/v1/auth/register", json=payload)
    with app.app_context():
        user = User.query.filter_by(email=payload["email"]).first()
        user.roles.append(Role.query.filter_by(name="admin").first())
        db.session.commit()
    token = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]}).get_json()["data"]["access_token"]
    return auth_headers(token)


# --- badges -----------------------------------------------------------------------------------


class TestBadges:
    @pytest.mark.parametrize("interval, founding, status, badge", [
        ("monthly", False, "active", None), ("yearly", False, "active", None), ("lifetime", False, "active", "Lifetime Member"),
        ("lifetime", True, "active", "Founding Lifetime Member"), ("lifetime", True, "revoked", None), ("lifetime", False, "cancelled", None),
    ])
    def test_badge_rules(self, client, app, interval, founding, status, badge):
        token, uid = _member(app, client, interval, status=status, founding_lifetime=founding)
        me = client.get("/api/v1/circle/me", headers=auth_headers(token)).get_json()["data"]
        assert (me["subscription"] or {}).get("memberBadge") == badge
        assert me["lifetimeAccess"] is (badge is not None)


# --- checkout regressions ---------------------------------------------------------------------


class TestCheckoutRegression:
    def test_lifetime_checkout_still_works_on_unlimited_plan(self, client, app):
        _enable_paystack(app)
        _pid, slug = _plan(app, interval="lifetime")
        token = _register(client, USER)
        resp, init = _checkout(client, token, slug)
        reference = init.call_args.kwargs["reference"]
        assert _verify(client, app, token, reference).get_json()["data"]["membershipActivated"] is True
        assert _current(app, _user(app).id).founding_lifetime is False

    def test_active_lifetime_cannot_repurchase_and_recurring_cannot_self_upgrade(self, client, app):
        _enable_paystack(app)
        token, uid = _member(app, client, "lifetime")
        _pid, slug = _plan(app, interval="lifetime")
        assert _checkout(client, token, slug)[0].get_json()["error"]["code"] == "lifetime_membership_active"
