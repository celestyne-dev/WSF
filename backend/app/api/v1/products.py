from datetime import date

from flask import Blueprint, request
from flask_jwt_extended import current_user, verify_jwt_in_request
from flask_restful import Api, Resource
from sqlalchemy import or_

from app.extensions import db
from app.models.commerce import OrderItem, Product, ProductCategory, ProductImage
from app.models.media import Media
from app.models.resource import Resource as ResourceModel
from app.schemas.commerce import ProductCategorySchema, ProductInputSchema, ProductSchema
from app.services.content_blocks import sanitize_content_blocks
from app.services.slugs import generate_unique_slug, validate_explicit_slug
from app.utils.filtering import apply_equality_filters, apply_search
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

products_bp = Blueprint("products", __name__)
api = Api(products_bp)

product_schema = ProductSchema()
product_category_schema = ProductCategorySchema()

# Public users never see pricing on a product that opted out of price
# disclosure — stripped from the dumped response rather than the field
# being conditionally excluded at the schema level, since visibility here
# depends on row data (price_visible), not on who's asking.
_PRICE_FIELDS = ("price", "sale_price")


def _require_active_user():
    verify_jwt_in_request()
    if not current_user or not current_user.is_active:
        raise ApiError("Account is inactive or no longer exists.", 403, code="forbidden")
    return current_user


def _current_user_or_none():
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return None
    if not current_user or not current_user.is_active:
        return None
    return current_user


def _require_manage():
    user = _require_active_user()
    if not user.has_permission("products.manage"):
        raise ApiError("You do not have permission to manage products.", 403, code="forbidden")
    return user


def _can_edit_or_none():
    try:
        return _require_manage()
    except Exception:
        return None


def _resolve_resource(resource_slug):
    if not resource_slug:
        return None
    resource = ResourceModel.query.filter_by(slug=resource_slug).first()
    if resource is None:
        raise ApiError(f'Resource "{resource_slug}" not found.', 404, code="not_found")
    return resource


def _resolve_category(category_id):
    if not category_id:
        return None
    category = db.session.get(ProductCategory, category_id)
    if category is None:
        raise ApiError("Product category not found.", 404, code="not_found")
    return category


def _resolve_gallery(media_ids):
    if not media_ids:
        return []
    found = {m.id: m for m in Media.query.filter(Media.id.in_(media_ids)).all()}
    missing = [mid for mid in media_ids if mid not in found]
    if missing:
        raise ApiError(f"Media #{missing[0]} not found.", 404, code="not_found")
    return [ProductImage(media_id=mid, position=i) for i, mid in enumerate(media_ids)]


def _dump_product(product, can_view_all):
    data = product_schema.dump(product)
    if not product.price_visible and not can_view_all:
        for field in _PRICE_FIELDS:
            data[field] = None
    return data


def _apply_fields(product, data, resource, category, gallery_images):
    product.name = data["name"]
    product.short_description = data.get("short_description")
    product.description = sanitize_content_blocks(data.get("description", []))
    product.cover_media_id = data.get("cover_media_id")
    product.resource = resource
    product.category = category
    product.images = gallery_images
    product.type = data.get("type", "digital")
    product.sku = data.get("sku")
    product.price = data.get("price", 0)
    product.sale_price = data.get("sale_price")
    product.currency = data.get("currency", "USD")
    product.price_visible = data.get("price_visible", True)
    product.track_inventory = data.get("track_inventory", False)
    product.stock_quantity = data.get("stock_quantity")
    product.shipping_notes = data.get("shipping_notes")
    product.purchase_url = data.get("purchase_url")
    product.featured = data.get("featured", False)
    product.status = data.get("status", "active")
    product.is_active = product.status == "active"
    product.seo = data.get("seo")
    if product.status == "active" and product.published_date is None:
        product.published_date = data.get("published_date") or date.today()
    elif data.get("published_date"):
        product.published_date = data["published_date"]


def _is_referenced(product):
    return OrderItem.query.filter_by(product_id=product.id).first() is not None


