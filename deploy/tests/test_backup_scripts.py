"""End-to-end test of deploy/backup/wsf-backup.sh and wsf-restore-test.sh.

Uses a real PostgreSQL database (BACKUP_TEST_DATABASE, default wsf_mig: a
scratch database migrated to head), age, rclone with a local-folder "remote"
standing in for off-site storage, and temporary media directories. Skipped
when a tool is missing. Never touches a live database.
"""
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1] / "backup"
BACKUP = HERE / "wsf-backup.sh"
RESTORE = HERE / "wsf-restore-test.sh"
DB = os.environ.get("BACKUP_TEST_DATABASE", "wsf_mig")
PG = {"PGHOST": os.environ.get("PGHOST", "localhost"), "PGPORT": "5432", "PGUSER": "wsf",
      "PGPASSWORD": os.environ.get("PGPASSWORD", "wsf_dev_pw"), "PGDATABASE": DB}

pytestmark = pytest.mark.skipif(
    any(shutil.which(t) is None for t in ("pg_dump", "pg_restore", "psql", "createdb", "age", "age-keygen", "rclone")),
    reason="backup tooling not installed")


def _psql(sql, db=DB):
    return subprocess.run(["psql", "-X", "-A", "-t", "-d", db, "-c", sql], env={**os.environ, **PG},
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture()
def setup(tmp_path):
    if _psql("SELECT count(*) FROM information_schema.tables WHERE table_name = 'alembic_version'") != "1":
        pytest.skip(f"{DB} is not a migrated scratch database")
    _psql("DELETE FROM media WHERE uuid = 'backup-test'; DELETE FROM users WHERE email = 'backup-test@example.invalid'")
    _psql("INSERT INTO users (uuid, email, password_hash, first_name, last_name, is_active, is_verified, "
          "must_change_password, auth_version, created_at, updated_at) VALUES ('backup-test-user', "
          "'backup-test@example.invalid', 'x', 'B', 'T', true, false, false, 0, now(), now())")
    media = tmp_path / "srv" / "media"
    (media / "originals").mkdir(parents=True)
    (media / "originals" / "illustrative.png").write_bytes(b"\x89PNG illustrative")
    _psql("INSERT INTO media (uuid, original_filename, stored_filename, file_path, public_url, mime_type, created_at, "
          f"updated_at) VALUES ('backup-test', 'i.png', 'illustrative.png', '{media}/originals/illustrative.png', "
          "'/media/originals/illustrative.png', 'image/png', now(), now())")
    protected = tmp_path / "srv" / "protected"
    protected.mkdir()
    (protected / "toolkit.pdf").write_bytes(b"%PDF illustrative")
    app_env = tmp_path / "srv" / "backend.env"
    app_env.write_text("SECRET_KEY=PLAINTEXT-MARKER-should-never-appear-unencrypted\n")
    identity = tmp_path / "identity.txt"
    subprocess.run(["age-keygen", "-o", str(identity)], check=True, capture_output=True)
    recipients = tmp_path / "recipients.txt"
    recipients.write_text(subprocess.run(["age-keygen", "-y", str(identity)], check=True, capture_output=True,
                                         text=True).stdout)
    remote = tmp_path / "offsite"
    work = tmp_path / "work"
    work.mkdir()
    env_file = tmp_path / "backup.env"
    env_file.write_text("\n".join([
        *(f"{k}={v}" for k, v in PG.items()),
        f"MEDIA_ROOT={media}", f"PROTECTED_MEDIA_ROOT={protected}", f"APP_ENV_FILE={app_env}",
        f"AGE_RECIPIENTS_FILE={recipients}", f"RCLONE_REMOTE=:local:{remote}", f"BACKUP_WORK_DIR={work}",
        "DAILY_KEEP=2", "MONTHLY_KEEP=12", f"AGE_IDENTITY_FILE={identity}",
        f"EXPECTED_ALEMBIC_HEAD={_psql('SELECT version_num FROM alembic_version')}", "SKIP_APP_CHECK=1", ""]))
    env_file.chmod(0o600)
    yield {"env": env_file, "remote": remote, "work": work, "recipients": recipients}
    _psql("DELETE FROM media WHERE uuid = 'backup-test'; DELETE FROM users WHERE email = 'backup-test@example.invalid'")


def _run(script, setup, *args, now=None, extra=None):
    env = {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/root"), "WSF_BACKUP_ENV": str(setup["env"])}
    if now is not None:
        env["WSF_BACKUP_NOW"] = str(int(now.timestamp()))
    env.update(extra or {})
    return subprocess.run(["bash", str(script), *args], env=env, capture_output=True, text=True)


def _at(day, hour=2):
    return datetime(2026, 12, day, hour, 30, tzinfo=timezone.utc)


def test_backup_is_encrypted_offsite_verified_and_leaves_nothing_local(setup):
    res = _run(BACKUP, setup, now=_at(1))
    assert res.returncode == 0, res.stdout + res.stderr
    daily = sorted(p.name for p in (setup["remote"] / "daily").iterdir())
    assert daily == ["wsf-20261201T023000Z.tar.age", "wsf-20261201T023000Z.tar.age.sha256"]
    monthly = sorted(p.name for p in (setup["remote"] / "monthly").iterdir())
    assert monthly == ["wsf-2026-12.tar.age", "wsf-2026-12.tar.age.sha256"]
    blob = (setup["remote"] / "daily" / daily[0]).read_bytes()
    assert blob.startswith(b"age-encryption.org/v1") and b"PLAINTEXT-MARKER" not in blob
    assert list(setup["work"].iterdir()) == []  # no backup kept on the server
    assert "uploaded and verified" in res.stdout and "PGPASSWORD" not in res.stdout


def test_retention_keeps_the_newest_daily_backups(setup):
    for day in (2, 3, 4):
        assert _run(BACKUP, setup, now=_at(day)).returncode == 0
    names = sorted(p.name for p in (setup["remote"] / "daily").iterdir() if p.name.endswith(".tar.age"))
    assert names == ["wsf-20261203T023000Z.tar.age", "wsf-20261204T023000Z.tar.age"]  # DAILY_KEEP=2
    assert not (setup["remote"] / "monthly").exists()  # monthly copies only on the 1st


def test_restore_test_restores_into_a_temporary_database_and_cleans_up(setup):
    assert _run(BACKUP, setup, now=_at(5)).returncode == 0
    res = _run(RESTORE, setup, "latest")
    assert res.returncode == 0, res.stdout + res.stderr
    for line in ("1 checksum OK", "2-3 decrypted, contents verified", "4 restored into", "5 alembic revision",
                 "7 media: 1 sampled files present", "restore test PASSED", "temporary database"):
        assert line in res.stdout
    temp_db = res.stdout.split("4 restored into ")[1].split()[0]
    assert _psql(f"SELECT count(*) FROM pg_database WHERE datname = '{temp_db}'", db="postgres") == "0"


def test_restore_test_detects_a_corrupted_offsite_copy(setup):
    assert _run(BACKUP, setup, now=_at(6)).returncode == 0
    obj = next(p for p in (setup["remote"] / "daily").iterdir() if p.name.endswith(".tar.age"))
    data = bytearray(obj.read_bytes())
    data[-10] ^= 0xFF
    obj.write_bytes(bytes(data))
    res = _run(RESTORE, setup, "latest")
    assert res.returncode != 0 and "checksum mismatch" in res.stdout


def test_refuses_a_readable_config_or_a_private_key_as_recipient(setup):
    setup["env"].chmod(0o644)
    res = _run(BACKUP, setup, now=_at(7))
    assert res.returncode != 0 and "chmod 600" in res.stdout
    setup["env"].chmod(0o600)
    setup["recipients"].write_text("AGE-SECRET-KEY-1XXXXXXXX\n")
    res = _run(BACKUP, setup, now=_at(7))
    assert res.returncode != 0 and "PRIVATE key" in res.stdout
