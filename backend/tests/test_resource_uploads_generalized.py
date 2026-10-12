"""Focused tests for generalizing WSF-hosted protected-file delivery
beyond circle_only. direct_download/email_gate/member_only Resources can
now also use an uploaded `protected_file_path`, served through the same
short-lived download token circle_only already used — including for an
anonymous visitor, since ResourceDownloadToken.user_id is now nullable.
See app/models/resource.py's PROTECTED_FILE_ELIGIBLE_ACCESS_TYPES,
app/services/resource_downloads.py's issue_download_token()/
resolve_download_token(), and app/api/v1/resources.py's
_resolve_target_url()/_validate_publish().

Existing circle_only coverage (test_resource_downloads.py,
test_resources_access.py, test_resource_protected_uploads.py) is not
duplicated here — this file is specifically about the generalization:
the other three access types gaining the same capability, circle_only
never gaining a fallback it didn't have before, and legacy file_url/
external_url behavior staying exactly as it was.
"""
import hashlib
import io
import uuid
from datetime import date

import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "resgen-manager@example.com", "password": "supersecret1",
    "first_name": "Folake", "last_name": "Adeyemi", "country_code": "NG",
}
MEMBER_PAYLOAD = {
    "email": "resgen-member@example.com", "password": "supersecret1",
    "first_name": "Wanjiru", "last_name": "Kamau", "country_code": "KE",
}


def _register(client, payload):
    client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    return login.get_json()["data"]["access_token"]


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
def member_token(client):
    return _register(client, MEMBER_PAYLOAD)


@pytest.fixture()
def protected_root(app, tmp_path):
    root = tmp_path / "protected_media"
    root.mkdir()
    app.config["PROTECTED_MEDIA_ROOT"] = str(root)
    return root


