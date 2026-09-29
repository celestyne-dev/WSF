"""Gunicorn configuration for production (Hostinger VPS: Nginx -> Gunicorn
-> Flask -> PostgreSQL — see DEPLOYMENT.md). Every value is overridable via
an environment variable so this file never needs editing per-machine; it
only encodes sensible defaults and the reasoning behind each one.

Usage (see DEPLOYMENT.md for the full systemd unit):
    cd /var/www/womenshapingfutures/backend
    source .venv/bin/activate
    gunicorn -c gunicorn.conf.py "run:app"

Never used for local development — `flask run` (via run.py) stays the dev
server; this file is only ever invoked by Gunicorn itself.
"""
import multiprocessing
import os

bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8000")

# No single worker count fits every Hostinger VPS tier — the classic
# (2 x CPU cores) + 1 heuristic is a reasonable starting point for a
# small-to-medium instance, but GUNICORN_WORKERS lets an operator pin an
# exact number once they know the box's real CPU/RAM budget (each worker
# is a full Python process with its own DB connection pool — see
# config.py's SQLALCHEMY_ENGINE_OPTIONS comment on why more workers isn't
# automatically better once Postgres's own max_connections enters the
# picture).
workers = int(os.environ.get("GUNICORN_WORKERS", multiprocessing.cpu_count() * 2 + 1))
worker_class = "sync"

# How long a worker may take to answer a request before Gunicorn kills and
# restarts it. 30s comfortably covers this app's slowest real endpoints
# (media upload + WebP variant generation) without letting one truly stuck
# worker hang indefinitely.
timeout = int(os.environ.get("GUNICORN_TIMEOUT", 30))
# graceful_timeout bounds how long an in-flight request gets to finish
# during a reload/restart (see DEPLOYMENT.md's deployment-sequence section
# on `systemctl reload`) before Gunicorn force-kills the worker anyway.
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", 30))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", 5))

# "-" means stdout/stderr — under systemd this lands in the journal
# (`journalctl -u womenshapingfutures`), which is where DEPLOYMENT.md's
# logging section expects to find it. Point these at real file paths
# instead only if systemd/journald isn't the chosen log destination.
accesslog = os.environ.get("GUNICORN_ACCESS_LOG", "-")
errorlog = os.environ.get("GUNICORN_ERROR_LOG", "-")
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Belt-and-suspenders alongside app/__init__.py's Werkzeug ProxyFix: this
# tells Gunicorn itself to accept forwarded-header rewriting only from the
# loopback address Nginx actually proxies from on a single-VPS deployment.
# If Nginx ever runs on a different host, replace "127.0.0.1" with that
# host's real address — never "*".
forwarded_allow_ips = os.environ.get("GUNICORN_FORWARDED_ALLOW_IPS", "127.0.0.1")
