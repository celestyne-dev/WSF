import os

import click
from flask import current_app

from app.extensions import db
from app.models.user import Role, User
from app.services.advertise import seed_advertise_page_and_offerings
from app.services.articles_workflow import publish_due_articles
from app.services.listing_maintenance import expire_closed_listings
from app.services.demo_seed import seed_demo_content
from app.services.footer import heal_footer_defaults
from app.services.geography import seed_countries
from app.services.navigation import seed_default_navigation
from app.services.pages import seed_system_pages
from app.services.rbac import seed_roles_and_permissions


def register_cli(app):
    @app.cli.command("seed-roles")
    def seed_roles_command():
        """Create the standard roles and permissions if they don't already exist."""
        seed_roles_and_permissions()
        click.echo("Roles and permissions seeded.")

    @app.cli.command("seed-geography")
    def seed_geography_command():
        """Load/refresh the Country reference table."""
        seed_countries()
        click.echo("Countries seeded.")

    @app.cli.command("seed-pages")
    def seed_pages_command():
        """Bootstrap the six required system Pages (About/Contact/Privacy/
        Terms/Cookies/Editorial Policy) that GET /pages/public/<key> and
        the header/footer navigation depend on. Create-only: an existing
        system Page (seeded before, or since edited by an admin) is never
        modified — see app/services/pages.py:seed_system_pages for why a
        plain reseed must not touch it. Safe to run repeatedly and safe on
        a real production database — same category as seed-roles/
        seed-geography/seed-navigation, never seed-demo.
        """
        created = seed_system_pages()
        if created:
            click.echo(f"Created {len(created)} missing system page(s): {', '.join(created)}.")
        else:
            click.echo("Created 0 missing system pages — all required system pages already exist.")

    @app.cli.command("seed-navigation")
    def seed_navigation_command():
        """Bootstrap/heal the "primary" and "secondary" header menus: adds
        any of the site's core top-level sections (Stories/Topics/People/
        Opportunities/Resources/Events/Community/Shop, and the utility bar's
        WSF Weekly Newsletter/Partner With Us/About) that are missing from
        an already-existing menu, without touching anything an admin has
        already configured or relabeled. Safe to run repeatedly and safe
        on a real production database — same category as seed-roles/
        seed-geography, never seed-demo. See
        app/services/navigation.py:seed_default_navigation for why a
        create-only seed guard isn't enough here.
        """
        seed_default_navigation()
        click.echo("Default navigation seeded/healed.")

    @app.cli.command("seed-footer")
    def seed_footer_command():
        """Bootstrap/heal the four canonical footer groups (Explore/
        Opportunities/About/Legal, at their existing footer_explore/
        footer_opportunity/footer_wsf/footer_legal keys): adds any
        canonical destination (Resources/Events/Community/Mentorship/
        Contact/Advertise/Cookies/Editorial Policy, etc.) missing from an
        already-existing group, without touching anything an admin has
        already configured, relabeled, or moved — including a legacy
        route link (e.g. url="/privacy") that already satisfies a
        canonical Page-backed destination, which is never duplicated. See
        app/services/footer.py:heal_footer_defaults for the full
        create-only-plus-heal contract. A required system Page that
        doesn't exist yet (run `flask seed-pages` first) is handled
        safely: that one destination is simply skipped until the page
        exists, nothing crashes. Safe to run repeatedly and safe on a
        real production database — same category as seed-roles/
        seed-geography/seed-pages/seed-navigation, never seed-demo. Does
        not touch footer settings or social links — see this command's
        own docstring in DEPLOYMENT.md for why that's out of scope here.
        """
        result = heal_footer_defaults()
        created, added = result["created_groups"], result["added_items"]
        if not created and not added:
            click.echo("Footer already has every canonical destination — nothing to heal.")
            return
        if created:
            click.echo(f"Created {len(created)} missing footer group(s): {', '.join(created)}.")
        if added:
            click.echo(f"Added {len(added)} missing footer link(s): " + ", ".join(f"{key}:{label}" for key, label in added) + ".")

    @app.cli.command("seed-advertise")
    def seed_advertise_command():
        """Bootstrap the /advertise page (AdvertisePage id=1) and its eight
        canonical AdvertiseOffering rows. GET /api/v1/advertise/public
        404s whenever that page row is missing or not "published" — the
        migration that creates it (e7f3b2a9c1d4) deliberately leaves it
        draft with no content, so a freshly migrated, properly
        bootstrapped site still 404s on /advertise until this runs (or
        an admin manually publishes it through AdminAdvertise). Only
        ever acts on a genuinely missing row or one that is still
        exactly that migration's untouched placeholder (see
        app/services/advertise.py:_is_untouched_placeholder for the
        strict, testable definition) — any other existing row, including
        one an administrator intentionally left in draft, is left
        completely alone, publication status included. Offerings are
        created one at a time by name, so an admin's own edit to any of
        the eight (or any other offering they created) is never
        duplicated or overwritten. Safe to run repeatedly and safe on a
        real production database — same category as seed-roles/
        seed-geography/seed-pages/seed-navigation/seed-footer, never
        seed-demo.
        """
        result = seed_advertise_page_and_offerings()
        page_action = result["page_action"]
        if page_action == "created":
            click.echo("Created and published the Advertise page (was missing).")
        elif page_action == "healed":
            click.echo("Published the Advertise page (was an untouched draft placeholder).")
        else:
            click.echo("Advertise page already has administrator content — left untouched.")
        created = result["offerings_created"]
        if created:
            click.echo(f"Created {len(created)} missing offering(s): {', '.join(created)}.")
        else:
            click.echo("Created 0 missing offerings — all eight canonical offerings already exist.")

    @app.cli.command("seed-demo")
    def seed_demo_command():
        """Load a representative slice of demo content (articles, jobs,
        opportunities, events, resources, navigation, homepage) for local
        verification against the real API. Run seed-roles/seed-geography
        first.
        """
        seed_demo_content()
        click.echo("Demo content seeded.")

    @app.cli.command("publish-due-content")
    def publish_due_content_command():
        """Publish every scheduled Article whose scheduled_at is now due.
        Meant to run on a schedule (cron/systemd timer) — see
        app/services/articles_workflow.py:publish_due_articles for the
        concurrency-safety/idempotency guarantees. Safe to run with zero
        due articles, and safe to re-run immediately after (already-
        published rows are re-checked and skipped, not re-published).
        Production invocation (Hostinger VPS, no Celery/Redis):
            cd /var/www/womenshapingfutures/backend && \\
              source .venv/bin/activate && flask --app run:app publish-due-content
        via a cron entry or systemd timer — this command does not modify
        any system-level scheduler itself. The explicit `--app run:app`
        matters: a bare `flask publish-due-content` lets Flask's CLI
        auto-discovery load the app factory with no config_name argument,
        silently defaulting to DevelopmentConfig regardless of
        FLASK_CONFIG (see production-check's own CONFIG_NAME check).
        """
        result = publish_due_articles()
        click.echo(
            f"Published {len(result['published'])}, skipped {len(result['skipped'])}, "
            f"failed {len(result['failed'])}."
        )
        for failure in result["failed"]:
            click.echo(f"  FAILED article_id={failure['article_id']}: {failure['error']}")
        # Same timer, one more idempotent step: Jobs/Opportunities whose
        # close date has passed get their stored status updated (the public
        # site already hides them by date; this keeps Studio accurate).
        _echo_expired(expire_closed_listings())
        # And: comment IP hashes past their 90 days are cleared.
        _echo_purged_ip_hashes()

    def _echo_purged_ip_hashes():
        from app.services.comments import purge_expired_ip_hashes

        click.echo(f"Cleared {purge_expired_ip_hashes()} expired comment IP hash(es).")

    @app.cli.command("comments-purge-ip-hashes")
    def comments_purge_ip_hashes_command():
        """Idempotent: clears comment IP hashes older than 90 days (their
        ip_hash_expires_at has passed). Also runs inside publish-due-content,
        the scheduled maintenance command."""
        _echo_purged_ip_hashes()

    def _echo_expired(changed):
        click.echo(f"Expired {len(changed['jobs'])} job(s); closed {len(changed['opportunities'])} opportunity(ies).")

    @app.cli.command("expire-closed-listings")
    def expire_closed_listings_command():
        """Idempotent: published/scheduled Jobs past their deadline or expiry
        date -> expired; published Opportunities past theirs -> closed.
        Never deletes or archives. Also runs inside publish-due-content."""
        _echo_expired(expire_closed_listings())

    @app.cli.command("create-superadmin")
    @click.option("--email", required=True)
    @click.option("--password", required=True)
    @click.option("--first-name", default="Super")
    @click.option("--last-name", default="Admin")
    def create_superadmin_command(email, password, first_name, last_name):
        """Create (or promote) a super_admin user for local/staging access."""
        role = Role.query.filter_by(name="super_admin").first()
        if role is None:
            click.echo("No super_admin role found — run `flask seed-roles` first.")
            return

        user = User.query.filter_by(email=email.lower()).first()
        existing = user is not None
        if user is None:
            user = User(email=email.lower(), first_name=first_name, last_name=last_name, is_verified=True)
            db.session.add(user)
        user.set_password(password)
        if role not in user.roles:
            user.roles.append(role)
        if existing:
            # New password and possibly a new role: credentials issued before
            # now end (app/services/refresh_sessions.py).
            from app.services.refresh_sessions import invalidate_user_sessions

            invalidate_user_sessions(user, "superadmin_cli")

        db.session.commit()
        click.echo(f"Super admin ready: {email}")

    @app.cli.command("learning-lifetime-preflight")
    def learning_lifetime_preflight_command():
        """Read-only: is /lifetime safe to launch? Reports slug conflicts
        (Article, general Page, Article Redirect: a deployment BLOCKER, exit
        1) and the active Lifetime plan(s) (name, slug, founding, max
        members, enabled currencies). No active plan is a warning only.
        Never writes, never prints secrets. Run as
        `flask --app run:app learning-lifetime-preflight`."""
        from app.services.lifetime_preflight import lifetime_preflight

        result = lifetime_preflight()
        click.echo(f'Flat slug "/{result["slug"]}": ' + ("CONFLICT" if result["blockers"] else "free (reserved route)"))
        if result["plans"]:
            for plan in result["plans"]:
                seats = "unlimited" if plan["maxMembers"] is None else f'{plan["maxMembers"]} (remaining {plan["remaining"]})'
                click.echo(
                    f'Active Lifetime plan: {plan["name"]} [{plan["slug"]}] founding={"yes" if plan["founding"] else "no"} '
                    f'max_members={seats} currencies={", ".join(plan["currencies"]) or "none"}'
                )
        else:
            click.echo("Active Lifetime plan: none")
        for warning in result["warnings"]:
            click.echo(f"WARNING: {warning}")
        for blocker in result["blockers"]:
            click.echo(f"BLOCKER: {blocker}")
        if result["blockers"]:
            click.echo("Lifetime preflight FAILED.")
            raise SystemExit(1)
        click.echo("Lifetime preflight PASSED.")

    @app.cli.command("legal-pages-audit")
    def legal_pages_audit_command():
        """Read-only: the four core legal Pages (status, dates, structure,
        SEO) and the browser technologies WSF's code actually uses. Prints
        no user data. Missing/unpublished legal Pages are highlighted;
        structural gaps are warnings. Always exits 0 (advisory)."""
        from app.services.legal_audit import INACTIVE_INTEGRATIONS, TECHNOLOGY_INVENTORY, audit_legal_pages

        result = audit_legal_pages()
        for row in result["pages"]:
            if not row["exists"]:
                click.echo(f"[{row['key']}] MISSING")
                continue
            click.echo(
                f"[{row['key']}] \"{row['title']}\" status={row['status']} public={'yes' if row['public'] else 'no'} "
                f"effective={row['effectiveDate'] or '-'} reviewed={row['lastReviewedAt'] or '-'} blocks={row['blocks']} "
                f"seo_title={'yes' if row['seoTitle'] else 'no'} seo_description={'yes' if row['seoDescription'] else 'no'} "
                f"canonical={row['canonical']}"
            )
            click.echo(f"    headings: {', '.join(row['headings']) or '(none)'}")
        for line in result["highlights"]:
            click.echo(f"HIGHLIGHT: {line}")
        for line in result["warnings"]:
            click.echo(f"WARNING: {line}")
        click.echo("Technologies in use (input for the Cookie Policy):")
        for tech in TECHNOLOGY_INVENTORY:
            click.echo(f"  - {tech['name']} | {tech['provider']} | {tech['category']} | {tech['storage']} | "
                       f"consent {'required' if tech['consentRequired'] else 'not required'} | {tech['purpose']} | {tech['duration']}")
        from app.services.legal_audit import configurable_status

        for name, configured in configurable_status():
            click.echo(f"Configurable integration: {name}: {'CONFIGURED (runs only with consent)' if configured else 'not configured (inactive)'}")
        click.echo(f"Configured but NOT active (no runtime integration): {', '.join(INACTIVE_INTEGRATIONS)}")
        from app.services.legal_audit import implementation_facts

        click.echo("Implementation facts (verified from code/config; input for the policy pages):")
        for section, line in implementation_facts():
            click.echo(f"  [{section}] {line}")

    @app.cli.command("csp-report-summary")
    @click.option("--days", default=7, show_default=True, help="Only violations seen in the last N days.")
    def csp_report_summary_command(days):
        """Read-only: CSP violations reported by browsers (aggregated, no
        personal data), newest first, and the current CSP mode. Use before
        switching CSP_MODE from report-only to enforce."""
        from datetime import datetime, timedelta, timezone

        from app.models.csp_violation import CspViolation

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = (CspViolation.query.filter(CspViolation.last_seen >= since)
                .order_by(CspViolation.count.desc(), CspViolation.last_seen.desc()).all())
        click.echo(f"CSP mode: {app.config.get('CSP_MODE')} | violations seen in the last {days} day(s): {len(rows)}")
        for row in rows:
            click.echo(f"  {row.count:>6}  {row.directive:<16} {row.blocked:<45} on {row.page_path} "
                       f"(first {row.first_seen:%Y-%m-%d}, last {row.last_seen:%Y-%m-%d %H:%M})")

    @app.cli.command("production-check")
    def production_check_command():
        """Read-only pre-flight check for a production deployment. Verifies
        presence/shape of critical configuration WITHOUT printing any
        secret value, and never touches the database (no migration, no
        seed, no write) — safe to run repeatedly, including against a live
        deployment, as a deploy-script sanity gate (see DEPLOYMENT.md).
        Exits non-zero on any failure so it can gate a deploy script.

        Must always be invoked as `flask --app run:app production-check`
        (never bare `flask production-check`) — see DEPLOYMENT.md §11/§13.
        A bare invocation lets Flask's CLI auto-discovery call the app
        factory with no config_name argument, which defaults to
        DevelopmentConfig regardless of FLASK_CONFIG; this command's own
        CONFIG_NAME check below exists specifically to still catch that
        mistake and fail loudly rather than reporting PASSED against the
        wrong app.
        """
        from config import require_production_settings

        problems = []
        warnings = []

        # Proves which config actually loaded (see app/__init__.py's
        # CONFIG_NAME) rather than leaving an operator to infer it from the
        # absence of a startup error — the dangerous case this guards
        # against is FLASK_CONFIG being unset/wrong so the process silently
        # ran DevelopmentConfig on what was meant to be the production VPS.
        click.echo(
            f"Active config: FLASK_CONFIG={current_app.config.get('CONFIG_NAME')!r} "
            f"-> ENV={current_app.config.get('ENV')!r}, DEBUG={current_app.debug}"
        )

        # Which store rate limiting is really using right now (never a
        # password). "database" in production means Redis is down or
        # unreachable: a WARNING, not silently accepted.
        from app.services.rate_limit_storage import rate_limit_status

        rl = rate_limit_status()
        click.echo(f"Rate-limit store: {rl['backend']} (Redis: {rl['redis']}); CSP mode: {current_app.config.get('CSP_MODE')}")
        if rl["backend"] != "redis":
            warnings.append(f"Rate limiting is using the {rl['backend']} store, not Redis. Check REDIS_URL and the Redis service.")

        try:
            require_production_settings(current_app)
        except RuntimeError as exc:
            # require_production_settings' own message is already
            # secret-free (it names which variable is missing/placeholder,
            # never its value) — safe to echo directly.
            problems.append(str(exc))

        # CONFIG_NAME (not ENV) is the authoritative check here: it's set
        # directly from the config_name create_app() actually received,
        # with no separate layer that could itself default to something
        # misleading. This must be a hard failure, never a warning — a
        # bare `flask production-check` (no `--app run:app`) has Flask's
        # own CLI auto-discovery call create_app() with NO argument,
        # silently loading DevelopmentConfig regardless of FLASK_CONFIG
        # in the environment, which is exactly the scenario this check
        # exists to catch. See DEPLOYMENT.md §13/§11 for why every
        # production Flask CLI invocation must say `--app run:app`.
        config_name = current_app.config.get("CONFIG_NAME")
        if config_name != "production":
            problems.append(
                f"CONFIG_NAME is {config_name!r}, not 'production' — this process did not "
                f"load ProductionConfig. If this was invoked as a bare `flask <command>` "
                f"without `--app run:app`, Flask's CLI auto-discovery silently defaults to "
                f"the development app factory regardless of FLASK_CONFIG. Re-run every "
                f"production CLI command as `flask --app run:app <command>` (see DEPLOYMENT.md)."
            )
        if current_app.debug:
            problems.append("DEBUG is True — must be False in production.")
        if current_app.config.get("TRUSTED_PROXY_COUNT", 0) < 1:
            warnings.append("TRUSTED_PROXY_COUNT is 0 — expected >=1 behind Nginx.")

        media_root = current_app.config.get("MEDIA_ROOT")
        if not media_root:
            problems.append("MEDIA_ROOT is not set.")
        elif not os.path.isdir(media_root):
            warnings.append(f"MEDIA_ROOT does not exist yet: {media_root} (create it before first upload).")
        elif not os.access(media_root, os.W_OK):
            problems.append(f"MEDIA_ROOT is not writable by this process: {media_root}")

        if problems:
            click.echo("PRODUCTION CHECK FAILED:")
            for p in problems:
                click.echo(f"  ✗ {p}")
            for w in warnings:
                click.echo(f"  ! {w}")
            raise SystemExit(1)

        click.echo("PRODUCTION CHECK PASSED.")
        for w in warnings:
            click.echo(f"  ! {w}")
