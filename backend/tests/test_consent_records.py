"""Account-linked cookie-consent records (app/api/v1/consent.py)."""
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models.consent import ConsentRecord
from tests.conftest import auth_headers

MEMBER = {"email": "consent-member@example.com", "password": "supersecret1", "first_name": "C", "last_name": "M"}


def _register(client, data=MEMBER):
    res = client.post("/api/v1/auth/register", json=data)
    assert res.status_code == 201
    return res.get_json()["data"]["access_token"]


def _decision(**overrides):
    body = {"consentVersion": "1", "preferences": False, "analytics": True, "marketing": False,
            "decidedAt": "2026-11-23T10:00:00.000Z"}
    body.update(overrides)
    return body


def test_anonymous_visitors_cannot_record(client):
    assert client.post("/api/v1/consent", json=_decision()).status_code == 401
    assert client.get("/api/v1/consent/me").status_code == 401


def test_member_decision_is_recorded_without_ip_and_repeat_is_idempotent(client, app):
    token = _register(client)
    first = client.post("/api/v1/consent", json=_decision(), headers=auth_headers(token))
    assert first.status_code == 201
    data = first.get_json()["data"]
    assert data == {**data, "consentVersion": "1", "preferences": False, "analytics": True, "marketing": False}
    # The same decision again (reload, second tab, sign-in sync) adds nothing.
    assert client.post("/api/v1/consent", json=_decision(), headers=auth_headers(token)).status_code == 200
    # A new decision is a new history row.
    assert client.post("/api/v1/consent", json=_decision(analytics=False, decidedAt="2026-11-23T11:00:00Z"),
                       headers=auth_headers(token)).status_code == 201
    with app.app_context():
        rows = ConsentRecord.query.all()
        assert len(rows) == 2
        columns = set(ConsentRecord.__table__.columns.keys())
        assert not {"ip", "ip_address", "user_agent", "ip_hash"} & columns
    history = client.get("/api/v1/consent/me", headers=auth_headers(token)).get_json()["data"]
    assert [h["analytics"] for h in history] == [False, True]  # newest first


def test_history_is_private_to_each_member(client):
    a = _register(client)
    b = _register(client, {**MEMBER, "email": "consent-other@example.com"})
    client.post("/api/v1/consent", json=_decision(), headers=auth_headers(a))
    assert client.get("/api/v1/consent/me", headers=auth_headers(b)).get_json()["data"] == []


def test_invalid_or_stale_decisions_are_rejected(client):
    token = _register(client)
    headers = auth_headers(token)
    assert client.post("/api/v1/consent", json=_decision(consentVersion="0"), headers=headers).status_code == 409
    assert client.post("/api/v1/consent", json=_decision(analytics="yes"), headers=headers).status_code == 422
    assert client.post("/api/v1/consent", json=_decision(decidedAt="not a date"), headers=headers).status_code == 422
    future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    assert client.post("/api/v1/consent", json=_decision(decidedAt=future), headers=headers).status_code == 422
    assert client.post("/api/v1/consent", json=["x"], headers=headers).status_code == 422


def test_records_survive_account_removal_without_the_link(client, app):
    from app.models.user import User

    token = _register(client)
    client.post("/api/v1/consent", json=_decision(), headers=auth_headers(token))
    with app.app_context():
        user = User.query.filter_by(email=MEMBER["email"]).first()
        db.session.execute(db.text("DELETE FROM user_roles WHERE user_id = :id"), {"id": user.id})
        db.session.execute(db.text("DELETE FROM audit_logs WHERE user_id = :id"), {"id": user.id})
        db.session.execute(db.text("DELETE FROM users WHERE id = :id"), {"id": user.id})
        db.session.commit()
        row = ConsentRecord.query.one()
        assert row.user_id is None


def test_gpc_request_is_recorded_as_marketing_false_and_history_is_kept(client, app):
    token = _register(client)
    headers = auth_headers(token)
    # Yesterday, without GPC: Marketing allowed.
    assert client.post("/api/v1/consent", json=_decision(marketing=True, decidedAt="2026-11-22T10:00:00Z"),
                       headers=headers).status_code == 201
    # Today the browser sends GPC: even a payload claiming Marketing=true is stored as false.
    res = client.post("/api/v1/consent", json=_decision(preferences=True, analytics=True, marketing=True,
                                                         decidedAt="2026-11-23T10:00:00Z"),
                      headers={**headers, "Sec-GPC": "1"})
    assert res.status_code == 201
    assert res.get_json()["data"] == {**res.get_json()["data"], "preferences": True, "analytics": True, "marketing": False}
    history = client.get("/api/v1/consent/me", headers=headers).get_json()["data"]
    assert [(h["decidedAt"][:10], h["marketing"]) for h in history] == [("2026-11-23", False), ("2026-11-22", True)]
