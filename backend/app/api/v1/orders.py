import csv
import io
from datetime import date, datetime, timezone

from flask import Blueprint, Response, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.audit import AuditLog
from app.models.commerce import (
    FULFILLMENT_STATUSES,
    Order,
    OrderItem,
    OrderNote,
    ORDER_STATUS_TERMINAL,
    PAYMENT_STATUS_TERMINAL,
    Product,
)
from app.schemas.commerce import (
    OrderAdminUpdateSchema,
    OrderCancelInputSchema,
    OrderHistoryEntrySchema,
    OrderInputSchema,
    OrderNoteInputSchema,
    OrderSchema,
)
from app.services.audit import log_action
from app.services.orders import generate_order_reference
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

orders_bp = Blueprint("orders", __name__)
api = Api(orders_bp)

order_schema = OrderSchema()
order_history_schema = OrderHistoryEntrySchema()

_EXPORT_COLUMNS = (
    "reference",
    "created_at",
    "customer_name",
    "email",
    "total_amount",
    "currency",
    "order_status",
    "payment_status",
    "fulfillment_status",
)


def _optional_user():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    # current_user is a LocalProxy — `is not None` is always True even when
    # it wraps None, so normalize through truthiness (which the proxy
    # correctly delegates to the wrapped object) instead.
    return current_user if current_user else None


def _current_manager_or_none():
    user = _optional_user()
    if user and user.has_permission("orders.manage"):
        return user
    return None


def _dump_order(order, can_manage):
    """Internal notes are staff-only regardless of who else can see this
    order (the guest UUID-holder / logged-in owner both see their own
    transaction details — same as any order-confirmation page — but never
    another admin's internal notes).
    """
    data = order_schema.dump(order)
    if not can_manage:
        data.pop("notes", None)
    return data


def _apply_equality_status_filters(query):
    return apply_equality_filters(query, Order, request.args, ["order_status", "payment_status", "fulfillment_status", "currency"])


def _build_order_query(args):
    query = Order.query.order_by(Order.created_at.desc())
    query = _apply_equality_status_filters(query)
    query = apply_search(query, Order, args, ["reference", "email", "customer_name"], param="query")

    if args.get("archived") == "true":
        query = query.filter(Order.archived.is_(True))
    else:
        # Archived orders stay searchable/retrievable by reference or
        # detail lookup, but drop out of the default operational list —
        # archiving must never make data harder to find on purpose.
        query = query.filter(Order.archived.is_(False))

    product_slug = args.get("product")
    if product_slug:
        query = query.filter(Order.items.any(OrderItem.product_slug == product_slug))

    # The frontend's apiClient interceptor camelCase->snake_cases every
    # query param before it hits the wire (see frontend/src/api/client.js),
    # so `dateFrom`/`dateTo` arrive here as `date_from`/`date_to`.
    date_from = args.get("date_from")
    if date_from:
        query = query.filter(Order.created_at >= date_from)
    date_to = args.get("date_to")
    if date_to:
        query = query.filter(Order.created_at <= f"{date_to} 23:59:59")

    return query


def _validate_order_status_transition(old, new):
    if old == new:
        return
    if old in ORDER_STATUS_TERMINAL and new in ("pending", "confirmed", "processing"):
        raise ApiError(
            f'This order cannot move from "{old}" back to "{new}".', 422, code="invalid_status_transition"
        )


def _validate_payment_status_transition(old, new):
    if old == new:
        return
    if old in PAYMENT_STATUS_TERMINAL and new in ("unpaid", "pending"):
        raise ApiError(
            f'Payment status cannot move from "{old}" back to "{new}".', 422, code="invalid_status_transition"
        )


