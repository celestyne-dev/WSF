import os

import click
from flask import current_app

from app.extensions import db
from app.models.user import Role, User
from app.services.advertise import seed_advertise_page_and_offerings
from app.services.articles_workflow import publish_due_articles
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
              source .venv/bin/activate && flask publish-due-content
        via a cron entry or systemd timer — this command does not modify
        any system-level scheduler itself.
        """
        result = publish_due_articles()
        click.echo(
            f"Published {len(result['published'])}, skipped {len(result['skipped'])}, "
            f"failed {len(result['failed'])}."
        )
        for failure in result["failed"]:
            click.echo(f"  FAILED article_id={failure['article_id']}: {failure['error']}")

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
        if user is None:
            user = User(email=email.lower(), first_name=first_name, last_name=last_name, is_verified=True)
            db.session.add(user)
        user.set_password(password)
        if role not in user.roles:
            user.roles.append(role)

        db.session.commit()
        click.echo(f"Super admin ready: {email}")

    @app.cli.command("production-check")
    def production_check_command():
        """Read-only pre-flight check for a production deployment. Verifies
        presence/shape of critical configuration WITHOUT printing any
        secret value, and never touches the database (no migration, no
        seed, no write) — safe to run repeatedly, including against a live
        deployment, as a deploy-script sanity gate (see DEPLOYMENT.md).
        Exits non-zero on any failure so it can gate a deploy script.
        """
        from config import require_production_settings

        problems = []
        warnings = []

        try:
            require_production_settings(current_app)
        except RuntimeError as exc:
            # require_production_settings' own message is already
            # secret-free (it names which variable is missing/placeholder,
            # never its value) — safe to echo directly.
            problems.append(str(exc))

        if current_app.config.get("ENV") != "production":
            warnings.append(f"FLASK_CONFIG is '{current_app.config.get('ENV')}', not 'production'.")
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
