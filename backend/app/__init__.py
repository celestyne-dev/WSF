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

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    return app
