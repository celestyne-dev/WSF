"""Centralized logging setup — a consistent, practical format across
environments (no structured/JSON logging platform, no external log
shipper: see production-readiness task scope). Deliberately small: this
sets a formatter and level on Flask's own logger, it does not introduce a
new logging framework.
"""
import logging
import sys


_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(app):
    """Attach a single stream handler with a consistent
    timestamp/level/logger/message format to the app's logger, honoring
    LOG_LEVEL (falls back to INFO for an unrecognized value rather than
    raising over a typo'd env var).

    Gunicorn's own `--access-logfile`/`--error-logfile` (see
    gunicorn.conf.py) handle the HTTP access log line; this handles the
    application's own logger.exception/.warning/.info calls (auth events,
    scheduler results, unexpected-exception tracebacks — see
    app/utils/responses.py's global error handler). Never log request
    bodies, Authorization headers, or full submission content here — see
    each call site's own comments on what it deliberately omits.
    """
    level = getattr(logging, app.config.get("LOG_LEVEL", "INFO"), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))

    app.logger.handlers = [handler]
    app.logger.setLevel(level)
    app.logger.propagate = False

    app.logger.info("Application starting (env=%s, debug=%s)", app.config.get("ENV"), app.debug)
