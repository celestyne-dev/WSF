from datetime import date


def generate_order_reference(order):
    """A human-friendly, unique, immutable order reference — e.g.
    "WSF-2026-000123". Called once, right after the order has been
    flushed and has an id, so the id (already guaranteed unique by the
    database) can be used directly rather than maintaining a separate
    per-year sequence table.
    """
    year = order.created_at.year if order.created_at else date.today().year
    return f"WSF-{year}-{order.id:06d}"
