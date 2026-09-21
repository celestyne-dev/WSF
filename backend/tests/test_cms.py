import io

import pytest

from tests.conftest import auth_headers

ADMIN_PAYLOAD = {
    "email": "admin@example.com",
    "password": "supersecret1",
    "first_name": "Ada",
    "last_name": "Min",
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


def _tiny_png():
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (4, 4), color=(120, 40, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_media_upload_list_patch_and_delete_reference_guard(client, admin_token):
    upload = client.post(
        "/api/v1/media/upload",
        data={"file": (io.BytesIO(_tiny_png()), "tiny.png"), "alt_text": "A tiny square"},
        content_type="multipart/form-data",
        headers=auth_headers(admin_token),
    )
    assert upload.status_code == 201
    media = upload.get_json()["data"]
    assert media["variants"]

    listed = client.get("/api/v1/media", headers=auth_headers(admin_token))
    assert listed.status_code == 200
    assert listed.get_json()["meta"]["total"] == 1

    patched = client.patch(
        f"/api/v1/media/{media['id']}",
        json={"caption": "Updated caption"},
        headers=auth_headers(admin_token),
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["caption"] == "Updated caption"
    assert patched.get_json()["data"]["alt_text"] == "A tiny square"  # untouched fields survive a partial patch

    # Attach it as an author photo, then deleting must be refused.
    author = client.post(
        "/api/v1/authors",
        json={"name": "Someone", "photoMediaId": media["id"]},
        headers=auth_headers(admin_token),
    )
    assert author.status_code == 201

    blocked = client.delete(f"/api/v1/media/{media['id']}", headers=auth_headers(admin_token))
    assert blocked.status_code == 409


def test_media_list_search(client, admin_token):
    client.post(
        "/api/v1/media/upload",
        data={"file": (io.BytesIO(_tiny_png()), "team-offsite.png"), "alt_text": "Team at the offsite"},
        content_type="multipart/form-data",
        headers=auth_headers(admin_token),
    )
    client.post(
        "/api/v1/media/upload",
        data={"file": (io.BytesIO(_tiny_png()), "hero-banner.png"), "caption": "Homepage hero"},
        content_type="multipart/form-data",
        headers=auth_headers(admin_token),
    )

    by_filename = client.get("/api/v1/media?q=offsite", headers=auth_headers(admin_token))
    assert by_filename.status_code == 200
    assert by_filename.get_json()["meta"]["total"] == 1
    assert by_filename.get_json()["data"][0]["original_filename"] == "team-offsite.png"

    by_caption = client.get("/api/v1/media?q=hero", headers=auth_headers(admin_token))
    assert by_caption.get_json()["meta"]["total"] == 1
    assert by_caption.get_json()["data"][0]["caption"] == "Homepage hero"

    no_match = client.get("/api/v1/media?q=nonexistent", headers=auth_headers(admin_token))
    assert no_match.get_json()["meta"]["total"] == 0


def test_homepage_builder_round_trip(client, admin_token):
    payload = {
        "modules": [
            {"type": "hero", "heading": "Home", "config": {"leadArticleSlug": "some-article"}},
            {"type": "latest_stories", "enabled": False, "config": {"itemCount": 8}},
        ]
    }
    saved = client.put("/api/v1/admin/homepage", json=payload, headers=auth_headers(admin_token))
    assert saved.status_code == 200
    assert len(saved.get_json()["data"]) == 2

    public = client.get("/api/v1/public/homepage")
    assert public.status_code == 200
    # Only the enabled module should surface on the public endpoint.
    assert [m["type"] for m in public.get_json()["data"]] == ["hero"]


def test_navigation_builder_with_nested_children_and_social_links(client, admin_token):
    payload = {
        "menus": [
            {
                "key": "primary",
                "items": [
                    {
                        "label": "People",
                        "url": "/people",
                        "children": [
                            {"label": "Authors", "url": "/authors"},
                            {"label": "Series", "url": "/series"},
                        ],
                    },
                    {"label": "Resources", "url": "/resources"},
                ],
            }
        ],
        "socialLinks": [{"platform": "linkedin", "url": "https://linkedin.com/company/wsf", "handle": "WSF"}],
    }
    saved = client.put("/api/v1/admin/navigation", json=payload, headers=auth_headers(admin_token))
    assert saved.status_code == 200

    public = client.get("/api/v1/public/navigation")
    assert public.status_code == 200
    body = public.get_json()["data"]
    primary_items = body["menus"]["primary"]["items"]
    assert primary_items[0]["label"] == "People"
    assert [c["label"] for c in primary_items[0]["children"]] == ["Authors", "Series"]
    assert body["socialLinks"][0]["platform"] == "linkedin"


def test_settings_round_trip(client, admin_token):
    saved = client.put(
        "/api/v1/admin/settings",
        json={"settings": {"site_name": "Women Shaping Futures", "maintenance_mode": False}},
        headers=auth_headers(admin_token),
    )
    assert saved.status_code == 200
    assert saved.get_json()["data"]["site_name"] == "Women Shaping Futures"

    public = client.get("/api/v1/public/settings")
    assert public.status_code == 200
    assert public.get_json()["data"]["maintenance_mode"] is False


def test_media_endpoints_require_permission(client):
    client.post(
        "/api/v1/auth/register",
        json={"email": "member2@example.com", "password": "supersecret1", "first_name": "M", "last_name": "B"},
    )
    login = client.post(
        "/api/v1/auth/login", json={"email": "member2@example.com", "password": "supersecret1"}
    )
    token = login.get_json()["data"]["access_token"]

    resp = client.get("/api/v1/media", headers=auth_headers(token))
    assert resp.status_code == 403
