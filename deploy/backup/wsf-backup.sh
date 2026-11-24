#!/usr/bin/env bash
# Women Shaping Futures: encrypted, off-site backup (database + uploaded files
# + the backend environment file needed to restore).
#
#   1. pg_dump (custom format) and verify it can be listed by pg_restore
#   2. tar the public media, protected (purchasable) files and backend env file
#   3. bundle + encrypt with age to the PUBLIC recipient key(s) only: the VPS
#      can create backups but cannot decrypt them
#   4. SHA-256 checksum, upload to off-site storage with rclone
#   5. verify the uploaded copy (size, and by default a full re-download hash)
#   6. retention: newest DAILY_KEEP daily backups, newest MONTHLY_KEEP monthly
#      (a copy made on the first day of each month, UTC)
#   7. remove the local working files: no backup is kept on the VPS
#
# Configuration comes from a root-only file (default
# /etc/womenshapingfutures/backup.env, see backup.env.example). No secret is
# ever written to this script, the logs or the command line.
# Exit status is non-zero on any failure (systemd marks the run failed).
set -Eeuo pipefail
umask 077

ENV_FILE="${WSF_BACKUP_ENV:-/etc/womenshapingfutures/backup.env}"
log() { printf '%s wsf-backup: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { log "ERROR: $*"; exit 1; }

[[ -f "$ENV_FILE" ]] || die "configuration file $ENV_FILE not found"
perms="$(stat -c '%a' "$ENV_FILE")"
[[ "$perms" == "600" || "$perms" == "400" ]] || die "$ENV_FILE must be readable by its owner only (chmod 600), found $perms"
# Export everything it sets: pg_dump/psql/rclone read PG* and RCLONE_* from the environment.
set -a
# shellcheck source=/dev/null
source "$ENV_FILE"
set +a

: "${PGDATABASE:?PGDATABASE is required}"
: "${MEDIA_ROOT:?MEDIA_ROOT is required}"
: "${PROTECTED_MEDIA_ROOT:?PROTECTED_MEDIA_ROOT is required}"
: "${APP_ENV_FILE:?APP_ENV_FILE (the backend .env) is required}"
: "${AGE_RECIPIENTS_FILE:?AGE_RECIPIENTS_FILE (public key file) is required}"
: "${RCLONE_REMOTE:?RCLONE_REMOTE (e.g. wsfoffsite:wsf-backups) is required}"
DAILY_KEEP="${DAILY_KEEP:-30}"
MONTHLY_KEEP="${MONTHLY_KEEP:-12}"
VERIFY_DOWNLOAD="${VERIFY_DOWNLOAD:-1}"
WORK_PARENT="${BACKUP_WORK_DIR:-/var/tmp}"
NOW_EPOCH="${WSF_BACKUP_NOW:-$(date -u +%s)}"   # override for tests only

for tool in pg_dump pg_restore psql tar age rclone sha256sum; do
  command -v "$tool" >/dev/null || die "$tool is not installed"
done
[[ -s "$AGE_RECIPIENTS_FILE" ]] || die "AGE_RECIPIENTS_FILE is empty or missing"
grep -q 'AGE-SECRET-KEY' "$AGE_RECIPIENTS_FILE" && die "AGE_RECIPIENTS_FILE contains a PRIVATE key; it must hold public keys only"

STAMP="$(date -u -d "@$NOW_EPOCH" +%Y%m%dT%H%M%SZ)"
DAY="$(date -u -d "@$NOW_EPOCH" +%d)"
MONTH="$(date -u -d "@$NOW_EPOCH" +%Y-%m)"
NAME="wsf-${STAMP}.tar.age"

WORK="$(mktemp -d "$WORK_PARENT/wsf-backup.XXXXXX")"
cleanup() { rm -rf "$WORK"; }
trap cleanup EXIT

log "starting backup $NAME"

# 1. Database
pg_dump --format=custom --no-owner --no-privileges --file="$WORK/db.dump"
pg_restore --list "$WORK/db.dump" >/dev/null || die "pg_dump output is not a readable archive"
REVISION="$(psql -X -A -t -c 'SELECT version_num FROM alembic_version' 2>/dev/null | head -1 || true)"
log "database dumped ($(stat -c %s "$WORK/db.dump") bytes, alembic revision ${REVISION:-unknown})"

# 2. Files (paths stored relative to /)
for path in "$MEDIA_ROOT" "$PROTECTED_MEDIA_ROOT" "$APP_ENV_FILE"; do
  [[ -e "$path" ]] || die "$path does not exist"
done
tar --create --gzip --file="$WORK/files.tar.gz" --directory=/ \
  "${MEDIA_ROOT#/}" "${PROTECTED_MEDIA_ROOT#/}" "${APP_ENV_FILE#/}"
log "files archived ($(stat -c %s "$WORK/files.tar.gz") bytes)"

cat > "$WORK/MANIFEST" <<EOF
backup=$NAME
created_utc=$STAMP
alembic_revision=${REVISION:-unknown}
database=$PGDATABASE
media_root=$MEDIA_ROOT
protected_media_root=$PROTECTED_MEDIA_ROOT
app_env_file=$APP_ENV_FILE
EOF
(cd "$WORK" && sha256sum db.dump files.tar.gz > CONTENTS.sha256)

# 3. Bundle + encrypt (public key only)
tar --create --file="$WORK/bundle.tar" --directory="$WORK" MANIFEST CONTENTS.sha256 db.dump files.tar.gz
age --encrypt --recipients-file "$AGE_RECIPIENTS_FILE" --output "$WORK/$NAME" "$WORK/bundle.tar"
rm -f "$WORK/bundle.tar" "$WORK/db.dump" "$WORK/files.tar.gz"

# 4. Checksum + upload
(cd "$WORK" && sha256sum "$NAME" > "$NAME.sha256")
SIZE="$(stat -c %s "$WORK/$NAME")"
rclone copyto --immutable "$WORK/$NAME" "$RCLONE_REMOTE/daily/$NAME"
rclone copyto --immutable "$WORK/$NAME.sha256" "$RCLONE_REMOTE/daily/$NAME.sha256"

# 5. Verify the off-site copy
REMOTE_SIZE="$(rclone size --json "$RCLONE_REMOTE/daily/$NAME" | sed -n 's/.*"bytes":\([0-9]*\).*/\1/p')"
[[ "$REMOTE_SIZE" == "$SIZE" ]] || die "uploaded size $REMOTE_SIZE differs from local $SIZE"
if [[ "$VERIFY_DOWNLOAD" == "1" ]]; then
  EXPECTED="$(cut -d' ' -f1 "$WORK/$NAME.sha256")"
  ACTUAL="$(rclone cat "$RCLONE_REMOTE/daily/$NAME" | sha256sum | cut -d' ' -f1)"
  [[ "$ACTUAL" == "$EXPECTED" ]] || die "checksum of the uploaded copy does not match"
fi
log "uploaded and verified daily/$NAME ($SIZE bytes)"

# Monthly copy (first day of the month, UTC)
if [[ "$DAY" == "01" ]]; then
  MONTHLY_NAME="wsf-${MONTH}.tar.age"
  rclone copyto "$RCLONE_REMOTE/daily/$NAME" "$RCLONE_REMOTE/monthly/$MONTHLY_NAME"
  printf '%s  %s\n' "$(cut -d' ' -f1 "$WORK/$NAME.sha256")" "$MONTHLY_NAME" > "$WORK/$MONTHLY_NAME.sha256"
  rclone copyto "$WORK/$MONTHLY_NAME.sha256" "$RCLONE_REMOTE/monthly/$MONTHLY_NAME.sha256"
  log "monthly copy monthly/$MONTHLY_NAME (from daily/$NAME)"
fi

# 6. Retention
prune() {
  local folder="$1" keep="$2"
  mapfile -t objects < <(rclone lsf --files-only "$RCLONE_REMOTE/$folder" 2>/dev/null | grep -E '\.tar\.age$' | sort)
  local excess=$(( ${#objects[@]} - keep ))
  (( excess > 0 )) || return 0
  for obj in "${objects[@]:0:excess}"; do
    rclone deletefile "$RCLONE_REMOTE/$folder/$obj"
    rclone deletefile "$RCLONE_REMOTE/$folder/$obj.sha256" 2>/dev/null || true
    log "retention: removed $folder/$obj"
  done
}
prune daily "$DAILY_KEEP"
prune monthly "$MONTHLY_KEEP"

log "backup $NAME complete (local working files removed)"
