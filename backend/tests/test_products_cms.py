import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "products-manager@example.com",
    "password": "supersecret1",
    "first_name": "Amina",
    "last_name": "Okoye",
    "country_code": "NG",
}

NO_PERMISSION_PAYLOAD = {
    "email": "products-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
}


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
    return _register_with_role(client, app, MANAGER_PAYLOAD, "products_manager")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


def _make_media(app, filename="cover.jpg"):
    from app.extensions import db
    from app.models.media import Media

    with app.app_context():
        media = Media(
            original_filename=filename,
            stored_filename=filename,
            file_path=f"/media/{filename}",
            public_url=f"https://cdn.example.com/{filename}",
            mime_type="image/jpeg",
        )
        db.session.add(media)
        db.session.commit()
        return media.id


def _base_payload(**overrides):
    payload = {
        "name": "The Founder's Playbook",
        "shortDescription": "A practical guide to launching your first venture.",
        "description": [{"type": "paragraph", "text": "Everything you need to get started."}],
        "type": "digital",
        "price": 2900,
        "currency": "USD",
        "status": "active",
    }
    payload.update(overrides)
    return payload


def test_product_create_requires_permission(client):
    resp = client.post("/api/v1/products", json=_base_payload())
    assert resp.status_code in (401, 403)


def test_product_create_requires_permission_even_with_account(client, no_permission_token):
    resp = client.post("/api/v1/products", json=_base_payload(), headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_product_create_update_and_slug_uniqueness(client, manager_token):
    create = client.post("/api/v1/products", json=_base_payload(), headers=auth_headers(manager_token))
    assert create.status_code == 201
    product = create.get_json()["data"]
    assert product["slug"] == "the-founder-s-playbook" or product["slug"].startswith("the-founder")

    dupe = client.post(
        "/api/v1/products", json=_base_payload(), headers=auth_headers(manager_token)
    )
    assert dupe.status_code == 201
    assert dupe.get_json()["data"]["slug"] != product["slug"]

    update = client.put(
        f"/api/v1/products/{product['slug']}",
        json=_base_payload(name="The Founder's Playbook, Revised"),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    assert update.get_json()["data"]["name"] == "The Founder's Playbook, Revised"


def test_product_full_description_persists(client, manager_token):
    blocks = [
        {"type": "heading", "text": "What's included"},
        {"type": "paragraph", "text": "A workbook, templates, and a 6-week planner."},
    ]
    resp = client.post(
        "/api/v1/products", json=_base_payload(description=blocks), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    slug = resp.get_json()["data"]["slug"]

    fetched = client.get(f"/api/v1/products/{slug}", headers=auth_headers(manager_token))
    assert fetched.get_json()["data"]["description"] == blocks


def test_product_invalid_type_rejected(client, manager_token):
    resp = client.post(
        "/api/v1/products", json=_base_payload(type="not-a-real-type"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_product_category(client, app, manager_token):
    cat_resp = client.post(
        "/api/v1/products/categories", json={"name": "Guides"}, headers=auth_headers(manager_token)
    )
    assert cat_resp.status_code == 201
    category = cat_resp.get_json()["data"]
    assert category["slug"] == "guides"

    list_resp = client.get("/api/v1/products/categories")
    assert list_resp.status_code == 200
    assert any(c["slug"] == "guides" for c in list_resp.get_json()["data"])

    product = client.post(
        "/api/v1/products",
        json=_base_payload(categoryId=category["id"]),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert product["category"]["slug"] == "guides"
    assert product["category_id"] == category["id"]


def test_product_pricing_and_sale_price(client, manager_token):
    resp = client.post(
        "/api/v1/products",
        json=_base_payload(price=5000, salePrice=3500, currency="KES"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["price"] == 5000
    assert data["sale_price"] == 3500
    assert data["currency"] == "KES"


def test_product_sale_price_cannot_exceed_price(client, manager_token):
    resp = client.post(
        "/api/v1/products",
        json=_base_payload(price=1000, salePrice=1500),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 422


def test_product_negative_price_rejected(client, manager_token):
    resp = client.post("/api/v1/products", json=_base_payload(price=-5), headers=auth_headers(manager_token))
    assert resp.status_code == 422


def test_product_free_product(client, manager_token):
    resp = client.post("/api/v1/products", json=_base_payload(price=0), headers=auth_headers(manager_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["price"] == 0


def test_product_sku(client, manager_token):
    resp = client.post("/api/v1/products", json=_base_payload(sku="WSF-PB-001"), headers=auth_headers(manager_token))
    assert resp.status_code == 201
    assert resp.get_json()["data"]["sku"] == "WSF-PB-001"


def test_product_inventory_and_availability(client, manager_token):
    in_stock = client.post(
        "/api/v1/products",
        json=_base_payload(
            name="Printed Workbook", type="physical", trackInventory=True, stockQuantity=5
        ),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert in_stock["is_available"] is True

    out_of_stock = client.post(
        "/api/v1/products",
        json=_base_payload(
            name="Sold Out Workbook", type="physical", trackInventory=True, stockQuantity=0
        ),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert out_of_stock["is_available"] is False

    negative_stock = client.post(
        "/api/v1/products",
        json=_base_payload(name="Bad Stock", trackInventory=True, stockQuantity=-1),
        headers=auth_headers(manager_token),
    )
    assert negative_stock.status_code == 422


def test_product_digital_does_not_require_inventory(client, manager_token):
    resp = client.post(
        "/api/v1/products", json=_base_payload(type="digital"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["is_available"] is True
    assert data["stock_quantity"] is None


def test_product_media_and_gallery(client, app, manager_token):
    cover_id = _make_media(app, "cover.jpg")
    gallery_id_1 = _make_media(app, "gallery1.jpg")
    gallery_id_2 = _make_media(app, "gallery2.jpg")

    resp = client.post(
        "/api/v1/products",
        json=_base_payload(coverMediaId=cover_id, galleryMediaIds=[gallery_id_1, gallery_id_2]),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["cover_media"]["id"] == cover_id
    assert [img["media"]["id"] for img in data["images"]] == [gallery_id_1, gallery_id_2]

    # Reordering + removing persists, not just client-side state.
    update = client.put(
        f"/api/v1/products/{data['slug']}",
        json=_base_payload(coverMediaId=cover_id, galleryMediaIds=[gallery_id_2]),
        headers=auth_headers(manager_token),
    )
    assert update.status_code == 200
    updated = update.get_json()["data"]
    assert [img["media"]["id"] for img in updated["images"]] == [gallery_id_2]


def test_product_gallery_rejects_unknown_media(client, manager_token):
    resp = client.post(
        "/api/v1/products", json=_base_payload(galleryMediaIds=[999999]), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 404


def test_product_purchase_url(client, manager_token):
    resp = client.post(
        "/api/v1/products",
        json=_base_payload(purchaseUrl="https://gumroad.com/l/founders-playbook"),
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["purchase_url"] == "https://gumroad.com/l/founders-playbook"


def test_product_purchase_url_validation(client, manager_token):
    resp = client.post(
        "/api/v1/products", json=_base_payload(purchaseUrl="not-a-url"), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422


def test_product_featured(client, manager_token):
    resp = client.post(
        "/api/v1/products", json=_base_payload(featured=True), headers=auth_headers(manager_token)
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["featured"] is True


def test_product_status_and_public_visibility(client, manager_token):
    draft = client.post(
        "/api/v1/products", json=_base_payload(status="draft"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/products/{draft['slug']}")
    assert anon_detail.status_code == 404

    manager_detail = client.get(f"/api/v1/products/{draft['slug']}", headers=auth_headers(manager_token))
    assert manager_detail.status_code == 200

    anon_list = client.get("/api/v1/products")
    assert draft["slug"] not in [p["slug"] for p in anon_list.get_json()["data"]]

    publish = client.put(
        f"/api/v1/products/{draft['slug']}", json=_base_payload(status="active"), headers=auth_headers(manager_token)
    )
    assert publish.status_code == 200

    anon_detail_after = client.get(f"/api/v1/products/{draft['slug']}")
    assert anon_detail_after.status_code == 200
    anon_list_after = client.get("/api/v1/products")
    assert draft["slug"] in [p["slug"] for p in anon_list_after.get_json()["data"]]


def test_product_unavailable_stays_publicly_visible(client, manager_token):
    unavailable = client.post(
        "/api/v1/products",
        json=_base_payload(name="Temporarily Unavailable", status="unavailable"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]
    assert unavailable["is_available"] is False

    anon_detail = client.get(f"/api/v1/products/{unavailable['slug']}")
    assert anon_detail.status_code == 200
    assert anon_detail.get_json()["data"]["is_available"] is False


def test_product_archived_hidden_from_public(client, manager_token):
    archived = client.post(
        "/api/v1/products",
        json=_base_payload(name="Archived Guide", status="archived"),
        headers=auth_headers(manager_token),
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/products/{archived['slug']}")
    assert anon_detail.status_code == 404

    anon_list = client.get("/api/v1/products")
    assert archived["slug"] not in [p["slug"] for p in anon_list.get_json()["data"]]

    manager_list = client.get("/api/v1/products?status=archived", headers=auth_headers(manager_token))
    assert archived["slug"] in [p["slug"] for p in manager_list.get_json()["data"]]


def test_product_safe_deletion_with_order_references(client, manager_token):
    product = client.post(
        "/api/v1/products", json=_base_payload(name="Referenced Product"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    order = client.post(
        "/api/v1/orders",
        json={"email": "buyer2@example.com", "items": [{"productSlug": product["slug"], "quantity": 1}]},
    )
    assert order.status_code == 201

    delete = client.delete(f"/api/v1/products/{product['slug']}", headers=auth_headers(manager_token))
    assert delete.status_code == 409
    assert delete.get_json()["error"]["code"] == "reference_conflict"

    still_there = client.get(f"/api/v1/products/{product['slug']}", headers=auth_headers(manager_token))
    assert still_there.status_code == 200


def test_product_delete_without_references_succeeds(client, manager_token):
    product = client.post(
        "/api/v1/products", json=_base_payload(name="Unreferenced Product"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    delete = client.delete(f"/api/v1/products/{product['slug']}", headers=auth_headers(manager_token))
    assert delete.status_code == 200


def test_product_delete_requires_permission(client, manager_token, no_permission_token):
    product = client.post(
        "/api/v1/products", json=_base_payload(name="Guarded Product"), headers=auth_headers(manager_token)
    ).get_json()["data"]

    denied = client.delete(f"/api/v1/products/{product['slug']}", headers=auth_headers(no_permission_token))
    assert denied.status_code == 403


def test_product_public_serializer_hides_price_when_not_visible(client, manager_token):
    product = client.post(
        "/api/v1/products",
        json=_base_payload(name="Hidden Price Product", priceVisible=False, price=9900),
        headers=auth_headers(manager_token),
    ).get_json()["data"]

    anon_detail = client.get(f"/api/v1/products/{product['slug']}")
    assert anon_detail.status_code == 200
    anon_data = anon_detail.get_json()["data"]
    assert anon_data["price"] is None
    assert anon_data["sale_price"] is None

    manager_detail = client.get(f"/api/v1/products/{product['slug']}", headers=auth_headers(manager_token))
    manager_data = manager_detail.get_json()["data"]
    assert manager_data["price"] == 9900


def test_product_list_filters_by_type_category_featured_free(client, manager_token):
    client.post(
        "/api/v1/products",
        json=_base_payload(name="Free Ebook", type="digital", price=0, featured=True),
        headers=auth_headers(manager_token),
    )
    client.post(
        "/api/v1/products",
        json=_base_payload(name="Paid Course", type="service", price=5000),
        headers=auth_headers(manager_token),
    )

    type_filtered = client.get("/api/v1/products?type=service")
    names = [p["name"] for p in type_filtered.get_json()["data"]]
    assert "Paid Course" in names
    assert "Free Ebook" not in names

    free_filtered = client.get("/api/v1/products?free=true")
    names = [p["name"] for p in free_filtered.get_json()["data"]]
    assert "Free Ebook" in names
    assert "Paid Course" not in names

    featured_filtered = client.get("/api/v1/products?featured=true")
    names = [p["name"] for p in featured_filtered.get_json()["data"]]
    assert "Free Ebook" in names
