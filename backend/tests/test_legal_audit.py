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


def _frontend_storage_keys(src):
    keys = set()
    for path in src.rglob("*.js*"):
        if ".test." in path.name:
            continue
        text = path.read_text()
        keys |= set(re.findall(r"""(?:KEY|_KEY)\s*=\s*['"](wsf[\w-]*)['"]""", text))
        keys |= {m.split(":")[0] for m in re.findall(r"`(wsf-[\w-]+):", text)}
    return keys


def _keys_missing_from_inventory(keys):
    from app.services.legal_audit import TECHNOLOGY_INVENTORY

    # A key may be named in an entry's name or, when one key has several
    # storage modes, in each mode's storage field ("sessionStorage (key)").
    listed = " ".join(f"{t['name']} {t['storage']}" for t in TECHNOLOGY_INVENTORY)
    return sorted(k for k in keys if k not in listed)


def test_every_frontend_storage_key_is_in_the_inventory():
    keys = _frontend_storage_keys(Path(__file__).resolve().parents[2] / "frontend" / "src")
    assert keys, "no storage keys found"
    assert _keys_missing_from_inventory(keys) == []


def test_video_players_are_preferences_and_ad_trackers_inactive():
    from app.services.legal_audit import INACTIVE_INTEGRATIONS, TECHNOLOGY_INVENTORY

    video = next(t for t in TECHNOLOGY_INVENTORY if t["name"].startswith("Embedded video players"))
    assert video["category"] == "preferences" and video["consentRequired"] is True
    # Every Marketing technology is a configurable third party (inactive until
    # its ID is set) that requires consent.
    marketing = [t for t in TECHNOLOGY_INVENTORY if t["category"] == "marketing"]
    assert {t["configKey"] for t in marketing} == {"linkedinPartnerId", "metaPixelId"}
    assert all(t["consentRequired"] for t in marketing)
    assert INACTIVE_INTEGRATIONS == ("Google Search Console",)
    ga = next(t for t in TECHNOLOGY_INVENTORY if t["name"].startswith("Google Analytics 4"))
    assert ga["category"] == "analytics" and ga["consentRequired"] is True and ga["configKey"] == "ga4MeasurementId"


def test_newsletter_popup_is_listed_in_both_storage_modes():
    from app.services.legal_audit import TECHNOLOGY_INVENTORY

    modes = [t for t in TECHNOLOGY_INVENTORY if "(wsf_newsletter_popup)" in t["storage"]]
    by_storage = {t["storage"].split(" ")[0]: t for t in modes}
    assert set(by_storage) == {"sessionStorage", "localStorage"} and len(modes) == 2
    session, local = by_storage["sessionStorage"], by_storage["localStorage"]
    assert (session["category"], session["consentRequired"]) == ("essential", False)
    assert "does not persist across visits" in session["purpose"]
    assert (local["category"], local["consentRequired"]) == ("preferences", True)
    assert "default 14 days" in local["duration"] and "default 365 days" in local["duration"]
    assert "Effective:" in local["duration"] and "Physical:" in local["duration"]


def test_unknown_frontend_storage_keys_are_still_caught(tmp_path):
    """Matching names OR storage fields must not let an unlisted key through."""
    (tmp_path / "thing.js").write_text("export const THING_KEY = 'wsf_unlisted_thing'\n")
    keys = _frontend_storage_keys(tmp_path)
    assert keys == {"wsf_unlisted_thing"}
    assert _keys_missing_from_inventory(keys) == ["wsf_unlisted_thing"]


def test_implementation_facts_cover_the_newsletter(app):
    from app.services.legal_audit import implementation_facts

    with app.app_context():
        lines = [line for section, line in implementation_facts() if section == "Newsletter"]
    text = " ".join(lines)
    assert "double opt-in" in text and "only confirmed subscribers are exported" in text
    assert "provider-neutral" in text and "legacy_unconfirmed=" in text
    assert "@" not in text  # counts only, never addresses


def test_implementation_facts_flag_a_missing_footer_address(app):
    from app.extensions import db
    from app.services.legal_audit import implementation_facts
    from app.services.site_settings import save_site_identity

    with app.app_context():
        email_lines = [line for section, line in implementation_facts() if section == "Email"]
        assert any(line.startswith("WARNING: email footer postal address is NOT SET") for line in email_lines)
        save_site_identity({"site_name": "Women Shaping Futures", "postal_address": "Illustrative Street 1"})
        db.session.commit()
        email_lines = [line for section, line in implementation_facts() if section == "Email"]
        assert "Email footer postal address: set in Studio." in email_lines
