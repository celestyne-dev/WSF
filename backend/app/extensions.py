from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_marshmallow import Marshmallow
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
ma = Marshmallow()

# Rate limiting: Redis shared by every Gunicorn worker, with a PostgreSQL
# fallback while Redis is unavailable; never per-process memory
# (app/services/rate_limit_storage.py; RATELIMIT_* in config.py). No
# storage_uri here: it comes from app config. get_remote_address reads
# request.remote_addr, which only reflects the real client IP once ProxyFix
# (see app/__init__.py) has rewritten it from X-Forwarded-For.
import app.services.rate_limit_storage  # noqa: E402,F401  (registers the wsf-ratelimit:// scheme)

limiter = Limiter(key_func=get_remote_address, default_limits=[])
