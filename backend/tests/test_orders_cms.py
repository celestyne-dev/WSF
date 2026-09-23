import pytest

from tests.conftest import auth_headers

MANAGER_PAYLOAD = {
    "email": "orders-manager@example.com",
    "password": "supersecret1",
    "first_name": "Order",
    "last_name": "Manager",
    "country_code": "US",
}

NO_PERMISSION_PAYLOAD = {
    "email": "orders-nobody@example.com",
    "password": "supersecret1",
    "first_name": "No",
    "last_name": "Permission",
    "country_code": "US",
}

PRODUCT_ADMIN_PAYLOAD = {
    "email": "orders-product-admin@example.com",
    "password": "supersecret1",
    "first_name": "Product",
    "last_name": "Admin",
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
    return _register_with_role(client, app, MANAGER_PAYLOAD, "orders_manager")


@pytest.fixture()
def no_permission_token(client, app):
    client.post("/api/v1/auth/register", json=NO_PERMISSION_PAYLOAD)
    login = client.post(
        "/api/v1/auth/login",
        json={"email": NO_PERMISSION_PAYLOAD["email"], "password": NO_PERMISSION_PAYLOAD["password"]},
    )
    return login.get_json()["data"]["access_token"]


@pytest.fixture()
def product_admin_token(client, app):
    return _register_with_role(client, app, PRODUCT_ADMIN_PAYLOAD, "products_manager")


@pytest.fixture()
def digital_product(client, product_admin_token):
    resp = client.post(
        "/api/v1/products",
        json={"name": "The Founder's CV Template", "price": 29, "currency": "USD", "type": "digital", "sku": "WSF-TPL-1", "status": "active"},
        headers=auth_headers(product_admin_token),
    )
    return resp.get_json()["data"]


@pytest.fixture()
def physical_product(client, product_admin_token):
    resp = client.post(
        "/api/v1/products",
        json={"name": "WSF Leadership Journal", "price": 28, "currency": "USD", "type": "physical", "sku": "WSF-MER-1", "status": "active"},
        headers=auth_headers(product_admin_token),
    )
    return resp.get_json()["data"]


def _create_order(client, product_slug, quantity=1, email="buyer@example.com"):
    return client.post(
        "/api/v1/orders", json={"email": email, "items": [{"productSlug": product_slug, "quantity": quantity}]}
    )


# ---- Permissions ----


def test_order_list_requires_permission(client, digital_product):
    _create_order(client, digital_product["slug"])
    resp = client.get("/api/v1/orders")
    assert resp.status_code in (401, 403)


def test_order_list_denied_without_orders_permission(client, no_permission_token, digital_product):
    _create_order(client, digital_product["slug"])
    resp = client.get("/api/v1/orders", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_order_list_allowed_for_orders_manager(client, manager_token, digital_product):
    _create_order(client, digital_product["slug"])
    resp = client.get("/api/v1/orders", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert len(resp.get_json()["data"]) >= 1


def test_order_detail_stranger_without_ownership_blocked(client, app, no_permission_token, digital_product):
    from app.extensions import db
    from app.models.commerce import Order
    from app.models.user import User

    created = _create_order(client, digital_product["slug"]).get_json()["data"]
    order_uuid = created["uuid"]

    # Attach the order to a real user (not the requester) to exercise the
    # "logged-in order only visible to its owner or staff" branch.
    client.post(
        "/api/v1/auth/register",
        json={"email": "orders-order-owner@example.com", "password": "supersecret1", "first_name": "Owner", "last_name": "User", "country_code": "US"},
    )
    with app.app_context():
        real_owner = User.query.filter_by(email="orders-order-owner@example.com").first()
        order = Order.query.filter_by(uuid=order_uuid).first()
        order.user_id = real_owner.id
        db.session.commit()

    resp = client.get(f"/api/v1/orders/{order_uuid}", headers=auth_headers(no_permission_token))
    assert resp.status_code == 404


def test_order_detail_guest_uuid_access_works(client, digital_product):
    created = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.get(f"/api/v1/orders/{created['uuid']}")
    assert resp.status_code == 200


def test_order_patch_requires_permission(client, no_permission_token, digital_product):
    created = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.patch(
        f"/api/v1/orders/{created['uuid']}", json={"orderStatus": "confirmed"}, headers=auth_headers(no_permission_token)
    )
    assert resp.status_code == 403


# ---- Order reference ----


def test_order_reference_unique_and_formatted(client, digital_product):
    first = _create_order(client, digital_product["slug"]).get_json()["data"]
    second = _create_order(client, digital_product["slug"]).get_json()["data"]
    assert first["reference"].startswith("WSF-")
    assert second["reference"].startswith("WSF-")
    assert first["reference"] != second["reference"]
    assert "id" not in first["reference"]


# ---- OrderItem snapshot integrity ----


def test_order_item_snapshot_survives_product_price_change(client, manager_token, product_admin_token, digital_product):
    order = _create_order(client, digital_product["slug"], quantity=2).get_json()["data"]
    item = order["items"][0]
    assert item["product_name"] == "The Founder's CV Template"
    assert item["product_sku"] == "WSF-TPL-1"
    assert item["unit_price"] == 29
    assert item["line_total"] == 58

    # Change the Product's price/name after the order exists.
    client.put(
        f"/api/v1/products/{digital_product['slug']}",
        json={"name": "Renamed Template", "price": 99, "currency": "USD", "type": "digital"},
        headers=auth_headers(product_admin_token),
    )

    refetched = client.get(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token)).get_json()["data"]
    refetched_item = refetched["items"][0]
    assert refetched_item["product_name"] == "The Founder's CV Template"
    assert refetched_item["unit_price"] == 29
    assert refetched_item["line_total"] == 58
    assert refetched["total_amount"] == 58


def test_order_item_links_to_current_product(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    fetched = client.get(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token)).get_json()["data"]
    assert fetched["items"][0]["product"]["slug"] == digital_product["slug"]


# ---- Totals / currency ----


def test_order_totals_and_currency(client, digital_product):
    order = _create_order(client, digital_product["slug"], quantity=3).get_json()["data"]
    assert order["subtotal_amount"] == 87
    assert order["total_amount"] == 87
    assert order["currency"] == "USD"


def test_order_rejects_mixed_currency(client, product_admin_token):
    usd = client.post(
        "/api/v1/products", json={"name": "USD Item", "price": 10, "currency": "USD"}, headers=auth_headers(product_admin_token)
    ).get_json()["data"]
    kes = client.post(
        "/api/v1/products", json={"name": "KES Item", "price": 500, "currency": "KES"}, headers=auth_headers(product_admin_token)
    ).get_json()["data"]

    resp = client.post(
        "/api/v1/orders",
        json={"email": "buyer@example.com", "items": [{"productSlug": usd["slug"]}, {"productSlug": kes["slug"]}]},
    )
    assert resp.status_code == 400


# ---- Order status transitions ----


def test_order_status_transition_forward_allowed(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.patch(
        f"/api/v1/orders/{order['uuid']}", json={"orderStatus": "confirmed"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["order_status"] == "confirmed"


def test_order_status_completed_cannot_revert_to_pending(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"orderStatus": "completed"}, headers=auth_headers(manager_token))

    resp = client.patch(
        f"/api/v1/orders/{order['uuid']}", json={"orderStatus": "pending"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422
    assert resp.get_json()["error"]["code"] == "invalid_status_transition"


# ---- Payment status ----


def test_payment_status_update_sets_paid_at(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    assert order["paid_at"] is None

    resp = client.patch(
        f"/api/v1/orders/{order['uuid']}",
        json={"paymentStatus": "paid", "paymentProvider": "mpesa", "paymentReference": "REF123"},
        headers=auth_headers(manager_token),
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["payment_status"] == "paid"
    assert data["paid_at"] is not None
    assert data["payment_provider"] == "mpesa"
    assert data["payment_reference"] == "REF123"


def test_payment_status_refunded_cannot_revert_to_unpaid(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"paymentStatus": "paid"}, headers=auth_headers(manager_token))
    client.patch(
        f"/api/v1/orders/{order['uuid']}",
        json={"paymentStatus": "refunded", "refundAmount": 29, "refundReason": "Customer requested."},
        headers=auth_headers(manager_token),
    )

    resp = client.patch(
        f"/api/v1/orders/{order['uuid']}", json={"paymentStatus": "unpaid"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 422

    refetched = client.get(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token)).get_json()["data"]
    assert refetched["refund_amount"] == 29
    assert refetched["refund_reason"] == "Customer requested."
    assert refetched["refunded_at"] is not None


# ---- Fulfillment status ----


def test_fulfillment_status_defaults_by_product_type(client, digital_product, physical_product):
    digital_order = _create_order(client, digital_product["slug"]).get_json()["data"]
    physical_order = _create_order(client, physical_product["slug"]).get_json()["data"]

    assert digital_order["fulfillment_status"] == "not_applicable"
    assert digital_order["requires_shipping"] is False
    assert physical_order["fulfillment_status"] == "unfulfilled"
    assert physical_order["requires_shipping"] is True


def test_fulfillment_status_update(client, manager_token, physical_product):
    order = _create_order(client, physical_product["slug"]).get_json()["data"]
    resp = client.patch(
        f"/api/v1/orders/{order['uuid']}", json={"fulfillmentStatus": "shipped"}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["fulfillment_status"] == "shipped"


# ---- Cancellation ----


def test_cancel_order_preserves_data(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.post(
        f"/api/v1/orders/{order['uuid']}/cancel", json={"reason": "Customer changed their mind."}, headers=auth_headers(manager_token)
    )
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert data["order_status"] == "cancelled"
    assert data["cancellation_reason"] == "Customer changed their mind."
    assert data["cancelled_at"] is not None
    assert len(data["items"]) == 1
    assert data["total_amount"] == order["total_amount"]


def test_cancel_already_completed_order_rejected(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"orderStatus": "completed"}, headers=auth_headers(manager_token))

    resp = client.post(f"/api/v1/orders/{order['uuid']}/cancel", headers=auth_headers(manager_token))
    assert resp.status_code == 422


# ---- Archive ----


def test_archive_and_unarchive_order(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]

    archived = client.post(f"/api/v1/orders/{order['uuid']}/archive", headers=auth_headers(manager_token))
    assert archived.status_code == 200
    assert archived.get_json()["data"]["archived"] is True

    default_list = client.get("/api/v1/orders", headers=auth_headers(manager_token)).get_json()["data"]
    assert order["reference"] not in [o["reference"] for o in default_list]

    archived_list = client.get("/api/v1/orders?archived=true", headers=auth_headers(manager_token)).get_json()["data"]
    assert order["reference"] in [o["reference"] for o in archived_list]

    # Still retrievable directly, archived or not.
    still_fetchable = client.get(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token))
    assert still_fetchable.status_code == 200

    unarchived = client.post(f"/api/v1/orders/{order['uuid']}/unarchive", headers=auth_headers(manager_token))
    assert unarchived.status_code == 200
    assert unarchived.get_json()["data"]["archived"] is False


# ---- Internal notes / privacy ----


def test_internal_notes_staff_only(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    added = client.post(
        f"/api/v1/orders/{order['uuid']}/notes", json={"body": "Customer requested invoice."}, headers=auth_headers(manager_token)
    )
    assert added.status_code == 201
    assert added.get_json()["data"]["notes"][0]["body"] == "Customer requested invoice."

    guest_view = client.get(f"/api/v1/orders/{order['uuid']}")
    assert guest_view.status_code == 200
    assert "notes" not in guest_view.get_json()["data"]

    staff_view = client.get(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token))
    assert staff_view.get_json()["data"]["notes"][0]["body"] == "Customer requested invoice."


def test_add_note_requires_permission(client, no_permission_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.post(
        f"/api/v1/orders/{order['uuid']}/notes", json={"body": "trying to add a note"}, headers=auth_headers(no_permission_token)
    )
    assert resp.status_code == 403


# ---- Safe deletion ----


def test_delete_unpaid_pending_order_allowed(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.delete(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token))
    assert resp.status_code == 200


def test_delete_paid_order_rejected(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"paymentStatus": "paid"}, headers=auth_headers(manager_token))

    resp = client.delete(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token))
    assert resp.status_code == 409
    assert resp.get_json()["error"]["code"] == "reference_conflict"


def test_delete_completed_order_rejected(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"orderStatus": "completed"}, headers=auth_headers(manager_token))

    resp = client.delete(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(manager_token))
    assert resp.status_code == 409


def test_delete_requires_permission(client, no_permission_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.delete(f"/api/v1/orders/{order['uuid']}", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


# ---- Audit / history ----


def test_order_history_records_status_changes(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"orderStatus": "confirmed"}, headers=auth_headers(manager_token))
    client.patch(f"/api/v1/orders/{order['uuid']}", json={"paymentStatus": "paid"}, headers=auth_headers(manager_token))

    history = client.get(f"/api/v1/orders/{order['uuid']}/history", headers=auth_headers(manager_token))
    assert history.status_code == 200
    entries = history.get_json()["data"]
    actions = [e["action"] for e in entries]
    assert "order.create" in actions
    assert "order.status_change" in actions
    assert "order.payment_status_change" in actions
    assert entries[0]["user"]["email"] == MANAGER_PAYLOAD["email"]


def test_order_history_requires_permission(client, no_permission_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.get(f"/api/v1/orders/{order['uuid']}/history", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


# ---- Filters ----


def test_order_filters_by_status_and_search(client, manager_token, digital_product):
    order_a = _create_order(client, digital_product["slug"], email="alice@example.com").get_json()["data"]
    _create_order(client, digital_product["slug"], email="bob@example.com")

    client.patch(f"/api/v1/orders/{order_a['uuid']}", json={"orderStatus": "confirmed"}, headers=auth_headers(manager_token))

    # Query params hit the Flask test client directly here (no JS apiClient
    # in between to camelCase->snake_case them), so the raw backend param
    # name is used, matching what the frontend's interceptor produces.
    by_status = client.get("/api/v1/orders?order_status=confirmed", headers=auth_headers(manager_token)).get_json()["data"]
    assert all(o["order_status"] == "confirmed" for o in by_status)
    assert order_a["reference"] in [o["reference"] for o in by_status]

    by_search = client.get("/api/v1/orders?query=alice", headers=auth_headers(manager_token)).get_json()["data"]
    assert all("alice" in o["email"] for o in by_search)

    by_reference = client.get(f"/api/v1/orders?query={order_a['reference']}", headers=auth_headers(manager_token)).get_json()["data"]
    assert len(by_reference) == 1
    assert by_reference[0]["reference"] == order_a["reference"]


def test_order_filters_by_product(client, manager_token, digital_product, physical_product):
    _create_order(client, digital_product["slug"])
    _create_order(client, physical_product["slug"])

    filtered = client.get(f"/api/v1/orders?product={physical_product['slug']}", headers=auth_headers(manager_token)).get_json()["data"]
    assert len(filtered) == 1
    assert filtered[0]["items"][0]["product_slug"] == physical_product["slug"]


# ---- Export ----


def test_export_requires_permission(client, no_permission_token, digital_product):
    _create_order(client, digital_product["slug"])
    resp = client.get("/api/v1/orders/export", headers=auth_headers(no_permission_token))
    assert resp.status_code == 403


def test_export_returns_csv(client, manager_token, digital_product):
    order = _create_order(client, digital_product["slug"]).get_json()["data"]
    resp = client.get("/api/v1/orders/export", headers=auth_headers(manager_token))
    assert resp.status_code == 200
    assert resp.content_type.startswith("text/csv")
    body = resp.get_data(as_text=True)
    assert "reference" in body.splitlines()[0]
    assert order["reference"] in body
    assert order["email"] in body
