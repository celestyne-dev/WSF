import os

import click
from flask import current_app

from app.extensions import db
from app.models.user import Role, User
from app.services.articles_workflow import publish_due_articles
from app.services.demo_seed import seed_demo_content
from app.services.geography import seed_countries
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
