from flask import Flask

from config import config_by_name
from app.extensions import cors, db, jwt, ma, migrate


def create_app(config_name="development"):
    """Application factory. Each versioned API namespace registers its own
    Blueprint (app/api/v1/*.py) with its url_prefix here once implemented.
    """
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_URL"]}})
    ma.init_app(app)

    from app import models  # noqa: F401  registers all models before migrations/queries run

    from app.auth.jwt_callbacks import register_jwt_callbacks
    from app.cli import register_cli
    from app.utils.responses import register_error_handlers, success_response

    register_jwt_callbacks(app)
    register_error_handlers(app)
    register_cli(app)

    from app.api.v1.admin import admin_bp
    from app.api.v1.analytics import analytics_bp
    from app.api.v1.articles import articles_bp
    from app.api.v1.authors import authors_bp
    from app.api.v1.auth import auth_bp
    from app.api.v1.events import events_bp
    from app.api.v1.jobs import jobs_bp
    from app.api.v1.media import media_bp
    from app.api.v1.newsletter import newsletter_bp
    from app.api.v1.nominations import nominations_bp
    from app.api.v1.advertise import advertise_bp
    from app.api.v1.community import community_bp
    from app.api.v1.mentorship import mentorship_bp
    from app.api.v1.opportunities import opportunities_bp
    from app.api.v1.orders import orders_bp
    from app.api.v1.organizations import organizations_bp
    from app.api.v1.partnerships import partnerships_bp
    from app.api.v1.people import people_bp
    from app.api.v1.products import products_bp
    from app.api.v1.public import public_bp
    from app.api.v1.redirects import redirects_bp
    from app.api.v1.resources import resources_bp
    from app.api.v1.search import search_bp
    from app.api.v1.sponsors import sponsors_bp
    from app.api.v1.submissions import submissions_bp
    from app.api.v1.taxonomy import categories_bp, series_bp, topics_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(media_bp, url_prefix="/api/v1/media")
    app.register_blueprint(public_bp, url_prefix="/api/v1/public")
    app.register_blueprint(articles_bp, url_prefix="/api/v1/articles")
    app.register_blueprint(topics_bp, url_prefix="/api/v1/topics")
    app.register_blueprint(categories_bp, url_prefix="/api/v1/categories")
    app.register_blueprint(series_bp, url_prefix="/api/v1/series")
    app.register_blueprint(authors_bp, url_prefix="/api/v1/authors")
    app.register_blueprint(people_bp, url_prefix="/api/v1/people")
    app.register_blueprint(redirects_bp, url_prefix="/api/v1/redirects")
    app.register_blueprint(jobs_bp, url_prefix="/api/v1/jobs")
    app.register_blueprint(opportunities_bp, url_prefix="/api/v1/opportunities")
    app.register_blueprint(events_bp, url_prefix="/api/v1/events")
    app.register_blueprint(resources_bp, url_prefix="/api/v1/resources")
    app.register_blueprint(newsletter_bp, url_prefix="/api/v1/newsletter")
    app.register_blueprint(submissions_bp, url_prefix="/api/v1/submissions")
    app.register_blueprint(nominations_bp, url_prefix="/api/v1/nominations")
    app.register_blueprint(partnerships_bp, url_prefix="/api/v1/partnerships")
    app.register_blueprint(organizations_bp, url_prefix="/api/v1/organizations")
    app.register_blueprint(products_bp, url_prefix="/api/v1/products")
    app.register_blueprint(orders_bp, url_prefix="/api/v1/orders")
    app.register_blueprint(search_bp, url_prefix="/api/v1/search")
    app.register_blueprint(analytics_bp, url_prefix="/api/v1/analytics")
    app.register_blueprint(sponsors_bp, url_prefix="/api/v1/sponsors")
    app.register_blueprint(advertise_bp, url_prefix="/api/v1/advertise")
    app.register_blueprint(community_bp, url_prefix="/api/v1/community")
    app.register_blueprint(mentorship_bp, url_prefix="/api/v1/mentorship")

    @app.get("/api/v1/health")
    def health():
        return success_response({"status": "ok"})

    if app.debug:
        # Convenience only: in local development Flask can serve MEDIA_URL
        # straight from MEDIA_ROOT so there's no need to run Nginx just to
        # preview uploads. In production, Nginx serves MEDIA_URL directly
        # from the filesystem and this route is never reached.
        from flask import send_from_directory

        @app.get(f"{app.config['MEDIA_URL']}<path:filename>")
        def media(filename):
            return send_from_directory(app.config["MEDIA_ROOT"], filename)

    return app
