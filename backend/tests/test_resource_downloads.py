"""Focused tests for Module 10, part A — protected circle_only Resource
downloads (app/services/resource_downloads.py, app/api/v1/resources.py's
ResourceDownloadResource). Entitlement itself is never re-derived here —
every "should this be allowed" assertion traces back to
app/services/circle.py's has_circle_access(), exactly as production code
does; this file is about the token mechanism layered on top of an
already-correct entitlement decision.
"""
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

from tests.conftest import auth_headers

USER_A = {
    "email": "resdl-user-a@example.com", "password": "supersecret1",
    "first_name": "Amina", "last_name": "Diallo", "country_code": "SN",
}
USER_B = {
    "email": "resdl-user-b@example.com", "password": "supersecret1",
    "first_name": "Beatrice", "last_name": "Mwangi", "country_code": "NG",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def user_a_token(client):
    return _register(client, USER_A)


@pytest.fixture()
def user_b_token(client):
    return _register(client, USER_B)


def _resolve_user(email):
    from app.models.user import User

    return User.query.filter_by(email=email).first()


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _make_circle_resource(app, protected_root, filename, content=b"%PDF-1.4 fake pdf body", **overrides):
    """A published circle_only Resource whose real file is written to
    `protected_root` (never MEDIA_ROOT) — the exact production shape
    (Resource.protected_file_path + a file that actually exists there).
    """
    from app.extensions import db
    from app.models.resource import Resource

    (protected_root / filename).write_bytes(content)
    defaults = dict(
        slug=overrides.pop("slug", None) or _slug("circle-resource"),
        name="Circle Workbook",
        access_type="circle_only",
        protected_file_path=filename,
        status="published",
        published_date=date.today(),
        description=[{"type": "paragraph", "text": "Members-only workbook."}],
        price=0,
        currency="USD",
    )
    defaults.update(overrides)
    with app.app_context():
        resource = Resource(**defaults)
        db.session.add(resource)
        db.session.commit()
        return resource.id, resource.slug


def _make_plan(app):
    from app.extensions import db
    from app.models.circle import CirclePlan

    with app.app_context():
        plan = CirclePlan(
            slug=_slug("circle-plan"), name="WSF Circle Membership",
            billing_interval="monthly", price=1000, currency="USD", status="active",
        )
        db.session.add(plan)
        db.session.commit()
        return plan.id


def _give_active_circle(app, email):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    plan_id = _make_plan(app)
    with app.app_context():
        user = _resolve_user(email)
        subscription = CircleSubscription(user_id=user.id, plan_id=plan_id, status="active", source="manual")
        db.session.add(subscription)
        db.session.commit()
        return subscription.id


def _expire_subscription(app, subscription_id):
    from app.extensions import db
    from app.models.circle import CircleSubscription

    with app.app_context():
        sub = db.session.get(CircleSubscription, subscription_id)
        sub.status = "expired"
        db.session.commit()


def _issue_token_for(app, resource_id, email):
    """Bypasses the HTTP layer to mint a token directly against the
    service — used only by the tamper/expiry/cross-resource tests below,
    which need to manipulate the token or its row in ways a real client
    never could. Every "real" grant test goes through POST /access.
    """
    from app.extensions import db
    from app.models.resource import Resource
    from app.services.resource_downloads import issue_download_token

    with app.app_context():
        resource = Resource.query.get(resource_id)
        user = _resolve_user(email)
        return issue_download_token(resource, user)


@pytest.fixture()
def protected_root(app, tmp_path):
    root = tmp_path / "protected_media"
    root.mkdir()
    app.config["PROTECTED_MEDIA_ROOT"] = str(root)
    return root


# ===========================================================================
# 1-2: anonymous / signed-in non-member denied — no token ever issued
# ===========================================================================


def test_1_anonymous_denied_at_access_endpoint(app, client, protected_root):
    _, slug = _make_circle_resource(app, protected_root, "workbook.pdf")
    resp = client.post(f"/api/v1/resources/{slug}/access")
    assert resp.status_code == 401


def test_2_signed_in_non_member_denied_at_access_endpoint(app, client, protected_root, user_a_token):
    _, slug = _make_circle_resource(app, protected_root, "workbook.pdf")
    resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403


# ===========================================================================
# 3: active Circle member allowed — real end-to-end grant + download
# ===========================================================================


def test_3_active_circle_member_allowed_end_to_end(app, client, protected_root, user_a_token):
    _give_active_circle(app, USER_A["email"])
    _, slug = _make_circle_resource(app, protected_root, "workbook.pdf", content=b"the real workbook bytes")

    access_resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user_a_token))
    assert access_resp.status_code == 200
    data = access_resp.get_json()["data"]
    assert data["accessType"] == "circle_only"
    url = data["url"]
    assert url.startswith("/api/v1/resources/downloads/")
    # Never the raw storage path/filename, never a /media/ URL.
    assert "workbook.pdf" not in url
    assert "/media/" not in url

    download_resp = client.get(url)
    assert download_resp.status_code == 200
    assert download_resp.data == b"the real workbook bytes"


