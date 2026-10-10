"""Focused tests for Module 13B — secure circle_only Resource file uploads
(app/services/resource_downloads.py's save_protected_upload(), app/api/v1/
resources.py's ResourceProtectedUploadResource, and the replace/clear/
delete cleanup lifecycle). Writes INTO the existing Module 10/10.1
protected-download architecture (PROTECTED_MEDIA_ROOT, is_safe_protected_
path()/resolve_real_protected_path() containment, resource-bound download
tokens) — never bypasses or re-derives any of it; see
test_resource_downloads.py for that architecture's own test coverage,
which this file does not duplicate.
"""
import io
import os
import uuid
import zipfile
from datetime import date

import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "resup-manager@example.com", "password": "supersecret1",
    "first_name": "Zanele", "last_name": "Dube", "country_code": "ZA",
}
ORDINARY_PAYLOAD = {
    "email": "resup-ordinary@example.com", "password": "supersecret1",
    "first_name": "Priya", "last_name": "Nair", "country_code": "IN",
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
def ordinary_token(client):
    return _register(client, ORDINARY_PAYLOAD)


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


def _fake_pdf_bytes():
    return b"this file claims to be a pdf but is not"


def _zip_bytes(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _docx_bytes():
    return _zip_bytes({"[Content_Types].xml": "<Types/>", "word/document.xml": "<document/>"})


def _xlsx_bytes():
    return _zip_bytes({"[Content_Types].xml": "<Types/>", "xl/workbook.xml": "<workbook/>"})


def _pptx_bytes():
    return _zip_bytes({"[Content_Types].xml": "<Types/>", "ppt/presentation.xml": "<presentation/>"})


def _plain_zip_bytes():
    return _zip_bytes({"readme.txt": "just a readme, no office document structure"})


def _corrupt_zip_bytes():
    return b"PK\x03\x04" + os.urandom(64)


def _upload(client, token, filename, content, mimetype=None):
    file_tuple = (io.BytesIO(content), filename) if mimetype is None else (io.BytesIO(content), filename, mimetype)
    return client.post(
        "/api/v1/resources/uploads/protected",
        data={"file": file_tuple},
        content_type="multipart/form-data",
        headers=auth_headers(token) if token else {},
    )


def _create_circle_resource(client, token, protected_file_path, status="published", **overrides):
    payload = {
        "name": overrides.pop("name", "Circle Workbook"),
        "accessType": "circle_only",
        "protectedFilePath": protected_file_path,
        "description": [{"type": "paragraph", "text": "Members-only workbook."}],
        "status": status,
    }
    payload.update(overrides)
    return client.post("/api/v1/resources", json=payload, headers=auth_headers(token))


# ===========================================================================
# 1-4: basic authorized upload shape
# ===========================================================================


def test_1_resources_manage_valid_pdf_upload_succeeds(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "Career Reset Workbook.pdf", _pdf_bytes())
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["fileFormat"] == "PDF"
    assert data["fileSize"] == len(_pdf_bytes())
    assert data["protectedOriginalFilename"] == "Career Reset Workbook.pdf"


def test_2_returned_protected_file_path_is_server_generated(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "Career Reset Workbook.pdf", _pdf_bytes())
    path = resp.get_json()["data"]["protectedFilePath"]
    assert path.startswith("resource_")
    assert path.endswith(".pdf")
    assert "Career" not in path
    assert (protected_root / path).exists()


def test_3_returned_path_is_relative_with_no_root_leakage(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "report.pdf", _pdf_bytes())
    data = resp.get_json()["data"]
    assert not data["protectedFilePath"].startswith("/")
    assert str(protected_root) not in data["protectedFilePath"]
    import json

    body_text = json.dumps(data)
    assert str(protected_root) not in body_text
    assert "PROTECTED_MEDIA_ROOT" not in body_text


def test_4_original_filename_metadata_is_sanitized(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "../../etc/passwd.pdf", _pdf_bytes())
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    # Only the basename survives — no directory traversal component, and
    # it never influenced the actual stored path (checked separately below).
    assert data["protectedOriginalFilename"] == "passwd.pdf"
    assert ".." not in data["protectedFilePath"]
    assert "/" not in data["protectedFilePath"]


# ===========================================================================
# 5-6: authorization
# ===========================================================================


def test_5_unauthenticated_upload_rejected(client, protected_root):
    resp = _upload(client, None, "workbook.pdf", _pdf_bytes())
    assert resp.status_code == 401


def test_6_ordinary_authenticated_user_rejected(client, ordinary_token, protected_root):
    resp = _upload(client, ordinary_token, "workbook.pdf", _pdf_bytes())
    assert resp.status_code == 403


# ===========================================================================
# 7-18: content validation per format
# ===========================================================================


def test_7_unsupported_extension_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "virus.exe", b"MZ fake exe header")
    assert resp.status_code == 415


def test_8_fake_pdf_content_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "fake.pdf", _fake_pdf_bytes())
    assert resp.status_code == 415


