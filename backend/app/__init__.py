from flask import Flask

from config import config_by_name
from app.extensions import db, migrate, jwt, cors, ma


def create_app(config_name="development"):
    """Application factory. Blueprints for each API resource
    (articles, people, jobs, opportunities, events, resources, ...)
    register here once implemented under app/api/.
    """
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["FRONTEND_URL"]}})
    ma.init_app(app)

    # from app.api.articles import articles_bp
    # app.register_blueprint(articles_bp, url_prefix="/api/v1/articles")
    # from app.api.media import media_bp
    # app.register_blueprint(media_bp, url_prefix="/api/v1/media")

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

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
