"""Read-only deployment preflight for /lifetime (`flask --app run:app
learning-lifetime-preflight`). Reads the database only; never writes,
never prints a secret (no provider keys, no customer data).

Blockers (exit 1): anything that would stop /lifetime resolving to the
Lifetime page: an Article, a general Page or an Article Redirect owning the
flat slug "lifetime". Warning only: no active Lifetime plan (the page
still renders its informational state; nothing is for sale)."""
from app.extensions import db

SLUG = "lifetime"


def lifetime_preflight():
    from app.models.article import Article, Redirect
    from app.models.circle import CirclePlan, CirclePlanPrice
    from app.models.page import Page
    from app.services.circle_payments import plan_availability
    from app.utils.slugs import is_reserved_slug

    blockers, warnings = [], []
    article = Article.query.filter_by(slug=SLUG).first()
    if article is not None:
        blockers.append(f'An Article (id {article.id}, status {article.status}) uses the slug "{SLUG}".')
    page = Page.query.filter_by(slug=SLUG).first()
    if page is not None:
        blockers.append(f'A Page (id {page.id}, type {page.page_type}, status {page.status}) uses the slug "{SLUG}".')
    for redirect in Redirect.query.filter(db.or_(Redirect.from_slug == SLUG, Redirect.to_slug == SLUG)).all():
        blockers.append(f'An Article Redirect uses "{SLUG}" ({redirect.from_slug} -> {redirect.to_slug}).')
    if not is_reserved_slug(SLUG):
        blockers.append(f'"{SLUG}" is not a reserved route; content could claim it.')

    plans = []
    for plan in CirclePlan.query.filter_by(billing_interval="lifetime", status="active").order_by(CirclePlan.id).all():
        currencies = sorted(
            p.currency for p in CirclePlanPrice.query.filter_by(plan_id=plan.id, enabled=True).all()
        )
        availability = plan_availability(plan)
        plans.append({
            "name": plan.name,
            "slug": plan.slug,
            "founding": bool(plan.is_founding),
            "maxMembers": plan.max_members,
            "remaining": availability.get("remaining"),
            "currencies": currencies,
        })
        if not currencies:
            warnings.append(f'Lifetime plan "{plan.slug}" has no enabled currency, so it cannot be bought.')
    if not plans:
        warnings.append("No active Lifetime Circle plan: /lifetime shows its informational state and nothing is on sale.")
    return {"slug": SLUG, "blockers": blockers, "warnings": warnings, "plans": plans}