def test_9_contradictory_mime_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "photo.pdf", _pdf_bytes(), mimetype="image/png")
    assert resp.status_code == 415


def test_10_generic_octet_stream_accepted_when_content_validates(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "workbook.pdf", _pdf_bytes(), mimetype="application/octet-stream")
    assert resp.status_code == 201


def test_11_valid_zip_accepted(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "assets.zip", _plain_zip_bytes())
    assert resp.status_code == 201
    assert resp.get_json()["data"]["fileFormat"] == "ZIP"


def test_12_corrupt_zip_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "assets.zip", _corrupt_zip_bytes())
    assert resp.status_code == 415


def test_13_valid_docx_structure_accepted(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "memo.docx", _docx_bytes())
    assert resp.status_code == 201
    assert resp.get_json()["data"]["fileFormat"] == "DOCX"


def test_14_generic_zip_renamed_docx_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "memo.docx", _plain_zip_bytes())
    assert resp.status_code == 415


def test_15_valid_xlsx_structure_accepted(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "budget.xlsx", _xlsx_bytes())
    assert resp.status_code == 201
    assert resp.get_json()["data"]["fileFormat"] == "XLSX"


def test_16_generic_zip_renamed_xlsx_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "budget.xlsx", _plain_zip_bytes())
    assert resp.status_code == 415


def test_17_valid_pptx_structure_accepted(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "deck.pptx", _pptx_bytes())
    assert resp.status_code == 201
    assert resp.get_json()["data"]["fileFormat"] == "PPTX"


def test_18_generic_zip_renamed_pptx_rejected(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "deck.pptx", _plain_zip_bytes())
    assert resp.status_code == 415


# ===========================================================================
# 19: size enforcement
# ===========================================================================


def test_19_oversized_protected_upload_rejected(client, app, manager_token, protected_root):
    app.config["MAX_PROTECTED_UPLOAD_SIZE"] = 100  # tiny ceiling for this test only
    resp = _upload(client, manager_token, "big.pdf", _pdf_bytes() + b"0" * 1000)
    assert resp.status_code == 413


# ===========================================================================
# 20-22: storage safety
# ===========================================================================


def test_20_malicious_client_filename_cannot_influence_disk_path(client, manager_token, protected_root):
    resp = _upload(client, manager_token, "../../../../etc/passwd", _pdf_bytes())
    # No ".pdf"-equivalent extension on this filename at all -> rejected
    # by the extension allowlist, which is itself the first line of
    # defense against a client filename ever reaching path construction.
    assert resp.status_code == 415

    resp2 = _upload(client, manager_token, "../../../../etc/passwd.pdf", _pdf_bytes())
    assert resp2.status_code == 201
    path = resp2.get_json()["data"]["protectedFilePath"]
    assert path == os.path.basename(path)
    assert ".." not in path


def test_21_duplicate_client_filenames_create_distinct_stored_files(client, manager_token, protected_root):
    first = _upload(client, manager_token, "workbook.pdf", _pdf_bytes())
    second = _upload(client, manager_token, "workbook.pdf", _pdf_bytes())
    assert first.status_code == second.status_code == 201
    path_a = first.get_json()["data"]["protectedFilePath"]
    path_b = second.get_json()["data"]["protectedFilePath"]
    assert path_a != path_b
    assert (protected_root / path_a).exists()
    assert (protected_root / path_b).exists()


