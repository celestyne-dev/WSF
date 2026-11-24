#!/usr/bin/env bash
# Women Shaping Futures: restore test for an off-site backup.
#
# Restores a backup into an ISOLATED temporary database and a temporary
# directory, checks it, then removes both. It never touches the live
# database or the live media directories.
#
#   usage: wsf-restore-test.sh [latest | daily/<name> | monthly/<name>]
#
# Checks:
#   1. checksum of the downloaded object matches its .sha256
#   2. decrypts with the PRIVATE age key (keep it off the VPS; run this on
#      the restore machine, or copy the key in only for the test)
#   3. inner checksums (CONTENTS.sha256) match
#   4. pg_restore into a temporary database succeeds
#   5. alembic_version equals EXPECTED_ALEMBIC_HEAD (when set) and the MANIFEST
#   6. representative record counts (users, articles, pages, media)
#   7. sampled media rows point at files that exist in the restored files
#   8. `flask --app run:app production-check` passes with the restored
#      environment file and the temporary database (unless SKIP_APP_CHECK=1)
#   9. cleanup: drop the temporary database, delete the temporary files
# Exit status is non-zero if any check fails.
set -Eeuo pipefail
umask 077

ENV_FILE="${WSF_BACKUP_ENV:-/etc/womenshapingfutures/backup.env}"
log() { printf '%s wsf-restore-test: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "FAILED: $*"; exit 1; }

[[ -f "$ENV_FILE" ]] || die "configuration file $ENV_FILE not found"
# Export everything it sets: pg_dump/psql/rclone read PG* and RCLONE_* from the environment.
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a
: "${RCLONE_REMOTE:?RCLONE_REMOTE is required}"
: "${AGE_IDENTITY_FILE:?AGE_IDENTITY_FILE (the PRIVATE key, for restore tests only) is required}"
BACKEND_DIR="${BACKEND_DIR:-/var/www/womenshapingfutures/backend}"
FLASK_BIN="${FLASK_BIN:-$BACKEND_DIR/.venv/bin/flask}"
TARGET="${1:-latest}"

for tool in pg_restore psql createdb dropdb tar age rclone sha256sum; do
  command -v "$tool" >/dev/null || die "$tool is not installed"
done

WORK="$(mktemp -d "${BACKUP_WORK_DIR:-/var/tmp}/wsf-restore.XXXXXX")"
TEMP_DB="wsf_restore_test_$(date -u +%Y%m%d%H%M%S)"
created_db=0
cleanup() {
  if (( created_db )); then dropdb --if-exists "$TEMP_DB" && log "temporary database $TEMP_DB dropped"; fi
  rm -rf "$WORK" && log "temporary files removed"
}
trap cleanup EXIT

if [[ "$TARGET" == "latest" ]]; then
  OBJECT="$(rclone lsf --files-only "$RCLONE_REMOTE/daily" | grep -E '\.tar\.age$' | sort | tail -1)"
  [[ -n "$OBJECT" ]] || die "no daily backups found"
  TARGET="daily/$OBJECT"
fi
log "testing $TARGET"

# 1. Download + outer checksum
rclone copyto "$RCLONE_REMOTE/$TARGET" "$WORK/backup.tar.age"
EXPECTED="$(rclone cat "$RCLONE_REMOTE/$TARGET.sha256" | cut -d' ' -f1)"
[[ -n "$EXPECTED" ]] || die "no checksum file for $TARGET"
ACTUAL="$(sha256sum "$WORK/backup.tar.age" | cut -d' ' -f1)"
[[ "$ACTUAL" == "$EXPECTED" ]] || die "checksum mismatch for $TARGET"
log "1 checksum OK"

# 2-3. Decrypt + inner checksums
age --decrypt --identity "$AGE_IDENTITY_FILE" --output "$WORK/bundle.tar" "$WORK/backup.tar.age"
tar --extract --file="$WORK/bundle.tar" --directory="$WORK"
(cd "$WORK" && sha256sum --check --quiet CONTENTS.sha256) || die "inner checksums do not match"
log "2-3 decrypted, contents verified"

# 4. Restore into an isolated database
createdb "$TEMP_DB"
created_db=1
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$TEMP_DB" "$WORK/db.dump"
log "4 restored into $TEMP_DB"

q() { psql -X -A -t -d "$TEMP_DB" -c "$1"; }

# 5. Alembic revision
REVISION="$(q 'SELECT version_num FROM alembic_version')"
MANIFEST_REVISION="$(sed -n 's/^alembic_revision=//p' "$WORK/MANIFEST")"
[[ "$REVISION" == "$MANIFEST_REVISION" ]] || die "restored revision $REVISION differs from MANIFEST $MANIFEST_REVISION"
if [[ -n "${EXPECTED_ALEMBIC_HEAD:-}" ]]; then
  [[ "$REVISION" == "$EXPECTED_ALEMBIC_HEAD" ]] || die "restored revision $REVISION, expected $EXPECTED_ALEMBIC_HEAD"
fi
log "5 alembic revision $REVISION"

# 6. Representative records
for table in users articles pages media; do
  log "6 $table: $(q "SELECT count(*) FROM $table") rows"
done
[[ "$(q 'SELECT count(*) FROM users')" -ge 1 ]] || die "the restored users table is empty"

# 7. Media files
mkdir -p "$WORK/files"
tar --extract --gzip --file="$WORK/files.tar.gz" --directory="$WORK/files"
MEDIA_ROOT_IN_BACKUP="$(sed -n 's/^media_root=//p' "$WORK/MANIFEST")"
missing=0; checked=0
while IFS= read -r stored; do
  [[ -n "$stored" ]] || continue
  checked=$((checked + 1))
  [[ -f "$WORK/files/${MEDIA_ROOT_IN_BACKUP#/}/originals/$stored" ]] || { missing=$((missing + 1)); log "7 missing media file originals/$stored"; }
done < <(q "SELECT stored_filename FROM media ORDER BY random() LIMIT 20")
(( missing == 0 )) || die "$missing of $checked sampled media files are missing"
log "7 media: $checked sampled files present ($(find "$WORK/files" -type f | wc -l) files restored)"

# 8. Application production-check against the restored environment
if [[ "${SKIP_APP_CHECK:-0}" != "1" ]]; then
  APP_ENV_IN_BACKUP="$(sed -n 's/^app_env_file=//p' "$WORK/MANIFEST")"
  RESTORED_ENV="$WORK/files/${APP_ENV_IN_BACKUP#/}"
  [[ -f "$RESTORED_ENV" ]] || die "the backend environment file is missing from the backup"
  (
    set -a
    # shellcheck source=/dev/null
    source "$RESTORED_ENV"
    set +a
    export DATABASE_URL="postgresql:///$TEMP_DB"
    cd "$BACKEND_DIR" && "$FLASK_BIN" --app run:app production-check
  ) || die "production-check failed against the restored backup"
  log "8 production-check passed"
else
  log "8 production-check skipped (SKIP_APP_CHECK=1)"
fi

log "restore test PASSED for $TARGET"
