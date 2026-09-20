# Business logic that shouldn't live in route handlers, one module per
# concern:
#
#   slugs.py     Slug generation, RESERVED_SLUGS/uniqueness validation
#                (mirrors frontend/src/mock/index.js), Redirect creation on
#                slug change (301, no chains).
#   media.py     The Hostinger VPS media pipeline: validate MIME type,
#                extension, and size; sanitize/replace the filename with a
#                UUID-based one; run uploads through Pillow to strip
#                metadata, correct orientation, and generate the
#                thumbnail/card/medium/large/hero WebP variants under
#                MEDIA_ROOT (see config.py); persist a Media row; and check
#                inbound references (articles, people, events, resources,
#                jobs, opportunities, products, sponsors, site settings)
#                before allowing a delete. Flask only ever handles
#                upload -> validate -> process -> metadata -> permissions;
#                Nginx serves the resulting files directly from disk.
#   payments.py  Payment-provider abstraction (M-Pesa Daraja/STK Push
#                first, Stripe/PayPal pluggable later).
#   newsletter.py  Sending WSF Weekly issues and managing subscriptions.
