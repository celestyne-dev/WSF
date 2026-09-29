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

# In-process, in-memory rate limiting — no Redis (see task scope: this app
# runs as a handful of Gunicorn worker *processes*, each with its own
# independent in-memory counter, not threads sharing one process). That
# means the effective limit for a single client is roughly
# "per-endpoint limit x number of Gunicorn workers" rather than a single
# global count, and counters reset on every worker restart/deploy. This is
# a deliberate, documented trade-off (see DEPLOYMENT.md's rate-limiting
# section) to avoid adding Redis purely for this — it still meaningfully
# blocks the scripted/bulk-submission and login-brute-force cases these
# limits target, which don't need cross-process precision to be stopped.
# get_remote_address reads request.remote_addr, which only reflects the
# real client IP once ProxyFix (see app/__init__.py) has rewritten it from
# X-Forwarded-For — both must be configured together behind Nginx.
limiter = Limiter(key_func=get_remote_address, storage_uri="memory://", default_limits=[])
