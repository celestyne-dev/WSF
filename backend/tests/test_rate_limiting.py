"""Rate limiting: Redis shared store, database fallback, never memory
(app/services/rate_limit_storage.py), named endpoint limits
(app/services/rate_limits.py)."""
import logging
import shutil
import socket
import subprocess
import time

import pytest

from app.extensions import limiter
from app.services.rate_limit_storage import FallbackStorage, rate_limit_status
from app.services.rate_limits import LIMITS, limit


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture()
def redis_server():
    binary = shutil.which("redis-server")
    if binary is None:
        pytest.skip("redis-server is not installed")
    port = _free_port()
    proc = subprocess.Popen([binary, "--port", str(port), "--save", "", "--appendonly", "no"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"redis://127.0.0.1:{port}/0"
    import redis

    client = redis.Redis.from_url(url)
    for _ in range(50):
        try:
            client.ping()
            break
        except Exception:
            time.sleep(0.1)
    yield {"url": url, "proc": proc, "client": client}
    proc.terminate()
    proc.wait(timeout=5)


def _signup(client, n):
    return client.post("/api/v1/auth/register", json={"email": f"rl{n}@example.com", "password": "supersecret1",
                                                       "first_name": "R", "last_name": "L"})


def test_limiter_storage_is_never_process_memory(app):
    storage = limiter._storage
    assert isinstance(storage, FallbackStorage)
    assert app.config["RATELIMIT_IN_MEMORY_FALLBACK_ENABLED"] is False
    assert app.config["RATELIMIT_SWALLOW_ERRORS"] is False
    assert storage.mode in ("redis", "database")


def test_database_store_enforces_signup_limit(app, client):
    # Tests run without REDIS_URL: the database store is in use.
    assert rate_limit_status()["backend"] == "database"
    codes = [_signup(client, i).status_code for i in range(6)]
    assert codes[:5] == [201] * 5 and codes[5] == 429


def test_named_limits_cover_the_required_endpoints():
    for name in ("login", "signup", "password_reset_request", "password_reset_submit", "newsletter_unsubscribe",
                 "contact", "story_submission", "story_image_upload", "comment_create", "comment_report"):
        assert LIMITS[name]
    with pytest.raises(KeyError):
        limit("no_such_limit")


def test_unsubscribe_by_email_is_rate_limited(client):
    codes = [client.post("/api/v1/newsletter/unsubscribe", json={"email": "x@example.com"}).status_code
             for _ in range(6)]
    assert codes[5] == 429 and all(c != 429 for c in codes[:5])


def test_redis_is_the_shared_store_when_configured(app, redis_server):
    storage = FallbackStorage(redis_url=redis_server["url"])
    assert storage.mode == "redis"
    with app.app_context():
        assert storage.incr("k1", 60) == 1 and storage.incr("k1", 60) == 2
    assert int(redis_server["client"].get("LIMITS:k1")) == 2  # really in Redis
    with app.app_context():
        from app.extensions import db

        assert db.session.execute(db.text("SELECT count(*) FROM rate_limit_counters")).scalar() == 0


def test_redis_failure_moves_to_database_loudly_and_comes_back(app, redis_server, caplog):
    storage = FallbackStorage(redis_url=redis_server["url"])
    with app.app_context():
        storage.incr("k2", 60)
        redis_server["proc"].terminate()
        redis_server["proc"].wait(timeout=5)
        with caplog.at_level(logging.WARNING, logger="app"):
            assert storage.incr("k2", 60) == 1  # counted in the database, not lost, not memory
        assert storage.mode == "database"
        assert any("DATABASE FALLBACK" in r.getMessage() for r in caplog.records)
        from app.extensions import db

        assert db.session.execute(db.text("SELECT count FROM rate_limit_counters WHERE key = 'k2'")).scalar() == 1
        assert storage.incr("k2", 60) == 2


def test_unreachable_redis_at_startup_uses_database_and_warns(app, caplog):
    with caplog.at_level(logging.WARNING, logger="app"):
        storage = FallbackStorage(redis_url=f"redis://127.0.0.1:{_free_port()}/0")
    assert storage.mode == "database"
    assert any("DATABASE FALLBACK" in r.getMessage() for r in caplog.records)
    with app.app_context():
        assert storage.incr("k3", 60) == 1 and storage.get("k3") == 1 and storage.get_expiry("k3") > time.time()


def test_window_resets_after_expiry(app):
    storage = FallbackStorage(redis_url=None)
    with app.app_context():
        assert storage.incr("k4", 1) == 1
        time.sleep(1.2)
        assert storage.incr("k4", 1) == 1  # a new window, counted from 1


def test_production_requires_redis_url():
    from flask import Flask

    from config import require_production_settings
    from tests.test_production_config import _bare_app

    with pytest.raises(RuntimeError, match="REDIS_URL"):
        require_production_settings(_bare_app(REDIS_URL=None))
    require_production_settings(_bare_app())  # the helper's valid config includes REDIS_URL
    assert Flask  # imported for parity with the helper module


def test_safe_url_hides_password():
    storage = FallbackStorage.__new__(FallbackStorage)
    storage.redis_url = "redis://:s3cret@cache.internal:6380/2"
    assert storage.redis_url_safe() == "redis://cache.internal:6380/2"
