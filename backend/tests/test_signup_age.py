"""Step 18: minimum age at signup (default 16, Studio-configurable 16–21),
confirmed by an explicit checkbox; nothing stored without it; the
confirmation time and the Terms/Privacy versions accepted are recorded."""
from datetime import date

from app.extensions import db
from app.models.cms import SiteSetting
from app.models.page import Page
from app.models.user import Role, User
from app.services.account_policy import ACCOUNT_POLICY_KEY, get_account_policy, legal_document_version
from tests.conftest import RAW_REGISTER_HEADER, auth_headers

BASE = {"email": "teen@example.com", "password": "supersecret1", "first_name": "Ada", "last_name": "L"}
RAW = {RAW_REGISTER_HEADER: "1"}


def _users(app):
    with app.app_context():
        return User.query.filter_by(email="teen@example.com").count()


def test_missing_confirmation_blocks_before_storing(client, app):
    res = client.post("/api/v1/auth/register", json=BASE, headers=RAW)
    assert res.status_code == 422
    body = res.get_json()
    assert body["error"]["code"] == "age_confirmation_required"
    assert "at least 16 years old" in body["error"]["message"]
    assert _users(app) == 0
    assert "wsf_refresh" not in (res.headers.get("Set-Cookie") or "")


def test_only_json_true_counts(client, app, monkeypatch):
    from app.extensions import limiter
    monkeypatch.setattr(limiter, "enabled", False)  # 8 signups > 5/min limit
    for value in (False, None, "yes", "true", 1, "on", [True], {}):
        res = client.post("/api/v1/auth/register", json={**BASE, "age_confirmed": value})
        assert res.status_code == 422, value
        assert res.get_json()["error"]["code"] == "age_confirmation_required"
    assert _users(app) == 0


def test_gate_runs_before_duplicate_email_check(client, app):
    assert client.post("/api/v1/auth/register", json={**BASE, "age_confirmed": True}).status_code == 201
    res = client.post("/api/v1/auth/register", json=BASE, headers=RAW)
    # No account lookup happens without the confirmation, so the response
    # doesn't reveal that the address is registered.
    assert res.status_code == 422
    assert res.get_json()["error"]["code"] == "age_confirmation_required"


def test_confirmation_and_versions_stored(client, app):
    with app.app_context():
        db.session.add(Page(key="terms", slug="terms", title="Terms", status="published",
                            content=[], effective_date=date(2026, 1, 1)))
        db.session.commit()
    res = client.post("/api/v1/auth/register", json={**BASE, "age_confirmed": True})
    assert res.status_code == 201
    with app.app_context():
        user = User.query.filter_by(email="teen@example.com").one()
        assert user.age_confirmed_at is not None
        assert user.legal_accepted_at == user.age_confirmed_at
        assert user.age_confirmed_minimum == 16
        assert user.terms_version_accepted.startswith("terms:2026-01-01@")
        assert user.terms_version_accepted == legal_document_version("terms")
        assert user.privacy_version_accepted == "privacy:unpublished"
    # Not part of the general user dump; present in the member's own export.
    token = res.get_json()["data"]["access_token"]
    me = client.get("/api/v1/auth/me", headers=auth_headers(token)).get_json()["data"]
    assert "age_confirmed_at" not in str(me)
    export = client.get("/api/v1/account/export", headers=auth_headers(token))
    account = export.get_json()["account"] if "account" in (export.get_json() or {}) else export.get_json()["data"]["account"]
    assert account["age_confirmed_minimum"] == 16
    assert account["terms_version_accepted"].startswith("terms:2026-01-01@")
    assert account["age_confirmed_at"]


def test_no_date_of_birth_collected(client, app):
    res = client.post("/api/v1/auth/register", json={**BASE, "age_confirmed": True, "date_of_birth": "2000-01-01"})
    # Unknown fields are rejected by the schema rather than stored.
    assert res.status_code == 422
    assert not hasattr(User, "date_of_birth")


def _super_admin_token(client, app):
    client.post("/api/v1/auth/register", json={"email": "boss@example.com", "password": "supersecret1",
                                                "first_name": "B", "last_name": "S"})
    with app.app_context():
        user = User.query.filter_by(email="boss@example.com").one()
        user.roles.append(Role.query.filter_by(name="super_admin").one())
        db.session.commit()
    return client.post("/api/v1/auth/login", json={"email": "boss@example.com", "password": "supersecret1"}) \
        .get_json()["data"]["access_token"]


def test_studio_setting_bounded_and_audited(client, app, monkeypatch):
    monkeypatch.setattr("app.services.two_factor.is_required", lambda user: False)
    token = _super_admin_token(client, app)
    h = auth_headers(token)
    got = client.get("/api/v1/admin/settings", headers=h).get_json()["data"][ACCOUNT_POLICY_KEY]
    assert got == {"minimumAge": 16, "bounds": {"min": 16, "max": 21, "default": 16}}
    for bad in (15, 22, "18", True, 17.5, None):
        res = client.put("/api/v1/admin/settings", headers=h, json={"settings": {ACCOUNT_POLICY_KEY: {"minimumAge": bad}}})
        assert res.status_code == 422, bad
    res = client.put("/api/v1/admin/settings", headers=h, json={"settings": {ACCOUNT_POLICY_KEY: {"minimumAge": 18}}})
    assert res.status_code == 200
    assert res.get_json()["data"][ACCOUNT_POLICY_KEY]["minimumAge"] == 18
    with app.app_context():
        assert get_account_policy() == {"minimumAge": 18}
        from app.models.audit import AuditLog
        assert AuditLog.query.filter_by(action="settings.update", entity_id=ACCOUNT_POLICY_KEY).count() == 1
    # Public settings carry only the minimum age; signup uses the new value.
    public = client.get("/api/v1/public/settings").get_json()["data"]
    assert public["accountPolicy"] == {"minimumAge": 18}
    res = client.post("/api/v1/auth/register", json=BASE, headers=RAW)
    assert "at least 18 years old" in res.get_json()["error"]["message"]
    assert client.post("/api/v1/auth/register", json={**BASE, "age_confirmed": True}).status_code == 201
    with app.app_context():
        assert User.query.filter_by(email="teen@example.com").one().age_confirmed_minimum == 18


def test_corrupt_stored_value_falls_back_to_default(app):
    with app.app_context():
        db.session.add(SiteSetting(key=ACCOUNT_POLICY_KEY, value={"minimumAge": 3}))
        db.session.commit()
        assert get_account_policy() == {"minimumAge": 16}


def test_legal_audit_reports_the_minimum_age(app):
    from app.services.legal_audit import implementation_facts

    with app.app_context():
        text = " ".join(line for section, line in implementation_facts() if section == "Account")
        assert "Minimum age at signup: 16" in text
        assert "no date of birth" in text
