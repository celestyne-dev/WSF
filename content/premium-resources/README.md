# Premium resources: manuscripts & print-ready PDFs

Each folder holds one Think Positive Always title:

- `manuscript.md`: the source text (Pandoc Markdown with a little HTML for write-in lines and tables)
- `generate.py`: for the workbook and journal only. It generates `manuscript.md` from structured day-by-day content, so edit this file instead of the `.md`.
- `<slug>.pdf`: the print-ready A4 PDF to upload in Admin → Premium Resources
- `cover.png`: the cover image for the product card

See `CATALOG_PLAN.md` for product copy, catalog clean-up, new titles, collections and pricing.

## Rebuilding after an edit

You need `pandoc`, `node` with `playwright`, and `pdfinfo`.

```bash
content/premium-resources/_build/build.sh                      # all titles
content/premium-resources/_build/build.sh the-power-of-starting-again   # one title
```

For the workbook and journal, run `python3 generate.py` in that folder first.

Write-in lines: `<div class="write l6"></div>` gives 6 ruled lines. Try-this boxes: `<div class="try"> … </div>`.