def _slug(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _pdf_bytes():
    return b"%PDF-1.4\n% fake but correctly-headered pdf body\n%%EOF"


def _upload(client, token, filename, content):
    return client.post(
        "/api/v1/resources/uploads/protected",
        data={"file": (io.BytesIO(content), filename)},
        content_type="multipart/form-data",
        headers=auth_headers(token),
    )


def _create_resource(client, token, **overrides):
    payload = {
        "name": overrides.pop("name", "Generalized Upload Resource"),
        "description": [{"type": "paragraph", "text": "Body."}],
        "status": overrides.pop("status", "published"),
    }
    payload.update(overrides)
    return client.post("/api/v1/resources", json=payload, headers=auth_headers(token))


def _token_hash(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _token_row(app, raw_token):
    from app.models.resource import ResourceDownloadToken

    with app.app_context():
        return ResourceDownloadToken.query.filter_by(token_hash=_token_hash(raw_token)).first()


def _tokens_for_resource(app, resource_id):
    from app.models.resource import ResourceDownloadToken

    with app.app_context():
        return ResourceDownloadToken.query.filter_by(resource_id=resource_id).all()


# ===========================================================================
# A. direct_download with an uploaded protected file
# ===========================================================================


def test_a1_anonymous_direct_download_uploaded_file_end_to_end(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "Free Guide.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]

    create = _create_resource(
        client, manager_token, accessType="direct_download", protectedFilePath=path,
        protectedOriginalFilename="Free Guide.pdf",
    )
    assert create.status_code == 201
    slug = create.get_json()["data"]["slug"]
    resource_id = create.get_json()["data"]["id"]

    access = client.post(f"/api/v1/resources/{slug}/access")
    assert access.status_code == 200
    data = access.get_json()["data"]
    assert data["accessType"] == "direct_download"
    url = data["url"]
    assert url.startswith("/api/v1/resources/downloads/")
    assert "Free Guide" not in url

    download = client.get(url)
    assert download.status_code == 200
    assert download.data == _pdf_bytes()
    assert "Free Guide.pdf" in download.headers.get("Content-Disposition", "")

    raw_token = url.rsplit("/", 1)[-1]
    row = _token_row(client.application, raw_token)
    assert row is not None
    assert row.user_id is None
    assert row.resource_id == resource_id


# ===========================================================================
# B. email_gate with an uploaded protected file
# ===========================================================================


def test_b1_email_gate_missing_email_grants_no_token_and_does_not_increment_count(
    app, client, manager_token, protected_root
):
    upload = _upload(client, manager_token, "Lead Magnet.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_resource(client, manager_token, accessType="email_gate", protectedFilePath=path)
    resource_id = create.get_json()["data"]["id"]
    slug = create.get_json()["data"]["slug"]

    resp = client.post(f"/api/v1/resources/{slug}/access", json={})
    assert resp.status_code == 422

    with app.app_context():
        from app.extensions import db
        from app.models.resource import Resource

        assert db.session.get(Resource, resource_id).download_count == 0
    assert _tokens_for_resource(app, resource_id) == []


def test_b2_email_gate_valid_anonymous_email_creates_lead_and_downloads(app, client, manager_token, protected_root):
    upload = _upload(client, manager_token, "Lead Magnet.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_resource(client, manager_token, accessType="email_gate", protectedFilePath=path)
    slug = create.get_json()["data"]["slug"]

    resp = client.post(f"/api/v1/resources/{slug}/access", json={"email": "leadmagnet@example.com"})
    assert resp.status_code == 201
    url = resp.get_json()["data"]["url"]
    assert url.startswith("/api/v1/resources/downloads/")

    with app.app_context():
        from app.models.resource import ResourceLead

        assert ResourceLead.query.filter_by(email="leadmagnet@example.com").first() is not None

    download = client.get(url)
    assert download.status_code == 200
    assert download.data == _pdf_bytes()


# ===========================================================================
# C. member_only with an uploaded protected file
# ===========================================================================


def test_c1_anonymous_member_only_uploaded_file_denied(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "Members Workbook.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_resource(client, manager_token, accessType="member_only", protectedFilePath=path)
    slug = create.get_json()["data"]["slug"]

    resp = client.post(f"/api/v1/resources/{slug}/access")
    assert resp.status_code == 401


def test_c2_authenticated_member_only_uploaded_file_succeeds_and_downloads(
    client, manager_token, member_token, protected_root
):
    upload = _upload(client, manager_token, "Members Workbook.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_resource(client, manager_token, accessType="member_only", protectedFilePath=path)
    slug = create.get_json()["data"]["slug"]

    access = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(member_token))
    assert access.status_code == 200
    url = access.get_json()["data"]["url"]

    download = client.get(url)
    assert download.status_code == 200
    assert download.data == _pdf_bytes()


# ===========================================================================
# D. circle_only: still never falls back to file_url/external_url, even
# when both are also present on the row (the generalized _resolve_target_
# url() must still special-case it, not just happen to work).
# ===========================================================================


def test_d1_circle_only_ignores_file_url_even_when_both_configured(app, client, manager_token, protected_root):
    from app.extensions import db
    from app.models.circle import CirclePlan, CircleSubscription
    from app.models.resource import Resource
    from app.models.user import User

    (protected_root / "circle-only.pdf").write_bytes(b"the real circle-protected bytes")
    with app.app_context():
        resource = Resource(
            slug=_slug("circle-both-targets"), name="Circle Both Targets", access_type="circle_only",
            protected_file_path="circle-only.pdf", file_url="https://cdn.example.com/should-never-be-returned.pdf",
            status="published", published_date=date.today(),
            description=[{"type": "paragraph", "text": "Body."}],
        )
        db.session.add(resource)
        db.session.commit()
        slug = resource.slug

        plan = CirclePlan(slug=_slug("plan"), name="Circle", billing_interval="monthly", price=1000, currency="USD", status="active")
        db.session.add(plan)
        db.session.commit()
        member_token = _register(client, {"email": "resgen-circle-member@example.com", "password": "supersecret1", "first_name": "Zara", "last_name": "N", "country_code": "TZ"})
        user = User.query.filter_by(email="resgen-circle-member@example.com").first()
        db.session.add(CircleSubscription(user_id=user.id, plan_id=plan.id, status="active", source="manual"))
        db.session.commit()

    access = client.post(f"/api/v1/resources/{slug}/access", headers=auth_headers(member_token))
    assert access.status_code == 200
    url = access.get_json()["data"]["url"]
    assert url.startswith("/api/v1/resources/downloads/")
    assert "should-never-be-returned" not in url

    download = client.get(url)
    assert download.status_code == 200
    assert download.data == b"the real circle-protected bytes"


# ===========================================================================
# E. legacy direct_download file_url: unchanged by the generalization
# ===========================================================================


def test_e1_legacy_direct_download_file_url_only_returns_url_unchanged_with_no_token(app, client, manager_token):
    create = _create_resource(
        client, manager_token, accessType="direct_download", fileUrl="https://cdn.example.com/legacy-guide.pdf",
    )
    assert create.status_code == 201
    resource_id = create.get_json()["data"]["id"]
    slug = create.get_json()["data"]["slug"]

    access = client.post(f"/api/v1/resources/{slug}/access")
    assert access.status_code == 200
    assert access.get_json()["data"]["url"] == "https://cdn.example.com/legacy-guide.pdf"
    assert _tokens_for_resource(app, resource_id) == []


# ===========================================================================
# F. publish validation
# ===========================================================================


def test_f1_direct_download_protected_upload_can_publish(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "publishable.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    resp = _create_resource(client, manager_token, accessType="direct_download", protectedFilePath=path)
    assert resp.status_code == 201
    assert resp.get_json()["data"]["status"] == "published"


def test_f2_email_gate_protected_upload_can_publish(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "publishable.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    resp = _create_resource(client, manager_token, accessType="email_gate", protectedFilePath=path)
    assert resp.status_code == 201
    assert resp.get_json()["data"]["status"] == "published"


def test_f3_member_only_protected_upload_can_publish(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "publishable.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    resp = _create_resource(client, manager_token, accessType="member_only", protectedFilePath=path)
    assert resp.status_code == 201
    assert resp.get_json()["data"]["status"] == "published"


def test_f4_direct_download_nonexistent_protected_path_rejected_even_with_valid_file_url(
    client, manager_token, protected_root
):
    # protectedFilePath was never actually uploaded — must be rejected
    # even though a perfectly valid legacy fileUrl is ALSO present; an
    # explicitly configured (but broken) protected file must never
    # silently fall back to the legacy URL.
    resp = _create_resource(
        client, manager_token, accessType="direct_download",
        protectedFilePath="never-uploaded.pdf", fileUrl="https://cdn.example.com/fallback.pdf",
    )
    assert resp.status_code == 422


def test_f5_circle_only_still_requires_protected_path(client, manager_token):
    resp = _create_resource(client, manager_token, accessType="circle_only")
    assert resp.status_code == 422


# ===========================================================================
# G. public serialization — a direct_download resource's uploaded
# protected file must never leak, exactly like circle_only's already
# doesn't (test_resource_protected_uploads.py's test_36 covers that one).
# ===========================================================================


def test_g1_direct_download_protected_path_never_leaks_publicly(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "secret-direct.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_resource(
        client, manager_token, accessType="direct_download", protectedFilePath=path,
        protectedOriginalFilename="secret-direct.pdf",
    )
    slug = create.get_json()["data"]["slug"]

    detail = client.get(f"/api/v1/resources/{slug}")
    assert detail.status_code == 200
    data = detail.get_json()["data"]
    assert "protectedFilePath" not in data and "protected_file_path" not in data
    assert "protectedOriginalFilename" not in data and "protected_original_filename" not in data

    listing = client.get("/api/v1/resources")
    for item in listing.get_json()["data"]:
        assert "protectedFilePath" not in item and "protected_file_path" not in item


# ===========================================================================
# H. replacement/deletion cleanup works for a non-Circle resource too
# ===========================================================================


def test_h1_direct_download_replace_cleans_up_old_file_after_commit(client, manager_token, protected_root):
    upload_a = _upload(client, manager_token, "v1.pdf", _pdf_bytes())
    path_a = upload_a.get_json()["data"]["protectedFilePath"]
    create = _create_resource(client, manager_token, accessType="direct_download", protectedFilePath=path_a)
    slug = create.get_json()["data"]["slug"]
    assert (protected_root / path_a).exists()

    upload_b = _upload(client, manager_token, "v2.pdf", _pdf_bytes())
    path_b = upload_b.get_json()["data"]["protectedFilePath"]

    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Generalized Upload Resource", "accessType": "direct_download", "protectedFilePath": path_b,
            "description": [{"type": "paragraph", "text": "Body."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["protected_file_path"] == path_b
    assert (protected_root / path_b).exists()
    assert not (protected_root / path_a).exists()


def test_h2_direct_download_failed_update_does_not_delete_old_file(app, client, manager_token, protected_root):
    from app.extensions import db

    upload_a = _upload(client, manager_token, "v1.pdf", _pdf_bytes())
    path_a = upload_a.get_json()["data"]["protectedFilePath"]
    create = _create_resource(client, manager_token, accessType="direct_download", protectedFilePath=path_a)
    slug = create.get_json()["data"]["slug"]

    # Points at a protected path that was never uploaded, with no
    # fallback fileUrl either — _validate_publish rejects this before
    # any commit, so the old (still valid) file must be left untouched.
    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Generalized Upload Resource", "accessType": "direct_download",
            "protectedFilePath": "never-uploaded-either.pdf",
            "description": [{"type": "paragraph", "text": "Body."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 422
    assert (protected_root / path_a).exists()

    db.session.rollback()
    reread = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
    assert reread.get_json()["data"]["protected_file_path"] == path_a


# ===========================================================================
# I. migration/model: nullable user_id
# ===========================================================================


def test_i1_resource_download_token_supports_nullable_user_id(app, client, manager_token, protected_root):
    from app.extensions import db
    from app.models.resource import Resource, ResourceDownloadToken

    (protected_root / "anon.pdf").write_bytes(_pdf_bytes())
    with app.app_context():
        resource = Resource(
            slug=_slug("nullable-user-id"), name="Nullable User Id Resource", access_type="direct_download",
            protected_file_path="anon.pdf", status="published", published_date=date.today(),
            description=[{"type": "paragraph", "text": "Body."}],
        )
        db.session.add(resource)
        db.session.commit()

        token = ResourceDownloadToken(
            resource_id=resource.id,
            user_id=None,
            token_hash="0" * 64,
            expires_at=db.func.now(),
        )
        db.session.add(token)
        db.session.commit()  # must not raise an IntegrityError on user_id

        reloaded = ResourceDownloadToken.query.filter_by(token_hash="0" * 64).first()
        assert reloaded is not None
        assert reloaded.user_id is None
