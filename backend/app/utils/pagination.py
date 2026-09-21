from flask import current_app, request


def paginate(query, schema=None, default_per_page=None, max_per_page=None):
    """Paginate a SQLAlchemy query from `page`/`per_page` query params and
    return {"items": [...], "meta": {...}} using the app's consistent
    pagination metadata shape.
    """
    default_per_page = default_per_page or current_app.config["DEFAULT_PAGE_SIZE"]
    max_per_page = max_per_page or current_app.config["MAX_PAGE_SIZE"]

    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", default_per_page, type=int)
    per_page = max(1, min(per_page, max_per_page))

    result = query.paginate(page=page, per_page=per_page, error_out=False)
    items = schema.dump(result.items, many=True) if schema is not None else result.items

    return {
        "items": items,
        "meta": {
            "page": result.page,
            "per_page": result.per_page,
            "total": result.total,
            "total_pages": result.pages,
            "has_next": result.has_next,
            "has_prev": result.has_prev,
        },
    }
