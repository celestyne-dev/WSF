from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.commerce import Order, OrderItem, Product
from app.schemas.commerce import OrderInputSchema, OrderSchema, OrderStatusInputSchema
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

orders_bp = Blueprint("orders", __name__)
api = Api(orders_bp)

order_schema = OrderSchema()


def _optional_user():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    # current_user is a LocalProxy — `is not None` is always True even when
    # it wraps None, so normalize through truthiness (which the proxy
    # correctly delegates to the wrapped object) instead.
    return current_user if current_user else None


class OrderListResource(Resource):
    """Checkout is public (guest checkout allowed — `email` is required,
    `user_id` is only set when a valid session happens to be present).
    Payment gateway integration (M-Pesa Daraja/STK Push) is a pluggable
    service that isn't wired up yet; orders are created as
    'pending_payment' and moved to 'paid' via the status endpoint below
    once that's built.
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
            currency=currencies.pop(),
            total_amount=0,
        )
        total = 0
        for item in data["items"]:
            product = products[item["product_slug"]]
            quantity = item.get("quantity", 1)
            order.items.append(
                OrderItem(product=product, quantity=quantity, unit_price=product.price, currency=product.currency)
            )
            total += product.price * quantity
        order.total_amount = total

        db.session.add(order)
        db.session.commit()
        return success_response(order_schema.dump(order), status=201)

    @permission_required("orders.manage")
    def get(self):
        query = Order.query.order_by(Order.created_at.desc())
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
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
        if order.user_id is not None:
            user = _optional_user()
            is_owner = user is not None and order.user_id == user.id
            is_staff = user is not None and user.has_permission("orders.manage")
            if not is_owner and not is_staff:
                raise ApiError("Order not found.", 404, code="not_found")

        return success_response(order_schema.dump(order))


class OrderStatusResource(Resource):
    @permission_required("orders.manage")
    def patch(self, order_uuid):
        order = Order.query.filter_by(uuid=order_uuid).first()
        if order is None:
            raise ApiError("Order not found.", 404, code="not_found")

        data = OrderStatusInputSchema().load(request.get_json(silent=True) or {})
        order.status = data["status"]
        if data.get("payment_provider"):
            order.payment_provider = data["payment_provider"]
        if data.get("payment_reference"):
            order.payment_reference = data["payment_reference"]
        db.session.commit()
        return success_response(order_schema.dump(order))


api.add_resource(OrderListResource, "")
api.add_resource(OrderDetailResource, "/<string:order_uuid>")
api.add_resource(OrderStatusResource, "/<string:order_uuid>/status")
