"""Focused unit tests for the pure transformation logic in
../apply_module12b_nginx_spa_shell.py — find_blocks()/classify()/
indent_for()/build_replacement_block()/build_new_lines(). All of these
operate purely on in-memory line lists; none of them touch the
filesystem, require root, or shell out to `nginx -t`, so these tests run
anywhere stdlib + pytest is available.
"""
import importlib.util
import os

import pytest

_MODULE_PATH = os.path.join(os.path.dirname(__file__), "..", "apply_module12b_nginx_spa_shell.py")
_spec = importlib.util.spec_from_file_location("apply_module12b_nginx_spa_shell", _MODULE_PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


OLD_SERVER_BLOCK = """\
server {
    listen 443 ssl http2;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~ /\\.(?!well-known) {
        deny all;
    }
}
"""

ALREADY_APPLIED_SERVER_BLOCK = """\
server {
    listen 443 ssl http2;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
    }

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

    location ~ /\\.(?!well-known) {
        deny all;
    }
}
"""


def _lines(text):
    return text.splitlines()


class TestFindBlocks:
    def test_finds_single_block_with_correct_bounds(self):
        lines = _lines(OLD_SERVER_BLOCK)
        blocks = mod.find_blocks(lines, mod.ROOT_OPEN_RE)
        assert len(blocks) == 1
        open_i, close_i = blocks[0]
        assert lines[open_i].strip() == "location / {"
        assert lines[close_i].strip() == "}"

    def test_brace_counting_skips_nested_braces(self):
        # A location block whose body itself contains a nested {...}
        # (e.g. an `if` block) must not end the outer block early.
        lines = _lines(
            """\
location /weird/ {
    if ($arg_x = "1") {
        return 403;
    }
}
"""
        )
        open_re = mod.re.compile(r"^\s*location\s+/weird/\s*\{\s*$")
        blocks = mod.find_blocks(lines, open_re)
        assert len(blocks) == 1
        open_i, close_i = blocks[0]
        assert close_i == len(lines) - 1  # the outer block's own closing '}'

    def test_no_match_returns_empty_list(self):
        lines = _lines(ALREADY_APPLIED_SERVER_BLOCK)
        # ROOT_OPEN_RE must never match a prefixed path like /api/.
        matches = [l for l in lines if mod.ROOT_OPEN_RE.match(l) and "api" in l]
        assert matches == []


class TestClassify:
    def test_not_applied_state(self):
        lines = _lines(OLD_SERVER_BLOCK)
        state, root_block, spa_block = mod.classify(lines)
        assert state == "not_applied"
        assert spa_block is None
        open_i, close_i = root_block
        assert mod.block_body(lines, open_i, close_i) == mod.OLD_ROOT_BODY

    def test_already_applied_state(self):
        lines = _lines(ALREADY_APPLIED_SERVER_BLOCK)
        state, root_block, spa_block = mod.classify(lines)
        assert state == "already_applied"
        assert spa_block is not None

    def test_missing_root_block_raises(self):
        lines = _lines(
            """\
server {
    location /api/ { proxy_pass http://127.0.0.1:8000; }
}
"""
        )
        with pytest.raises(mod.UnexpectedState, match="missing"):
            mod.classify(lines)

    def test_duplicate_root_block_raises(self):
        lines = _lines(OLD_SERVER_BLOCK + "\n" + OLD_SERVER_BLOCK)
        with pytest.raises(mod.UnexpectedState, match="appears 2 times"):
            mod.classify(lines)

    def test_duplicate_spa_shell_block_raises(self):
        lines = _lines(ALREADY_APPLIED_SERVER_BLOCK)
        extra_spa_block = _lines(
            """\
    location @spa_shell {
        proxy_pass http://127.0.0.1:8020;
    }
"""
        )
        # Insert a second @spa_shell block right before the final '}'.
        lines = lines[:-1] + extra_spa_block + [lines[-1]]
        with pytest.raises(mod.UnexpectedState, match="@spa_shell"):
            mod.classify(lines)

    def test_spa_shell_wrong_port_raises(self):
        wrong = ALREADY_APPLIED_SERVER_BLOCK.replace("127.0.0.1:8020", "127.0.0.1:9999")
        with pytest.raises(mod.UnexpectedState, match="differ from the expected"):
            mod.classify(_lines(wrong))

    def test_spa_shell_missing_header_raises(self):
        wrong = ALREADY_APPLIED_SERVER_BLOCK.replace(
            "        proxy_set_header X-Forwarded-Proto $scheme;\n", ""
        )
        with pytest.raises(mod.UnexpectedState, match="differ from the expected"):
            mod.classify(_lines(wrong))

    def test_new_root_body_without_spa_block_raises(self):
        # location / already points at @spa_shell, but no @spa_shell
        # block exists at all — an interrupted/partial apply.
        text = ALREADY_APPLIED_SERVER_BLOCK
        lines = _lines(text)
        spa_open, spa_close = mod.find_blocks(lines, mod.SPA_SHELL_OPEN_RE)[0]
        lines = lines[:spa_open] + lines[spa_close + 1 :]
        with pytest.raises(mod.UnexpectedState, match="interrupted"):
            mod.classify(lines)

    def test_old_root_body_with_existing_spa_block_raises(self):
        # location / still uses the old index.html fallback, but a
        # @spa_shell block already exists unexpectedly (someone added it
        # by hand without updating location / to reference it yet).
        lines = _lines(OLD_SERVER_BLOCK)
        spa_lines = _lines(
            """\
    location @spa_shell {
        proxy_pass http://127.0.0.1:8020;
    }
"""
        )
        lines = lines[:-1] + spa_lines + [lines[-1]]
        with pytest.raises(mod.UnexpectedState, match="unexpectedly"):
            mod.classify(lines)

    def test_unrecognized_root_body_raises(self):
        lines = _lines(OLD_SERVER_BLOCK.replace("try_files $uri $uri/ /index.html;", "return 404;"))
        with pytest.raises(mod.UnexpectedState, match="does not match"):
            mod.classify(lines)


class TestIndentAndBuild:
    def test_indent_for_detects_outer_and_inner_indent(self):
        lines = _lines(OLD_SERVER_BLOCK)
        root_open, root_close = mod.find_blocks(lines, mod.ROOT_OPEN_RE)[0]
        outer, inner = mod.indent_for(lines, root_open, root_close)
        assert outer == "    "
        assert inner == "        "

    def test_build_replacement_block_shape(self):
        block = mod.build_replacement_block("    ", "        ")
        assert block[0] == "    location / {"
        assert block[1] == "        try_files $uri $uri/ @spa_shell;"
        assert block[2] == "    }"
        assert block[3] == ""
        assert block[4] == "    location @spa_shell {"
        assert block[-1] == "    }"
        # Every expected directive, correctly indented, appears exactly once.
        for directive in mod.SPA_SHELL_LINES:
            assert f"        {directive}" in block
        assert len(block) == 5 + len(mod.SPA_SHELL_LINES) + 1

    def test_build_new_lines_preserves_everything_else_byte_for_byte(self):
        lines = _lines(OLD_SERVER_BLOCK)
        root_open, root_close = mod.find_blocks(lines, mod.ROOT_OPEN_RE)[0]
        new_lines = mod.build_new_lines(lines, root_open, root_close)

        # Everything before the old block is untouched.
        assert new_lines[:root_open] == lines[:root_open]
        # Everything after the old block's close is untouched, just
        # shifted to make room for the inserted @spa_shell block.
        outer, inner = mod.indent_for(lines, root_open, root_close)
        replacement_len = len(mod.build_replacement_block(outer, inner))
        assert new_lines[root_open + replacement_len :] == lines[root_close + 1 :]

        new_text = "\n".join(new_lines)
        assert "location / {\n        try_files $uri $uri/ @spa_shell;\n    }" in new_text
        assert "location @spa_shell {" in new_text
        assert "/index.html" not in new_text
        # Unrelated blocks survive untouched.
        assert "location /api/ {" in new_text
        assert "proxy_pass http://127.0.0.1:8000;" in new_text
        assert 'location ~ /\\.(?!well-known) {' in new_text

    def test_build_new_lines_is_idempotent_input_for_reclassify(self):
        # Feeding the transformed output back through classify() must
        # report "already_applied", proving the generated block is
        # exactly what classify() itself expects to see.
        lines = _lines(OLD_SERVER_BLOCK)
        root_open, root_close = mod.find_blocks(lines, mod.ROOT_OPEN_RE)[0]
        new_lines = mod.build_new_lines(lines, root_open, root_close)
        state, _root_block, spa_block = mod.classify(new_lines)
        assert state == "already_applied"
        assert spa_block is not None


def _rewrite(raw_text):
    """Runs raw_text through the exact same open-file-free pipeline
    main() uses for the actual on-disk write: classify() (via
    find_blocks/ROOT_OPEN_RE) + indent_for() + build_replacement_block()
    + replace_root_block_bytes()."""
    lines = raw_text.splitlines()
    root_open, root_close = mod.find_blocks(lines, mod.ROOT_OPEN_RE)[0]
    outer_indent, inner_indent = mod.indent_for(lines, root_open, root_close)
    replacement = mod.build_replacement_block(outer_indent, inner_indent)
    return mod.replace_root_block_bytes(raw_text, root_open, root_close, replacement)


class TestByteExactRewrite:
    """replace_root_block_bytes() is what main() actually writes to disk
    (see the Module 12B hardening task: the previous implementation
    rebuilt the whole file via "\\n".join(lines) + "\\n", silently
    normalizing CRLF to LF and always forcing a final newline — neither
    of which byte-exactly preserves the live file outside the one block
    this script is allowed to touch).
    """

    def test_crlf_input_preserves_crlf_outside_and_in_replacement(self):
        crlf_text = OLD_SERVER_BLOCK.replace("\n", "\r\n")
        new_text = _rewrite(crlf_text)

        # Every line ending in the output is "\r\n" — never a bare "\n".
        assert mod.re.search(r"(?<!\r)\n", new_text) is None
        assert "\r\n" in new_text

        assert "server {\r\n" in new_text
        assert "    location /api/ {\r\n" in new_text
        assert "    location / {\r\n        try_files $uri $uri/ @spa_shell;\r\n    }\r\n" in new_text
        assert "    location @spa_shell {\r\n        proxy_pass http://127.0.0.1:8020;\r\n" in new_text
        assert "    location ~ /\\.(?!well-known) {\r\n        deny all;\r\n    }\r\n}\r\n" in new_text
        assert "/index.html" not in new_text

    def test_lf_input_preserves_lf(self):
        new_text = _rewrite(OLD_SERVER_BLOCK)

        # No CRLF anywhere in the output — the input was pure LF.
        assert "\r" not in new_text

        assert "server {\n" in new_text
        assert "    location / {\n        try_files $uri $uri/ @spa_shell;\n    }\n" in new_text
        assert "    location @spa_shell {\n        proxy_pass http://127.0.0.1:8020;\n" in new_text
        assert "    location ~ /\\.(?!well-known) {\n        deny all;\n    }\n}\n" in new_text
        assert "/index.html" not in new_text

    def test_file_with_no_final_newline_stays_without_one(self):
        # The root block's own closing '}' is deliberately the file's
        # very last byte, with no trailing newline at all — this is the
        # one case where the replaced span's own last line (not merely
        # untouched trailing content) must carry that missing terminator
        # forward onto the NEW block's own last line.
        no_final_newline_text = "server {\n    location / {\n        try_files $uri $uri/ /index.html;\n    }"
        assert not no_final_newline_text.endswith("\n")

        new_text = _rewrite(no_final_newline_text)

        assert not new_text.endswith("\n")
        assert new_text.endswith("}")
        assert new_text.startswith("server {\n")
        assert "try_files $uri $uri/ @spa_shell;" in new_text
        assert "location @spa_shell {" in new_text
        assert "/index.html" not in new_text

    def test_unrelated_prefix_and_suffix_are_byte_for_byte_unchanged(self):
        prefix = (
            "# unrelated prefix comment — ünïcödé, trailing spaces   \n"
            "upstream backend_pool {\n"
            "    server 127.0.0.1:8000;\n"
            "}\n"
            "\n"
        )
        suffix = "\n# unrelated suffix — a\ttab, trailing ws   \n"
        full_text = prefix + OLD_SERVER_BLOCK + suffix

        new_text = _rewrite(full_text)

        assert new_text.startswith(prefix)
        assert new_text.endswith(suffix)
        # Nothing about the untouched regions changed length/content —
        # only the known, intentional substitution happened in between.
        assert new_text.count("upstream backend_pool {") == 1
        assert "/index.html" not in new_text
        assert "location @spa_shell {" in new_text

    def test_reclassify_after_byte_exact_rewrite_reports_already_applied(self):
        # The byte-exact write path must still produce output that
        # classify() itself recognizes as correctly applied — proving
        # replace_root_block_bytes()'s output is line-for-line identical
        # in content to build_replacement_block()'s own lines, not just
        # visually similar.
        new_text = _rewrite(OLD_SERVER_BLOCK)
        state, _root_block, spa_block = mod.classify(new_text.splitlines())
        assert state == "already_applied"
        assert spa_block is not None