def test_22_failed_validation_leaves_no_temp_or_partial_file_behind(client, manager_token, protected_root):
    before = set(os.listdir(protected_root))
    resp = _upload(client, manager_token, "fake.pdf", _fake_pdf_bytes())
    assert resp.status_code == 415
    after = set(os.listdir(protected_root))
    assert before == after


# ===========================================================================
# 23: uploaded file satisfies circle_only publish validation
# ===========================================================================


def test_23_newly_uploaded_file_satisfies_circle_only_publish_validation(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "career-workbook.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    original_name = upload.get_json()["data"]["protectedOriginalFilename"]

    create = _create_circle_resource(
        client, manager_token, path, status="published", protectedOriginalFilename=original_name
    )
    assert create.status_code == 201
    assert create.get_json()["data"]["status"] == "published"
    assert create.get_json()["data"]["protected_original_filename"] == original_name


# ===========================================================================
# 25-27: replace lifecycle
# ===========================================================================


def test_25_replace_activates_new_file_and_cleans_up_old_after_commit(client, manager_token, protected_root):
    upload_a = _upload(client, manager_token, "v1.pdf", _pdf_bytes())
    path_a = upload_a.get_json()["data"]["protectedFilePath"]
    create = _create_circle_resource(client, manager_token, path_a, status="published")
    slug = create.get_json()["data"]["slug"]
    assert (protected_root / path_a).exists()

    upload_b = _upload(client, manager_token, "v2.pdf", _pdf_bytes())
    path_b = upload_b.get_json()["data"]["protectedFilePath"]

    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Circle Workbook", "accessType": "circle_only", "protectedFilePath": path_b,
            "description": [{"type": "paragraph", "text": "Members-only workbook."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["protected_file_path"] == path_b
    assert (protected_root / path_b).exists()
    assert not (protected_root / path_a).exists()  # old file cleaned up


def test_26_simulated_update_failure_leaves_old_file_untouched(app, client, manager_token, protected_root):
    from app.extensions import db

    upload_a = _upload(client, manager_token, "v1.pdf", _pdf_bytes())
    path_a = upload_a.get_json()["data"]["protectedFilePath"]
    create = _create_circle_resource(client, manager_token, path_a, status="published")
    slug = create.get_json()["data"]["slug"]

    # Point at a path that was never actually uploaded — _validate_publish
    # rejects this before any commit, so the DB (and therefore the old
    # file's referenced status) must be completely unaffected.
    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Circle Workbook", "accessType": "circle_only", "protectedFilePath": "never-uploaded.pdf",
            "description": [{"type": "paragraph", "text": "Members-only workbook."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 422
    assert (protected_root / path_a).exists()

    # The `app` fixture keeps one app context (and therefore, since
    # Flask-SQLAlchemy 3.x scopes db.session by id(current app context) —
    # see flask_sqlalchemy.session._app_ctx_id — one single SQLAlchemy
    # session) alive for this whole test. client.put()/client.get() both
    # reuse that same already-pushed context (Flask's RequestContext.push
    # only creates a new app context when none for this app is already on
    # the stack), so without this, the GET below would return the exact
    # same Python object `_apply_fields` mutated in memory before
    # `_validate_publish` raised, regardless of what Postgres actually
    # has. Calling this directly (no nested `app.app_context()` — that
    # would push a context with a different id() and therefore resolve to
    # an unrelated, freshly-created session) forces the real, shared
    # session to re-fetch from the database on next access.
    db.session.rollback()

    reread = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
    assert reread.get_json()["data"]["protected_file_path"] == path_a


def test_27_shared_legacy_path_not_deleted_while_another_resource_still_uses_it(
    app, client, manager_token, protected_root
):
    from app.extensions import db
    from app.models.resource import Resource

    shared_filename = "legacy-shared-shared.pdf"
    (protected_root / shared_filename).write_bytes(_pdf_bytes())
    with app.app_context():
        other = Resource(
            slug=_slug("legacy-sibling"), name="Legacy Sibling", access_type="circle_only",
            protected_file_path=shared_filename, status="published", published_date=date.today(),
            description=[{"type": "paragraph", "text": "Body."}],
        )
        db.session.add(other)
        db.session.commit()

    create = _create_circle_resource(client, manager_token, shared_filename, status="published", name="Legacy Primary")
    slug = create.get_json()["data"]["slug"]

    upload_new = _upload(client, manager_token, "replacement.pdf", _pdf_bytes())
    new_path = upload_new.get_json()["data"]["protectedFilePath"]
    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Legacy Primary", "accessType": "circle_only", "protectedFilePath": new_path,
            "description": [{"type": "paragraph", "text": "Body."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    # The OTHER resource still references the shared legacy path, so it
    # must never be deleted even though THIS resource moved off it.
    assert (protected_root / shared_filename).exists()


# ===========================================================================
# 28-29: clear lifecycle (draft vs published)
# ===========================================================================


def test_28_draft_remove_succeeds_and_cleans_up_after_commit(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "draft-file.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_circle_resource(client, manager_token, path, status="draft")
    slug = create.get_json()["data"]["slug"]
    assert (protected_root / path).exists()

    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Circle Workbook", "accessType": "circle_only", "protectedFilePath": None,
            "description": [{"type": "paragraph", "text": "Members-only workbook."}], "status": "draft",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["protected_file_path"] is None
    assert not (protected_root / path).exists()


def test_29_published_remove_rejected_and_old_file_remains(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "published-file.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_circle_resource(client, manager_token, path, status="published")
    slug = create.get_json()["data"]["slug"]

    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Circle Workbook", "accessType": "circle_only", "protectedFilePath": None,
            "description": [{"type": "paragraph", "text": "Members-only workbook."}], "status": "published",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 422
    assert (protected_root / path).exists()


# ===========================================================================
# 30-31: delete / archive
# ===========================================================================


def test_30_resource_delete_cleans_up_unreferenced_protected_file(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "to-delete.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_circle_resource(client, manager_token, path, status="draft")
    slug = create.get_json()["data"]["slug"]
    assert (protected_root / path).exists()

    delete = client.delete(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
    assert delete.status_code == 200
    assert not (protected_root / path).exists()


def test_31_archived_resource_retains_protected_file(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "archive-me.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    create = _create_circle_resource(client, manager_token, path, status="published")
    slug = create.get_json()["data"]["slug"]

    update = client.put(
        f"/api/v1/resources/{slug}",
        json={
            "name": "Circle Workbook", "accessType": "circle_only", "protectedFilePath": path,
            "description": [{"type": "paragraph", "text": "Members-only workbook."}], "status": "archived",
        },
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["status"] == "archived"
    assert (protected_root / path).exists()


# ===========================================================================
# 32-33: download filename / legacy compatibility
# ===========================================================================


def test_32_legacy_null_original_filename_still_downloads(app, client, manager_token, protected_root):
    from app.extensions import db
    from app.models.circle import CirclePlan, CircleSubscription
    from app.models.resource import Resource
    from app.models.user import User

    filename = "legacy-manually-placed.pdf"
    (protected_root / filename).write_bytes(_pdf_bytes())
    with app.app_context():
        resource = Resource(
            slug=_slug("legacy-dl"), name="Legacy Download", access_type="circle_only",
            protected_file_path=filename, status="published", published_date=date.today(),
            description=[{"type": "paragraph", "text": "Body."}],
        )
        db.session.add(resource)
        db.session.commit()
        resource_slug = resource.slug

        plan = CirclePlan(slug=_slug("plan"), name="Circle", billing_interval="monthly", price=1000, currency="USD", status="active")
        db.session.add(plan)
        db.session.commit()
        member_token = _register(client, {"email": "resup-member-32@example.com", "password": "supersecret1", "first_name": "Lea", "last_name": "K", "country_code": "FR"})
        user = User.query.filter_by(email="resup-member-32@example.com").first()
        db.session.add(CircleSubscription(user_id=user.id, plan_id=plan.id, status="active", source="manual"))
        db.session.commit()

    access = client.post(f"/api/v1/resources/{resource_slug}/access", headers=auth_headers(member_token))
    assert access.status_code == 200
    download_url = access.get_json()["data"]["url"]
    download = client.get(download_url)
    assert download.status_code == 200
    assert "legacy-manually-placed.pdf" in download.headers.get("Content-Disposition", "")


def test_33_content_disposition_uses_protected_original_filename_when_present(
    app, client, manager_token, protected_root
):
    from app.extensions import db
    from app.models.circle import CirclePlan, CircleSubscription
    from app.models.user import User

    upload = _upload(client, manager_token, "Career Reset Workbook.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    original_name = upload.get_json()["data"]["protectedOriginalFilename"]
    create = _create_circle_resource(
        client, manager_token, path, status="published", protectedOriginalFilename=original_name
    )
    resource_slug = create.get_json()["data"]["slug"]

    with app.app_context():
        plan = CirclePlan(slug=_slug("plan"), name="Circle", billing_interval="monthly", price=1000, currency="USD", status="active")
        db.session.add(plan)
        db.session.commit()
        member_token = _register(client, {"email": "resup-member-33@example.com", "password": "supersecret1", "first_name": "Ama", "last_name": "O", "country_code": "GH"})
        user = User.query.filter_by(email="resup-member-33@example.com").first()
        db.session.add(CircleSubscription(user_id=user.id, plan_id=plan.id, status="active", source="manual"))
        db.session.commit()

    access = client.post(f"/api/v1/resources/{resource_slug}/access", headers=auth_headers(member_token))
    download_url = access.get_json()["data"]["url"]
    download = client.get(download_url)
    assert download.status_code == 200
    assert "Career Reset Workbook.pdf" in download.headers.get("Content-Disposition", "")
    # Never the server-generated storage name as the user-facing filename
    # when a real original filename is available.
    assert path not in download.headers.get("Content-Disposition", "")


# ===========================================================================
# 36-37: public payload exposure + staff round-trip
# ===========================================================================


def test_36_public_payload_never_exposes_protected_path_or_original_filename(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "secret-workbook.pdf", _pdf_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    original_name = upload.get_json()["data"]["protectedOriginalFilename"]
    create = _create_circle_resource(
        client, manager_token, path, status="published", protectedOriginalFilename=original_name
    )
    slug = create.get_json()["data"]["slug"]

    public_detail = client.get(f"/api/v1/resources/{slug}")
    assert public_detail.status_code == 200
    public_data = public_detail.get_json()["data"]
    assert "protectedFilePath" not in public_data
    assert "protected_file_path" not in public_data
    assert "protectedOriginalFilename" not in public_data
    assert "protected_original_filename" not in public_data

    public_list = client.get("/api/v1/resources")
    assert public_list.status_code == 200
    for item in public_list.get_json()["data"]:
        assert "protectedFilePath" not in item
        assert "protected_file_path" not in item
        assert "protectedOriginalFilename" not in item
        assert "protected_original_filename" not in item


def test_37_staff_detail_round_trips_original_filename_metadata(client, manager_token, protected_root):
    upload = _upload(client, manager_token, "Team Offsite Agenda.docx", _docx_bytes())
    path = upload.get_json()["data"]["protectedFilePath"]
    original_name = upload.get_json()["data"]["protectedOriginalFilename"]
    assert original_name == "Team Offsite Agenda.docx"

    create = _create_circle_resource(
        client, manager_token, path, status="draft", protectedOriginalFilename=original_name,
        fileFormat="DOCX",
    )
    slug = create.get_json()["data"]["slug"]

    staff_detail = client.get(f"/api/v1/resources/{slug}", headers=auth_headers(manager_token))
    assert staff_detail.status_code == 200
    data = staff_detail.get_json()["data"]
    assert data["protected_original_filename"] == original_name
    assert data["protected_file_path"] == path
