#!/usr/bin/env python3
"""Idempotently set PAYSTACK_ALLOWED_CURRENCIES to "KES,USD" in
/var/www/womenshapingfutures/backend/.env. stdlib only.

    --check   report the key's current value/state; never touches the file.
    --apply   make the edit (root required), backing up first.

Never prints PAYSTACK_SECRET_KEY or any other env value — only ever
reads/reports the one PAYSTACK_ALLOWED_CURRENCIES line. Never restarts
any service and never appends the key if it's missing (fails instead,
since that would mean guessing at a value production never had).
"""
import argparse
import filecmp
import os
import shutil
import sys
import time

ENV_PATH = "/var/www/womenshapingfutures/backend/.env"
BACKUP_DIR = "/var/backups/womenshapingfutures"
KEY = "PAYSTACK_ALLOWED_CURRENCIES"
TARGET_VALUE = "KES,USD"


def find_key_line(lines):
    """Index of the line assigning KEY (optionally `export `-prefixed),
    skipping comments and blank lines. None if KEY is never assigned."""
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        body = stripped[len("export "):] if stripped.startswith("export ") else stripped
        if body.startswith(f"{KEY}="):
            return i
    return None


def extract_value(line):
    _, _, rest = line.partition("=")
    value = rest.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report only, make no changes")
    group.add_argument("--apply", action="store_true", help="apply the edit (requires root)")
    args = parser.parse_args()

    if args.apply and os.geteuid() != 0:
        sys.exit("ERROR: --apply must be run as root.")

    if not os.path.isfile(ENV_PATH):
        sys.exit(f"ERROR: {ENV_PATH} not found.")

    with open(ENV_PATH) as f:
        lines = f.read().splitlines()

    key_i = find_key_line(lines)
    if key_i is None:
        sys.exit(f"ERROR: {KEY} not found in {ENV_PATH} — refusing to add it silently. Set it manually first.")

    current_value = extract_value(lines[key_i])

    if current_value == TARGET_VALUE:
        print(f'OK: {KEY} is already "{TARGET_VALUE}" — no change needed.')
        return 0

    if args.check:
        print(f'{KEY} is currently "{current_value}" — would change to "{TARGET_VALUE}".')
        return 0

    # --apply from here on (root already confirmed above).
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"env.{time.strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copy2(ENV_PATH, backup_path)
    if not filecmp.cmp(ENV_PATH, backup_path, shallow=False):
        sys.exit(f"ERROR: backup verification failed ({backup_path} does not match the live .env).")
    print(f"Backup created: {backup_path}")

    new_lines = list(lines)
    prefix = "export " if lines[key_i].strip().startswith("export ") else ""
    new_lines[key_i] = f'{prefix}{KEY}="{TARGET_VALUE}"'

    tmp_path = ENV_PATH + ".tmp_paystack"
    with open(tmp_path, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    st = os.stat(ENV_PATH)
    os.chown(tmp_path, st.st_uid, st.st_gid)
    os.chmod(tmp_path, st.st_mode)
    os.replace(tmp_path, ENV_PATH)

    print(f'{KEY} updated to "{TARGET_VALUE}".')
    return 0


if __name__ == "__main__":
    sys.exit(main())
