#!/usr/bin/env python3
"""Idempotently apply (or check) the Module 13B protected-upload Nginx
route in /etc/nginx/sites-available/womenshapingfutures. stdlib only.

    --check   report what would happen; never touches the file.
    --apply   make the edit (root required), backing up first, then
              validates with `nginx -t` and rolls back on failure.

Never reloads Nginx, never restarts any service, never touches
application code or any other route/limit in the file.
"""
import argparse
import filecmp
import os
import re
import shutil
import subprocess
import sys
import time

CONFIG_PATH = "/etc/nginx/sites-available/womenshapingfutures"
BACKUP_DIR = "/var/backups/womenshapingfutures"

EXPECTED_LINES = [
    "client_max_body_size 55m;",
    "proxy_pass http://127.0.0.1:8020;",
    "proxy_http_version 1.1;",
    "proxy_set_header Host $host;",
    "proxy_set_header X-Real-IP $remote_addr;",
    "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "proxy_set_header X-Forwarded-Proto $scheme;",
]

# Matches the exact-match Module 13B syntax only — used to confirm a
# found block is syntactically the correct one, not just the same URI.
EXACT_OPEN_RE = re.compile(r"^\s*location\s*=\s*/api/v1/resources/uploads/protected\s*\{\s*$")
# Matches ANY location block for this URI, exact-match or prefix — used
# for conflict detection so a differently-declared block for the same
# route is never missed and silently duplicated.
ANY_OPEN_RE = re.compile(r"^\s*location\s*(?:=\s*)?/api/v1/resources/uploads/protected\s*\{\s*$")
ANCHOR_RE = re.compile(r"^\s*location\s+/api/\s*\{\s*$")


def find_block(lines):
    """Returns (open_index, close_index) of any existing location block
    for the protected-upload URI (exact-match or prefix), brace-counted
    so it doesn't assume the closing '}' sits alone on its own line.
    None if no such block exists."""
    for i, line in enumerate(lines):
        if ANY_OPEN_RE.match(line):
            depth = line.count("{") - line.count("}")
            j = i
            while depth > 0:
                j += 1
                if j >= len(lines):
                    sys.exit("ERROR: unterminated protected-upload location block.")
                depth += lines[j].count("{") - lines[j].count("}")
            return i, j
    return None


def build_block(indent):
    inner = indent + "    "
    lines = [f"{indent}location = /api/v1/resources/uploads/protected {{"]
    lines += [f"{inner}{d}" for d in EXPECTED_LINES]
    lines.append(f"{indent}}}")
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="report only, make no changes")
    group.add_argument("--apply", action="store_true", help="apply the edit (requires root)")
    args = parser.parse_args()

    if args.apply and os.geteuid() != 0:
        sys.exit("ERROR: --apply must be run as root.")

    if not os.path.isfile(CONFIG_PATH):
        sys.exit(f"ERROR: {CONFIG_PATH} not found.")

    with open(CONFIG_PATH) as f:
        lines = f.read().splitlines()

    existing = find_block(lines)
    if existing is not None:
        open_i, close_i = existing
        body = [l.strip() for l in lines[open_i + 1:close_i] if l.strip()]
        is_exact_syntax = bool(EXACT_OPEN_RE.match(lines[open_i]))
        if is_exact_syntax and body == EXPECTED_LINES:
            print("OK: protected-upload block already present and correct — no change needed.")
            print("\n".join(lines[open_i:close_i + 1]))
            return 0
        print("ABORT: an existing protected-upload block differs from the expected Module 13B block.", file=sys.stderr)
        print("---- existing ----", file=sys.stderr)
        print("\n".join(lines[open_i:close_i + 1]), file=sys.stderr)
        print("---- expected directives ----", file=sys.stderr)
        print("\n".join(EXPECTED_LINES), file=sys.stderr)
        return 1

    anchor_i = next((i for i, l in enumerate(lines) if ANCHOR_RE.match(l)), None)
    if anchor_i is None:
        sys.exit("ERROR: could not find 'location /api/ {' anchor to insert before.")

    indent = lines[anchor_i][: len(lines[anchor_i]) - len(lines[anchor_i].lstrip())]
    new_block = build_block(indent)

    if args.check:
        print("Block absent — would insert immediately before 'location /api/ {':")
        print("\n".join(new_block))
        return 0

    # --apply from here on (root already confirmed above).
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"womenshapingfutures.conf.{time.strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copy2(CONFIG_PATH, backup_path)
    if not filecmp.cmp(CONFIG_PATH, backup_path, shallow=False):
        sys.exit(f"ERROR: backup verification failed ({backup_path} does not match live config).")
    print(f"Backup created: {backup_path}")

    new_lines = lines[:anchor_i] + new_block + [""] + lines[anchor_i:]
    tmp_path = CONFIG_PATH + ".tmp13b"
    with open(tmp_path, "w") as f:
        f.write("\n".join(new_lines) + "\n")
    st = os.stat(CONFIG_PATH)
    os.chown(tmp_path, st.st_uid, st.st_gid)
    os.chmod(tmp_path, st.st_mode)
    os.replace(tmp_path, CONFIG_PATH)

    check = subprocess.run(["nginx", "-t"])
    if check.returncode == 0:
        print("nginx -t passed.")
        print("Inserted protected-upload location block:")
        print("\n".join(new_block))
        print("SUCCESS (not reloaded — reload manually: systemctl reload nginx).")
        return 0

    print("nginx -t FAILED after edit — restoring backup.", file=sys.stderr)
    shutil.copy2(backup_path, CONFIG_PATH)
    restore_check = subprocess.run(["nginx", "-t"])
    if restore_check.returncode == 0:
        print("Backup restored and verified valid. No changes are live.", file=sys.stderr)
    else:
        print("WARNING: restored backup also fails nginx -t — predates this script's edit.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
