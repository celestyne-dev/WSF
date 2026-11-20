#!/usr/bin/env bash
# Builds every manuscript.md under content/premium-resources/<slug>/ into a print-ready A4 PDF.
# Usage: ./build.sh            (all)
#        ./build.sh <slug>     (one)
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(dirname "$HERE")"
slugs=("$@"); [ ${#slugs[@]} -eq 0 ] && slugs=($(cd "$ROOT" && ls -d */ | grep -v '^_' | tr -d /))
for s in "${slugs[@]}"; do
  md="$ROOT/$s/manuscript.md"; [ -f "$md" ] || continue
  html="$HERE/out/$s.html"; mkdir -p "$HERE/out" "$ROOT/$s"
  pandoc "$md" -f markdown+raw_html+fenced_divs+bracketed_spans -t html5 --standalone --template "$HERE/template.html" -o "$html"
  python3 "$HERE/postprocess.py" "$html"
  node "$HERE/render.js" "$html" "$ROOT/$s/$s.pdf"
  echo "built $s/$s.pdf ($(pdfinfo "$ROOT/$s/$s.pdf" | awk '/Pages/{print $2}') pages)"
done
