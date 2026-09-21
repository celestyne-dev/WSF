import click

from app.extensions import db
from app.models.user import Role, User
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
