"""Checkout Phase 1 test helper: give a legacy-priced CirclePlan/Resource
fixture its matching price row, via the SAME explicit whole-units ->
minor-units conversion the migration and legacy API writes use — so
existing payment tests keep exercising real stored price rows."""


def seed_legacy_price(obj):
    from app.models.circle import CirclePlan, CirclePlanPrice
    from app.models.resource import ResourcePrice
    from app.services.pricing import apply_legacy_price

    model = CirclePlanPrice if isinstance(obj, CirclePlan) else ResourcePrice
    apply_legacy_price(obj, obj.price or 0, obj.currency or "KES", model)
    return obj
