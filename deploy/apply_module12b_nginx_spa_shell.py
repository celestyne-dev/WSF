#!/usr/bin/env python3
"""Idempotently apply (or check) the Module 12B SPA-shell Nginx fallback
in /etc/nginx/sites-available/womenshapingfutures. stdlib only.

    --check   report what would happen; never touches the file.
    --apply   make the edit (root required), backing up first, then
              validates with `nginx -t` and rolls back on failure.

Changes ONLY the one SPA fallback block, from:

    location / {
        try_files $uri $uri/ /index.html;
    }

to:

    location / {
        try_files $uri $uri/ @spa_shell;
    }

    location @spa_shell {
        proxy_pass http://127.0.0.1:8020;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

Never reloads Nginx, never restarts any service, never touches
application code or any other route/block in the file.
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

OLD_ROOT_BODY = ["try_files $uri $uri/ /index.html;"]
NEW_ROOT_BODY = ["try_files $uri $uri/ @spa_shell;"]
SPA_SHELL_LINES = [
    "proxy_pass http://127.0.0.1:8020;",
    "proxy_http_version 1.1;",
    "proxy_set_header Host $host;",
    "proxy_set_header X-Real-IP $remote_addr;",
    "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "proxy_set_header X-Forwarded-Proto $scheme;",
]

# Matches ONLY the root-path location block ("location / {") — the "/"
# token must be followed by whitespace/brace, not by further path
# characters, so "location /api/ {" or "location /media/ {" never match.
ROOT_OPEN_RE = re.compile(r"^\s*location\s+/\s*\{\s*$")
# Matches the named @spa_shell location this script owns.
SPA_SHELL_OPEN_RE = re.compile(r"^\s*location\s+@spa_shell\s*\{\s*$")


class UnexpectedState(Exception):
    """Raised whenever the live file isn't in a state this script
    recognizes as either 'not yet applied' or 'already applied
    correctly' — the caller must report and abort, never guess or
    auto-repair past this point."""


def find_blocks(lines, open_re):
    """Every top-level block whose opening line matches `open_re`, as a
    list of (open_index, close_index), brace-counted so a nested '{'/'}'
    inside the block doesn't end it early. Used both to locate a block
    and to detect an unexpected duplicate of one."""
    blocks = []
    for i, line in enumerate(lines):
        if open_re.match(line):
            depth = line.count("{") - line.count("}")
            j = i
            while depth > 0:
                j += 1
                if j >= len(lines):
                    raise UnexpectedState(f"unterminated location block starting at line {i + 1}.")
                depth += lines[j].count("{") - lines[j].count("}")
            blocks.append((i, j))
    return blocks


def block_body(lines, open_i, close_i):
    return [l.strip() for l in lines[open_i + 1 : close_i] if l.strip()]


def classify(lines):
    """Inspects the full config file and returns one of:
        ("not_applied", (root_open, root_close), None)
        ("already_applied", (root_open, root_close), (spa_open, spa_close))
    Raises UnexpectedState for every other state (missing/duplicate root
    block, a pre-existing or malformed @spa_shell block, or a root block
    whose body matches neither the expected old nor new form).
    """
    root_blocks = find_blocks(lines, ROOT_OPEN_RE)
    if len(root_blocks) == 0:
        raise UnexpectedState("no 'location / { ... }' block found — the expected old SPA fallback block is missing.")
    if len(root_blocks) > 1:
        raise UnexpectedState(f"'location / {{ ... }}' appears {len(root_blocks)} times — expected exactly once.")
    root_open, root_close = root_blocks[0]
    root_body = block_body(lines, root_open, root_close)

    spa_blocks = find_blocks(lines, SPA_SHELL_OPEN_RE)
    if len(spa_blocks) > 1:
        raise UnexpectedState(f"'location @spa_shell {{ ... }}' appears {len(spa_blocks)} times — expected at most one.")

    if root_body == OLD_ROOT_BODY and not spa_blocks:
        return "not_applied", (root_open, root_close), None

    if root_body == NEW_ROOT_BODY and len(spa_blocks) == 1:
        spa_open, spa_close = spa_blocks[0]
        spa_body = block_body(lines, spa_open, spa_close)
        if spa_body == SPA_SHELL_LINES:
            return "already_applied", (root_open, root_close), (spa_open, spa_close)
        raise UnexpectedState(
            "'location @spa_shell { ... }' exists but its directives differ from the expected Module 12B block.\n"
            "---- existing ----\n"
            + "\n".join(lines[spa_open : spa_close + 1])
            + "\n---- expected directives ----\n"
            + "\n".join(SPA_SHELL_LINES)
        )

    if root_body == NEW_ROOT_BODY and not spa_blocks:
        raise UnexpectedState(
            "'location / { ... }' already references @spa_shell, but no 'location @spa_shell { ... }' block "
            "exists — a previous run may have been interrupted partway through. Refusing to guess; restore "
            "from a backup under " + BACKUP_DIR + " and retry."
        )

    if root_body == OLD_ROOT_BODY and spa_blocks:
        spa_open, spa_close = spa_blocks[0]
        raise UnexpectedState(
            "'location / { ... }' still uses the old index.html fallback, but a 'location @spa_shell { ... }' "
            "block already exists unexpectedly.\n---- existing @spa_shell ----\n"
            + "\n".join(lines[spa_open : spa_close + 1])
        )

    raise UnexpectedState(
        "'location / { ... }' body does not match the expected old or new form.\n"
        "---- existing ----\n"
        + "\n".join(lines[root_open : root_close + 1])
        + "\n---- expected old ----\n"
        + "\n".join(OLD_ROOT_BODY)
        + "\n---- expected new ----\n"
        + "\n".join(NEW_ROOT_BODY)
    )


def indent_for(lines, root_open, root_close):
    """(outer_indent, inner_indent) taken from the existing file so the
    inserted block matches whatever indent width this particular file
    already uses, rather than hard-coding one."""
    outer_indent = lines[root_open][: len(lines[root_open]) - len(lines[root_open].lstrip())]
    body_lines = [l for l in lines[root_open + 1 : root_close] if l.strip()]
    inner_indent = (
        body_lines[0][: len(body_lines[0]) - len(body_lines[0].lstrip())] if body_lines else outer_indent + "    "
    )
    return outer_indent, inner_indent


def build_replacement_block(outer_indent, inner_indent):
    """The lines that replace the single old 'location / { ... }' block:
    the same block (now pointing at @spa_shell) plus the new named
    'location @spa_shell { ... }' block, separated by one blank line."""
    return (
        [
            f"{outer_indent}location / {{",
            f"{inner_indent}try_files $uri $uri/ @spa_shell;",
            f"{outer_indent}}}",
            "",
            f"{outer_indent}location @spa_shell {{",
        ]
        + [f"{inner_indent}{directive}" for directive in SPA_SHELL_LINES]
        + [f"{outer_indent}}}"]
    )


def build_new_lines(lines, root_open, root_close):
    """The full new file content (as a list of lines), with the
    'location / { ... }' block replaced in place and every other line —
    before it and after it — carried through byte-for-byte."""
    outer_indent, inner_indent = indent_for(lines, root_open, root_close)
    replacement = build_replacement_block(outer_indent, inner_indent)
    return lines[:root_open] + replacement + lines[root_close + 1 :]


def _detect_newline_style(raw_text):
    """"\\r\\n" if that sequence appears anywhere in the file, else
    "\\n" — this file is expected to use one consistent line-ending
    style throughout, matching ordinary editor/Git behavior."""
    return "\r\n" if "\r\n" in raw_text else "\n"


def _line_terminator(line_with_end):
    """The exact terminator substring `line_with_end` (one element of
    str.splitlines(keepends=True)) ends with — "\\r\\n", "\\n", "\\r",
    or "" when the line is the file's last and carries no final
    newline at all."""
    if line_with_end.endswith("\r\n"):
        return "\r\n"
    if line_with_end.endswith("\n") or line_with_end.endswith("\r"):
        return line_with_end[-1]
    return ""


def replace_root_block_bytes(raw_text, root_open, root_close, replacement_lines):
    """Returns the new file content as a single string, built directly
    from `raw_text` rather than from a plain join of logical lines, so
    every byte outside the [root_open, root_close] line span — including
    the file's own newline style (LF vs CRLF) and whether it ends with a
    final newline at all — survives completely untouched. Only the
    `root_open`..`root_close` span (inclusive) is replaced, by
    `replacement_lines` (a plain list of lines with no terminators, as
    returned by build_replacement_block()).
    """
    lines_with_ends = raw_text.splitlines(keepends=True)
    newline = _detect_newline_style(raw_text)
    # The replaced span's own last line dictates what terminator the new
    # block's own last line gets: "\r\n"/"\n" when more content follows
    # it (as it must, for that original line to have had a terminator at
    # all), or "" when this span was the file's final line and the file
    # itself has no trailing newline — preserving that absence exactly.
    last_terminator = _line_terminator(lines_with_ends[root_close])

    before_text = "".join(lines_with_ends[:root_open])
    after_text = "".join(lines_with_ends[root_close + 1 :])
    middle_text = newline.join(replacement_lines) + last_terminator
    return before_text + middle_text + after_text


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

    # newline="" disables universal-newline translation on read (which
    # would otherwise silently rewrite a CRLF file's line endings to LF
    # the moment it's read) — raw_text is the file's exact text, byte
    # for byte. `lines` (no terminators) is still fine to derive from it
    # for the existing line-index-based classify()/indent_for() logic:
    # str.splitlines() treats "\r\n"/"\n"/"\r" as equivalent boundaries
    # regardless of how the string was read, so detection behavior here
    # is unchanged either way — only the final write (below) depends on
    # raw_text having been read untranslated.
    with open(CONFIG_PATH, "r", newline="") as f:
        raw_text = f.read()
    lines = raw_text.splitlines()

    try:
        state, root_block, spa_block = classify(lines)
    except UnexpectedState as exc:
        print(f"ABORT: {exc}", file=sys.stderr)
        return 1

    if state == "already_applied":
        _root_open, _root_close = root_block
        spa_open, spa_close = spa_block
        print("OK: Module 12B @spa_shell block already present and correct — no change needed.")
        print("\n".join(lines[root_block[0] : spa_close + 1]))
        return 0

    # state == "not_applied" from here on.
    root_open, root_close = root_block
    outer_indent, inner_indent = indent_for(lines, root_open, root_close)
    replacement = build_replacement_block(outer_indent, inner_indent)

    if args.check:
        print("Not yet applied — current block:")
        print("\n".join(lines[root_open : root_close + 1]))
        print("Would replace with:")
        print("\n".join(replacement))
        return 0

    # --apply from here on (root already confirmed above).
    os.makedirs(BACKUP_DIR, exist_ok=True)
    backup_path = os.path.join(BACKUP_DIR, f"womenshapingfutures.conf.{time.strftime('%Y%m%d%H%M%S')}.bak")
    shutil.copy2(CONFIG_PATH, backup_path)
    if not filecmp.cmp(CONFIG_PATH, backup_path, shallow=False):
        sys.exit(f"ERROR: backup verification failed ({backup_path} does not match live config).")
    print(f"Backup created: {backup_path}")

    new_text = replace_root_block_bytes(raw_text, root_open, root_close, replacement)
    tmp_path = CONFIG_PATH + ".tmp12b"
    # newline="" on write too, so a CRLF sequence already embedded in
    # new_text (from replace_root_block_bytes's own newline-style
    # detection) is written exactly as-is, never re-translated.
    with open(tmp_path, "w", newline="") as f:
        f.write(new_text)
    st = os.stat(CONFIG_PATH)
    os.chown(tmp_path, st.st_uid, st.st_gid)
    os.chmod(tmp_path, st.st_mode)
    os.replace(tmp_path, CONFIG_PATH)

    check = subprocess.run(["nginx", "-t"])
    if check.returncode == 0:
        print("nginx -t passed.")
        print("Applied Module 12B @spa_shell block:")
        print("\n".join(replacement))
        print(f"Backup: {backup_path}")
        print("APPLIED (not reloaded — reload manually: systemctl reload nginx).")
        return 0

    print("nginx -t FAILED after edit — restoring backup.", file=sys.stderr)
    shutil.copy2(backup_path, CONFIG_PATH)
    restore_check = subprocess.run(["nginx", "-t"])
    if restore_check.returncode == 0:
        print(f"RESTORED: backup restored and verified valid ({backup_path}). No changes are live.", file=sys.stderr)
    else:
        print("WARNING: restored backup also fails nginx -t — predates this script's edit.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