# ===========================================================================
# 4: expired member denied — existing entitlement check, unaffected
# ===========================================================================


def test_4_expired_member_denied_at_access_endpoint(app, client, protected_root, user_a_token):
    sub_id = _give_active_circle(app, USER_A["email"])
    _expire_subscription(app, sub_id)
    _, slug = _make_circle_resource(app, protected_root, "workbook.pdf")

    resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 403


# ===========================================================================
# 5-6: tampered / expired token denied
# ===========================================================================


def test_5_tampered_token_denied(app, client, protected_root):
    _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    resource_id, _ = _make_circle_resource(app, protected_root, "workbook.pdf")
    raw_token = _issue_token_for(app, resource_id, USER_A["email"])
    tampered = raw_token[:-1] + ("a" if raw_token[-1] != "a" else "b")
    resp = client.get(f"/api/v1/resources/downloads/{tampered}")
    assert resp.status_code == 404


def test_6_expired_token_denied(app, client, protected_root):
    from app.extensions import db
    from app.models.resource import ResourceDownloadToken

    _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    resource_id, _ = _make_circle_resource(app, protected_root, "workbook.pdf")
    raw_token = _issue_token_for(app, resource_id, USER_A["email"])
    with app.app_context():
        import hashlib

        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        token = ResourceDownloadToken.query.filter_by(token_hash=token_hash).first()
        token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.session.commit()

    resp = client.get(f"/api/v1/resources/downloads/{raw_token}")
    assert resp.status_code == 404


# ===========================================================================
# 7: Resource A's token cannot retrieve Resource B's file
# ===========================================================================


def test_7_resource_a_token_cannot_retrieve_resource_b(app, client, protected_root):
    _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    resource_a_id, _ = _make_circle_resource(app, protected_root, "workbook-a.pdf", content=b"AAAA resource A content")
    resource_b_id, _ = _make_circle_resource(app, protected_root, "workbook-b.pdf", content=b"BBBB resource B content")

    token_a = _issue_token_for(app, resource_a_id, USER_A["email"])
    token_b = _issue_token_for(app, resource_b_id, USER_A["email"])

    resp_a = client.get(f"/api/v1/resources/downloads/{token_a}")
    resp_b = client.get(f"/api/v1/resources/downloads/{token_b}")
    assert resp_a.data == b"AAAA resource A content"
    assert resp_b.data == b"BBBB resource B content"
    assert resp_a.data != resp_b.data


# ===========================================================================
# 8: traversal attempts fail
# ===========================================================================


