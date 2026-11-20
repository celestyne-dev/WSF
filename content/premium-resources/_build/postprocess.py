"""Expands <div class="write lN"></div> placeholders into N real ruled lines (prints crisply)."""
import re, sys
p = sys.argv[1]
html = open(p, encoding="utf-8").read()
def lines(m):
    n = int(m.group(1))
    return '<div class="write">' + '<div class="ln"></div>' * n + '</div>'
html = re.sub(r'<div class="write l(\d+)">\s*</div>', lines, html)
open(p, "w", encoding="utf-8").write(html)