class ProductListResource(Resource):
    def get(self):
        user = _current_user_or_none()
        can_manage = bool(user and user.has_permission("products.manage"))

        query = Product.query.order_by(Product.featured.desc(), Product.published_date.desc())
        if can_manage:
            if request.args.get("status"):
                query = query.filter(Product.status == request.args["status"])
        else:
            query = query.filter(Product.status.in_(["active", "unavailable"]))

        apply_search_fields = ["name", "short_description"]
        query = apply_search(query, Product, request.args, apply_search_fields, param="query")
        query = apply_equality_filters(query, Product, request.args, ["type"])
        if request.args.get("category"):
            query = query.filter(Product.category.has(slug=request.args["category"]))
        if request.args.get("featured") == "true":
            query = query.filter(Product.featured.is_(True))
        if request.args.get("free") == "true":
            query = query.filter(Product.price == 0)
        max_price = request.args.get("maxPrice")
        if max_price:
            query = query.filter(Product.price <= int(max_price))

        result = paginate(query, schema=None)
        viewer_can_view_all = can_manage
        result["items"] = [_dump_product(p, viewer_can_view_all) for p in result["items"]]
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        _require_manage()
        data = ProductInputSchema().load(request.get_json(silent=True) or {})
        resource = _resolve_resource(data.get("resource_slug"))
        category = _resolve_category(data.get("category_id"))
        gallery_images = _resolve_gallery(data.get("gallery_media_ids", []))

        product = Product()
        if data.get("slug"):
            product.slug = validate_explicit_slug(Product, data["slug"])
        else:
            product.slug = generate_unique_slug(Product, data["name"])

        _apply_fields(product, data, resource, category, gallery_images)
        db.session.add(product)
        db.session.commit()
        return success_response(_dump_product(product, True), status=201)


class ProductDetailResource(Resource):
    def get(self, slug):
        product = Product.query.filter_by(slug=slug).first()
        if product is None:
            raise ApiError("Product not found.", 404, code="not_found")
        editor = _can_edit_or_none()
        publicly_visible = product.status in ("active", "unavailable")
        if not publicly_visible and not editor:
            raise ApiError("Product not found.", 404, code="not_found")
        return success_response(_dump_product(product, bool(editor)))

    def put(self, slug):
        product = Product.query.filter_by(slug=slug).first()
        if product is None:
            raise ApiError("Product not found.", 404, code="not_found")
        _require_manage()

        data = ProductInputSchema().load(request.get_json(silent=True) or {})
        resource = _resolve_resource(data.get("resource_slug"))
        category = _resolve_category(data.get("category_id"))
        gallery_images = _resolve_gallery(data.get("gallery_media_ids", []))

        if data.get("slug") and data["slug"] != product.slug:
            product.slug = validate_explicit_slug(Product, data["slug"], current_id=product.id)

        _apply_fields(product, data, resource, category, gallery_images)
        db.session.commit()
        return success_response(_dump_product(product, True))

    def delete(self, slug):
        product = Product.query.filter_by(slug=slug).first()
        if product is None:
            raise ApiError("Product not found.", 404, code="not_found")
        _require_manage()

        if _is_referenced(product):
            raise ApiError(
                "This product is referenced by one or more orders and can't be deleted. "
                "Archive it instead to keep historical order data intact.",
                409,
                code="reference_conflict",
            )

        db.session.delete(product)
        db.session.commit()
        return success_response({"deleted": True})


class ProductCategoryListResource(Resource):
    def get(self):
        categories = ProductCategory.query.order_by(ProductCategory.name).all()
        return success_response(product_category_schema.dump(categories, many=True))

    def post(self):
        _require_manage()
        data = request.get_json(silent=True) or {}
        name = (data.get("name") or "").strip()
        if not name:
            raise ApiError("Category name is required.", 422, code="validation_error")

        category = ProductCategory(name=name, description=data.get("description"))
        category.slug = generate_unique_slug(ProductCategory, name)
        db.session.add(category)
        db.session.commit()
        return success_response(product_category_schema.dump(category), status=201)


api.add_resource(ProductListResource, "")
api.add_resource(ProductDetailResource, "/<string:slug>")
api.add_resource(ProductCategoryListResource, "/categories")
