from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.commerce import Product
from app.models.resource import Resource as ResourceModel
from app.schemas.commerce import ProductInputSchema, ProductSchema
from app.services.slugs import generate_unique_slug
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

products_bp = Blueprint("products", __name__)
api = Api(products_bp)

product_schema = ProductSchema()


class ProductListResource(Resource):
    def get(self):
        query = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc())
        result = paginate(query, product_schema)
        return success_response(result["items"], meta=result["meta"])

    @permission_required("settings.manage")
    def post(self):
        data = ProductInputSchema().load(request.get_json(silent=True) or {})

        resource = None
        if data.get("resource_slug"):
            resource = ResourceModel.query.filter_by(slug=data["resource_slug"]).first()
            if resource is None:
                raise ApiError(f"Resource \"{data['resource_slug']}\" not found.", 404, code="not_found")

        fields = {k: v for k, v in data.items() if k not in ("slug", "resource_slug")}
        product = Product(**fields, resource=resource)
        product.slug = data.get("slug") or generate_unique_slug(Product, data["name"])
        db.session.add(product)
        db.session.commit()
        return success_response(product_schema.dump(product), status=201)


class ProductDetailResource(Resource):
    def get(self, slug):
        product = Product.query.filter_by(slug=slug).first()
        if product is None:
            raise ApiError("Product not found.", 404, code="not_found")
        return success_response(product_schema.dump(product))


api.add_resource(ProductListResource, "")
api.add_resource(ProductDetailResource, "/<string:slug>")
