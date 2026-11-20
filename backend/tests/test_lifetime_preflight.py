"""`flask learning-lifetime-preflight`: read-only, blocks on a /lifetime
slug conflict, warns (only) when no Lifetime plan is active."""


def _run(app):
    return app.test_cli_runner().invoke(args=["learning-lifetime-preflight"])


def test_clean_database_passes_with_no_plan_warning(app):
    result = _run(app)
    assert result.exit_code == 0, result.output
    assert 'Flat slug "/lifetime": free (reserved route)' in result.output
    assert "Active Lifetime plan: none" in result.output
    assert "WARNING: No active Lifetime Circle plan" in result.output
    assert "PASSED" in result.output


def test_active_plan_is_reported(app):
    from app.extensions import db
    from app.models.circle import CirclePlan, CirclePlanPrice

    with app.app_context():
        plan = CirclePlan(slug="lifetime-founding", name="Founding Lifetime", billing_interval="lifetime", status="active",
                          price=500, currency="USD", is_founding=True, max_members=100)
        db.session.add(plan)
        db.session.flush()
        db.session.add_all([CirclePlanPrice(plan_id=plan.id, currency="USD", amount_minor=50000, enabled=True),
                            CirclePlanPrice(plan_id=plan.id, currency="KES", amount_minor=5000000, enabled=True),
                            CirclePlanPrice(plan_id=plan.id, currency="EUR", amount_minor=45000, enabled=False)])
        db.session.commit()
    result = _run(app)
    assert result.exit_code == 0, result.output
    assert "Active Lifetime plan: Founding Lifetime [lifetime-founding] founding=yes max_members=100 (remaining 100) currencies=KES, USD" in result.output
    assert "WARNING" not in result.output


def test_slug_conflicts_are_blockers(app):
    from app.extensions import db
    from app.models.article import Redirect
    from app.models.page import Page

    with app.app_context():
        db.session.add(Page(key="lifetime-legacy", slug="lifetime", page_type="general", title="Old", status="draft", content=[]))
        db.session.add(Redirect(from_slug="lifetime", to_slug="somewhere"))
        db.session.commit()
    result = _run(app)
    assert result.exit_code == 1
    assert "CONFLICT" in result.output and result.output.count("BLOCKER:") == 2 and "FAILED" in result.output
