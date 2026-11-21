"""legal-pages-audit: read-only report of legal Pages and technologies."""
import re
from pathlib import Path


def _seed(app, **overrides):
    from app.extensions import db
    from app.services.pages import seed_system_pages

    with app.app_context():
        seed_system_pages()
        from app.models.page import Page

        for key, fields in overrides.items():
            page = Page.query.filter_by(key=key).first()
            for k, v in fields.items():
                setattr(page, k, v)
        db.session.commit()


def _snapshot(app):
    from app.models.page import Page

    with app.app_context():
        return [(p.key, p.status, p.title, p.effective_date, p.last_reviewed_at, p.updated_at) for p in Page.query.order_by(Page.key)]


def test_audit_reports_pages_and_does_not_mutate(app):
    from datetime import date

    _seed(app, terms={"status": "draft"}, privacy={"effective_date": date(2026, 11, 1)})
    before = _snapshot(app)
    out = app.test_cli_runner().invoke(args=["legal-pages-audit"])
    assert out.exit_code == 0
    text = out.output
    assert '[privacy] "Privacy Policy" status=published public=yes effective=2026-11-01' in text
    assert 'HIGHLIGHT: The "terms" page is draft' in text
    assert '"cookies": never marked as reviewed.' in text
    assert "Configured but NOT active" in text and "Meta Pixel" in text
    assert _snapshot(app) == before  # read-only


def test_missing_page_highlighted(app):
    out = app.test_cli_runner().invoke(args=["legal-pages-audit"])
    assert "[editorial-policy] MISSING" in out.output and 'HIGHLIGHT: The "privacy" page does not exist' in out.output


def test_every_frontend_storage_key_is_in_the_inventory():
    from app.services.legal_audit import TECHNOLOGY_INVENTORY

    src = Path(__file__).resolve().parents[2] / "frontend" / "src"
    listed = " ".join(t["name"] for t in TECHNOLOGY_INVENTORY)
    keys = set()
    for path in src.rglob("*.js*"):
        if ".test." in path.name:
            continue
        text = path.read_text()
        keys |= set(re.findall(r"""(?:KEY|_KEY)\s*=\s*['"](wsf[\w-]*)['"]""", text))
        keys |= {m.split(":")[0] for m in re.findall(r"`(wsf-[\w-]+):", text)}
    assert keys, "no storage keys found"
    for key in keys:
        assert key in listed, f"{key} is written by the frontend but missing from TECHNOLOGY_INVENTORY"
