"""Shared rate-limit storage: Redis, with a database fallback. Never memory.

Flask-Limiter is configured with RATELIMIT_STORAGE_URI = "wsf-ratelimit://"
(config.py), which selects FallbackStorage below:

* Redis (REDIS_URL) is the normal store: one counter per limit and client,
  shared by every Gunicorn worker.
* If Redis can't be reached (at start-up or on any call), counters move to
  PostgreSQL (rate_limit_counters, app/models/rate_limit.py) and a WARNING
  is logged ("RATE LIMITING IS USING THE DATABASE FALLBACK"), repeated at
  most once a minute while it lasts. Redis is probed again every 30 seconds
  and used as soon as it answers (logged too).
* Per-process memory is never used: in-memory fallback is disabled in
  config and nothing here keeps counters in memory. If the database also
  fails, the error propagates (the request fails) rather than letting
  requests through unlimited.

Without REDIS_URL (development and tests) the database store is used and a
warning says so once. Production refuses to start without REDIS_URL
(config.require_production_settings).

rate_limit_status() reports the current store for `flask production-check`.
"""
import logging
import time
from limits.storage import Storage, storage_from_string
from sqlalchemy import text

logger = logging.getLogger("app")

_CURRENT = None  # the live FallbackStorage, for status reporting
PROBE_SECONDS = 30
WARN_EVERY_SECONDS = 60
CLEANUP_EVERY = 200


class DatabaseCounters:
    """Fixed-window counters in PostgreSQL, on their own connection (never
    the request's session/transaction)."""

    def __init__(self):
        self._calls = 0

    @staticmethod
    def _engine():
        from app.extensions import db

        return db.engine

    def incr(self, key, expiry, amount=1):
        self._calls += 1
        with self._engine().begin() as conn:
            count = conn.execute(text(
                "INSERT INTO rate_limit_counters (key, count, expires_at) "
                "VALUES (:key, :amount, now() + make_interval(secs => :expiry)) "
                "ON CONFLICT (key) DO UPDATE SET "
                "count = CASE WHEN rate_limit_counters.expires_at <= now() THEN :amount "
                "ELSE rate_limit_counters.count + :amount END, "
                "expires_at = CASE WHEN rate_limit_counters.expires_at <= now() "
                "THEN now() + make_interval(secs => :expiry) ELSE rate_limit_counters.expires_at END "
                "RETURNING count"), {"key": key, "amount": amount, "expiry": expiry}).scalar_one()
            if self._calls % CLEANUP_EVERY == 0:
                conn.execute(text("DELETE FROM rate_limit_counters WHERE expires_at <= now()"))
        return count

    def get(self, key):
        with self._engine().connect() as conn:
            value = conn.execute(text(
                "SELECT count FROM rate_limit_counters WHERE key = :key AND expires_at > now()"),
                {"key": key}).scalar()
        return int(value or 0)

    def get_expiry(self, key):
        with self._engine().connect() as conn:
            value = conn.execute(text(
                "SELECT expires_at FROM rate_limit_counters WHERE key = :key AND expires_at > now()"),
                {"key": key}).scalar()
        return value.timestamp() if value else time.time()

    def check(self):
        with self._engine().connect() as conn:
            return conn.execute(text("SELECT 1")).scalar() == 1

    def reset(self):
        with self._engine().begin() as conn:
            return conn.execute(text("DELETE FROM rate_limit_counters")).rowcount

    def clear(self, key):
        with self._engine().begin() as conn:
            conn.execute(text("DELETE FROM rate_limit_counters WHERE key = :key"), {"key": key})


class FallbackStorage(Storage):
    STORAGE_SCHEME = ["wsf-ratelimit"]

    def __init__(self, uri=None, wrap_exceptions=False, redis_url=None, **options):
        global _CURRENT
        super().__init__(uri, wrap_exceptions=wrap_exceptions, **options)
        self.redis_url = redis_url or None
        self.redis = storage_from_string(self.redis_url, socket_timeout=1, socket_connect_timeout=1) if self.redis_url else None
        self.database = DatabaseCounters()
        self._next_probe = 0.0
        self._last_warning = 0.0
        if self.redis is None:
            self.mode = "database"
            logger.warning("REDIS_URL is not set: rate limiting uses the database store (development/testing only).")
        elif self._redis_alive():
            self.mode = "redis"
        else:
            self._fall_back("Redis did not answer at start-up")
        _CURRENT = self

    # --- backend selection -------------------------------------------------------------
    def _redis_alive(self):
        try:
            return bool(self.redis.check())
        except Exception:
            return False

    def _fall_back(self, reason):
        self.mode = "database"
        self._next_probe = time.monotonic() + PROBE_SECONDS
        now = time.monotonic()
        if now - self._last_warning >= WARN_EVERY_SECONDS or self._last_warning == 0.0:
            self._last_warning = now
            logger.warning("RATE LIMITING IS USING THE DATABASE FALLBACK: %s (%s). Redis is retried every %ss.",
                           reason, self.redis_url_safe(), PROBE_SECONDS)

    def _maybe_recover(self):
        if self.redis is not None and self.mode == "database" and time.monotonic() >= self._next_probe:
            if self._redis_alive():
                self.mode = "redis"
                logger.warning("Rate limiting is back on Redis (%s).", self.redis_url_safe())
            else:
                self._next_probe = time.monotonic() + PROBE_SECONDS

    def _call(self, name, *args, **kwargs):
        self._maybe_recover()
        if self.mode == "redis":
            try:
                return getattr(self.redis, name)(*args, **kwargs)
            except Exception as exc:  # any Redis failure: switch, never drop the limit
                self._fall_back(f"Redis error on {name}: {exc.__class__.__name__}")
        return getattr(self.database, name)(*args, **kwargs)

    def redis_url_safe(self):
        """The Redis URL without any password."""
        if not self.redis_url:
            return "not configured"
        from urllib.parse import urlsplit

        parts = urlsplit(self.redis_url)
        host = parts.hostname or ""
        port = f":{parts.port}" if parts.port else ""
        return f"{parts.scheme}://{host}{port}{parts.path}"

    # --- Storage interface ---------------------------------------------------------------
    @property
    def base_exceptions(self):
        return Exception

    def incr(self, key, expiry, amount=1):
        return self._call("incr", key, expiry, amount=amount)

    def get(self, key):
        return self._call("get", key)

    def get_expiry(self, key):
        return self._call("get_expiry", key)

    def check(self):
        return self._call("check")

    def reset(self):
        return self._call("reset")

    def clear(self, key):
        return self._call("clear", key)


def rate_limit_status():
    """{"backend": "redis" | "database" | "unknown", "redis": safe URL}."""
    if _CURRENT is None:
        return {"backend": "unknown", "redis": "not configured"}
    _CURRENT._maybe_recover()
    return {"backend": _CURRENT.mode, "redis": _CURRENT.redis_url_safe()}
