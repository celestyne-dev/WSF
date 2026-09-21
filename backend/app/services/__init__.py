# Business logic that shouldn't live in route handlers, one module per
# concern:
#
#   geography.py  Country/region lookups backed by the Country table
#                 (app/models/geography.py) — see app/utils/filtering.py
#                 for the shared ?country=/?region= query helpers every
#                 listing endpoint uses.
#   slugs.py      Slug generation + uniqueness against a model, skipping
#                 reserved routes (app/utils/slugs.py). Redirect creation
#                 on slug change is added in Phase 2 alongside Article.
#   rbac.py       Seeds the standard roles/permissions (flask seed-roles).
#   audit.py      Appends to the audit_logs trail (app/models/audit.py).
#   media.py      The Hostinger VPS media pipeline: validate MIME type,
#                 extension, and size; sanitize/replace the filename with a
#                 UUID-based one; run uploads through Pillow to correct
#                 orientation and generate the thumbnail/card/medium/large/
#                 hero WebP variants under MEDIA_ROOT (see config.py);
#                 persist a Media row; and check inbound references before
#                 allowing a delete. Flask only ever handles upload ->
#                 validate -> process -> metadata -> permissions; Nginx
#                 serves the resulting files directly from disk.
#   payments.py   Payment-provider abstraction (added when Products/Orders
#                 land in Phase 7).
#   newsletter.py Sending WSF Weekly issues and managing subscriptions
#                 (added in Phase 6).