def test_8_path_traversal_in_protected_file_path_is_refused(app, client, protected_root):
    """A resource whose protected_file_path was somehow set to a
    traversal string (bypassing the schema-layer validator — e.g. a
    pre-existing row, or a future bug elsewhere) must still never let
    the download route escape PROTECTED_MEDIA_ROOT. resolve_download_token
    refuses it outright via is_safe_protected_path(); send_from_directory
    would refuse it independently even if that check were ever removed.
    """
    from app.extensions import db
    from app.models.resource import Resource

    _register(client, USER_A)
    _give_active_circle(app, USER_A["email"])
    # A real secret file OUTSIDE protected_root, one directory up.
    secret = protected_root.parent / "secret.txt"
    secret.write_text("should never be served")

    with app.app_context():
        resource = Resource(
            slug=_slug("traversal-resource"), name="Traversal Resource", access_type="circle_only",
            protected_file_path="../secret.txt", status="published", published_date=date.today(),
            description=[{"type": "paragraph", "text": "Body."}], price=0, currency="USD",
        )
        db.session.add(resource)
        db.session.commit()
        resource_id = resource.id

    token = _issue_token_for(app, resource_id, USER_A["email"])
    resp = client.get(f"/api/v1/resources/downloads/{token}")
    assert resp.status_code == 404
    assert b"should never be served" not in resp.data


def test_9_traversal_rejected_at_save_time_by_schema(app, client, user_a_token):
    """The admin editor itself refuses to save a traversal path in the
    first place — defense in depth, not the only line of defense (see
    test_8 above for the route-level one).
    """
    from app.extensions import db
    from app.models.user import Role, User

    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        role = Role.query.filter_by(name="resources_manager").first()
        user.roles.append(role)
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": USER_A["email"], "password": USER_A["password"]})
    manager_token = login.get_json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/resources",
        json={
            "name": "Bad Resource", "accessType": "circle_only", "protectedFilePath": "../../etc/passwd",
            "status": "draft",
        },
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


# ===========================================================================
# 10: normal public resources continue to work (regression)
# ===========================================================================


def test_10_direct_download_resource_still_returns_raw_file_url(app, client):
    from app.extensions import db
    from app.models.resource import Resource

    with app.app_context():
        resource = Resource(
            slug=_slug("public-resource"), name="Public Guide", access_type="direct_download",
            file_url="https://cdn.example.com/public-guide.pdf", status="published", published_date=date.today(),
            description=[{"type": "paragraph", "text": "Body."}], price=0, currency="USD",
        )
        db.session.add(resource)
        db.session.commit()
        slug = resource.slug

    resp = client.post(f"/api/v1/resources/{slug}/access")
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["url"] == "https://cdn.example.com/public-guide.pdf"
    assert data["accessType"] == "direct_download"


def test_11_circle_only_with_only_external_url_still_returns_it_directly(app, client, user_a_token):
    """A circle_only resource that intentionally has no protected_file_path
    — only an explicit external_url — keeps working exactly as before
    this module (spec: "existing genuinely public resource modes remain
    public unless a change is technically required" + an explicit
    non-WSF-hosted link is still a legitimate circle_only configuration).
    """
    from app.extensions import db
    from app.models.resource import Resource

    _give_active_circle(app, USER_A["email"])
    with app.app_context():
        resource = Resource(
            slug=_slug("circle-external"), name="Circle External Resource", access_type="circle_only",
            external_url="https://partner.example.com/circle-only-guide", status="published",
            published_date=date.today(), description=[{"type": "paragraph", "text": "Body."}],
            price=0, currency="USD",
        )
        db.session.add(resource)
        db.session.commit()
        slug = resource.slug

    resp = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(user_a_token))
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["url"] == "https://partner.example.com/circle-only-guide"


def test_12_circle_only_file_url_alone_no_longer_satisfies_publish(app, client, user_a_token):
    """A circle_only resource configured the OLD way (file_url pointing
    into the public /media/ tree, no protected_file_path) can no longer
    be published — the exact gap this module closes.
    """
    from app.models.user import Role, User
    from app.extensions import db

    with app.app_context():
        user = User.query.filter_by(email=USER_A["email"]).first()
        role = Role.query.filter_by(name="resources_manager").first()
        user.roles.append(role)
        db.session.commit()
    login = client.post("/api/v1/auth/login", json={"email": USER_A["email"], "password": USER_A["password"]})
    manager_token = login.get_json()["data"]["access_token"]

    resp = client.post(
        "/api/v1/resources",
        json={
            "name": "Old-Style Circle Resource", "accessType": "circle_only", "fileUrl": "/media/circle-file.pdf",
            "description": [{"type": "paragraph", "text": "Body."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422