def _apply_admin_update(order, data, user):
    """Applies whichever admin-editable fields were actually sent, each
    change individually audit-logged via the app's existing audit trail
    (app/services/audit.py) — no second history mechanism.
    """
    if "order_status" in data:
        new_status = data["order_status"]
        _validate_order_status_transition(order.order_status, new_status)
        if new_status != order.order_status:
            log_action(user, "order.status_change", "Order", order.id, changes={"field": "order_status", "from": order.order_status, "to": new_status})
            order.order_status = new_status

    if "payment_status" in data:
        new_status = data["payment_status"]
        _validate_payment_status_transition(order.payment_status, new_status)
        if new_status != order.payment_status:
            log_action(user, "order.payment_status_change", "Order", order.id, changes={"field": "payment_status", "from": order.payment_status, "to": new_status})
            if new_status == "paid" and order.payment_status != "paid":
                order.paid_at = datetime.now(timezone.utc)
            if new_status in ("refunded", "partially_refunded"):
                order.refunded_at = datetime.now(timezone.utc)
            order.payment_status = new_status

    if "fulfillment_status" in data:
        new_status = data["fulfillment_status"]
        if new_status != order.fulfillment_status:
            log_action(user, "order.fulfillment_status_change", "Order", order.id, changes={"field": "fulfillment_status", "from": order.fulfillment_status, "to": new_status})
            order.fulfillment_status = new_status

    if "payment_provider" in data:
        order.payment_provider = data["payment_provider"]
    if "payment_reference" in data:
        order.payment_reference = data["payment_reference"]
    if "refund_amount" in data:
        order.refund_amount = data["refund_amount"]
    if "refund_reason" in data:
        order.refund_reason = data["refund_reason"]


class OrderListResource(Resource):
    """Checkout is public (guest checkout allowed — `email` is required,
    `user_id` is only set when a valid session happens to be present).
    Payment gateway integration (M-Pesa Daraja/STK Push) is a pluggable
    service that isn't wired up yet; orders are created as
    payment_status='pending' and moved to 'paid' via the admin update
    endpoint below once that's built. This task is Orders CMS/
    administration only — it does not add a cart or checkout UI.
    """

    def post(self):
        data = OrderInputSchema().load(request.get_json(silent=True) or {})
        user = _optional_user()

        slugs = [item["product_slug"] for item in data["items"]]
        products = {p.slug: p for p in Product.query.filter(Product.slug.in_(slugs), Product.is_active.is_(True))}
        missing = [slug for slug in slugs if slug not in products]
        if missing:
            raise ApiError(f'Product "{missing[0]}" not found or unavailable.', 404, code="not_found")

        currencies = {products[slug].currency for slug in slugs}
        if len(currencies) > 1:
            raise ApiError("All items in an order must use the same currency.", 400, code="mixed_currency")

        order = Order(
            user_id=user.id if user else None,
            email=data["email"],
            customer_name=data.get("customer_name"),
            phone=data.get("phone"),
            billing_address=data.get("billing_address"),
            shipping_address=data.get("shipping_address"),
            currency=currencies.pop(),
            order_status="pending",
            payment_status="pending",
            total_amount=0,
        )
        subtotal = 0
        requires_shipping = False
        for item in data["items"]:
            product = products[item["product_slug"]]
            quantity = item.get("quantity", 1)
            line_total = product.price * quantity
            order.items.append(
                OrderItem(
                    product=product,
                    product_name=product.name,
                    product_sku=product.sku,
                    product_slug=product.slug,
                    product_type=product.type,
                    quantity=quantity,
                    unit_price=product.price,
                    line_total=line_total,
                    currency=product.currency,
                )
            )
            subtotal += line_total
            requires_shipping = requires_shipping or product.type == "physical"
        order.subtotal_amount = subtotal
        order.total_amount = subtotal
        order.fulfillment_status = "unfulfilled" if requires_shipping else "not_applicable"

        db.session.add(order)
        db.session.flush()
        order.reference = generate_order_reference(order)
        db.session.commit()
        log_action(user, "order.create", "Order", order.id, changes={"reference": order.reference})
        return success_response(_dump_order(order, can_manage=True), status=201)

    @permission_required("orders.manage")
    def get(self):
        query = _build_order_query(request.args)
        result = paginate(query, order_schema)
        return success_response(result["items"], meta=result["meta"])


class OrderDetailResource(Resource):
    def get(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")

        # A guest order (no account) has no owner to check against — the
        # unguessable UUID itself is the access control, same as any order
        # confirmation link. A logged-in order is only visible to its
        # owner or staff.
        can_manage = _current_manager_or_none() is not None
        if order.user_id is not None and not can_manage:
            user = _optional_user()
            is_owner = user is not None and order.user_id == user.id
            if not is_owner:
                raise ApiError("Order not found.", 404, code="not_found")

        return success_response(_dump_order(order, can_manage))

    @permission_required("orders.manage")
    def patch(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")

        data = OrderAdminUpdateSchema().load(request.get_json(silent=True) or {})
        _apply_admin_update(order, data, current_user)
        db.session.commit()
        return success_response(_dump_order(order, can_manage=True))

    @permission_required("orders.manage")
    def delete(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")

        # Orders are business records, not ordinary editable content — a
        # hard delete is only ever safe for a record that never became
        # real (no payment ever recorded, never progressed past pending).
        # Everything else must be archived instead.
        if order.payment_status not in ("unpaid", "pending", "failed") or order.order_status not in ("pending", "cancelled"):
            raise ApiError(
                "This order cannot be deleted because it contains payment or fulfillment history. Archive it instead.",
                409,
                code="reference_conflict",
            )

        log_action(current_user, "order.delete", "Order", order.id, changes={"reference": order.reference})
        db.session.delete(order)
        db.session.commit()
        return success_response({"deleted": True})


class OrderCancelResource(Resource):
    @permission_required("orders.manage")
    def post(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")
        if order.order_status in ORDER_STATUS_TERMINAL:
            raise ApiError(
                f'This order cannot be cancelled — it is already "{order.order_status}".',
                422,
                code="invalid_status_transition",
            )

        data = OrderCancelInputSchema().load(request.get_json(silent=True) or {})
        log_action(current_user, "order.cancel", "Order", order.id, changes={"from": order.order_status, "reason": data.get("reason")})
        order.order_status = "cancelled"
        order.cancelled_at = datetime.now(timezone.utc)
        order.cancellation_reason = data.get("reason")
        db.session.commit()
        return success_response(_dump_order(order, can_manage=True))


class OrderArchiveResource(Resource):
    @permission_required("orders.manage")
    def post(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")
        order.archived = True
        order.archived_at = datetime.now(timezone.utc)
        db.session.commit()
        log_action(current_user, "order.archive", "Order", order.id)
        return success_response(_dump_order(order, can_manage=True))


class OrderUnarchiveResource(Resource):
    @permission_required("orders.manage")
    def post(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")
        order.archived = False
        order.archived_at = None
        db.session.commit()
        log_action(current_user, "order.unarchive", "Order", order.id)
        return success_response(_dump_order(order, can_manage=True))


class OrderNoteListResource(Resource):
    @permission_required("orders.manage")
    def post(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")

        data = OrderNoteInputSchema().load(request.get_json(silent=True) or {})
        note = OrderNote(order=order, user=current_user, body=data["body"])
        db.session.add(note)
        db.session.commit()
        log_action(current_user, "order.note_add", "Order", order.id)
        return success_response(_dump_order(order, can_manage=True), status=201)


class OrderHistoryResource(Resource):
    @permission_required("orders.manage")
    def get(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")

        entries = (
            AuditLog.query.filter_by(entity_type="Order", entity_id=str(order.id))
            .order_by(AuditLog.created_at.desc())
            .all()
        )
        return success_response(order_history_schema.dump(entries, many=True))


class OrderExportResource(Resource):
    @permission_required("orders.manage")
    def get(self):
        query = _build_order_query(request.args)
        orders = query.limit(5000).all()

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(_EXPORT_COLUMNS)
        for order in orders:
            writer.writerow(
                [
                    order.reference or "",
                    order.created_at.isoformat() if order.created_at else "",
                    order.customer_name or "",
                    order.email,
                    order.total_amount,
                    order.currency,
                    order.order_status,
                    order.payment_status,
                    order.fulfillment_status,
                ]
            )

        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=orders-{date.today().isoformat()}.csv"
        return response


api.add_resource(OrderListResource, "")
api.add_resource(OrderExportResource, "/export")
api.add_resource(OrderDetailResource, "/<string:order_uuid>")
api.add_resource(OrderCancelResource, "/<string:order_uuid>/cancel")
api.add_resource(OrderArchiveResource, "/<string:order_uuid>/archive")
api.add_resource(OrderUnarchiveResource, "/<string:order_uuid>/unarchive")
api.add_resource(OrderNoteListResource, "/<string:order_uuid>/notes")
api.add_resource(OrderHistoryResource, "/<string:order_uuid>/history")
