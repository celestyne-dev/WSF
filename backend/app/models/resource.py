from datetime import date

from app.extensions import db

RESOURCE_TYPES = (
    "Guide",
    "Workbook",
    "Template",
    "Checklist",
    "Planner",
    "Toolkit",
    "Ebook",
    "Worksheet",
    "Report",
    "Download",
    "Video Resource",
    "External Resource",
)
_RESOURCE_TYPE_CHECK_SQL = "type IS NULL OR type IN (" + ", ".join(f"'{t}'" for t in RESOURCE_TYPES) + ")"

# draft: incomplete/unpublished. review: submitted, awaiting editorial
# approval. scheduled: approved, with published_date set in the future —
# becomes publicly visible automatically once that date arrives (same
# pattern as Job/Event). published: live and publicly listed. archived:
# retained for record, hidden from any public listing.
RESOURCE_STATUSES = ("draft", "review", "scheduled", "published", "archived")
_RESOURCE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_STATUSES) + ")"

# The single field that actually drives how a visitor gets the resource.
# is_premium/is_downloadable/is_external (kept below for the handful of
# existing call sites built against them) are derived from this at write
# time rather than being independently editable — one status an editor
# sets, not several that could disagree. See app/services/resource_access.py
# for the one place every one of these rules is actually enforced — this
# module only declares the allowed values.
#   direct_download: free, no gate — the button just works.
#   email_gate: free, but first name/email (+ consent) is captured before
#     the file is handed over — the lead-magnet flow.
#   member_only: any valid authenticated WSF account (User) — not a
#     Community membership, not WSF Circle. WSF accounts exist now, so
#     this is a real gate, not a placeholder.
#   circle_only: requires an active WSF Circle entitlement (see
#     app/services/circle.py's has_circle_access — the one authoritative
#     check; never re-derived here).
#   premium: has a real price and a working Paystack checkout (see
#     app/services/resource_payments.py); access requires a durable
#     one-time ResourcePurchase entitlement (see that model below and
#     app/services/resource_access.py's check_resource_access — the one
#     authoritative check). A WSF Circle membership does NOT unlock a
#     premium resource — Circle and one-off resource purchase are
#     deliberately separate commercial concepts.
#   external_link: hosted elsewhere — the CTA sends the visitor off-site.
ACCESS_TYPES = ("direct_download", "email_gate", "member_only", "circle_only", "premium", "external_link")
_ACCESS_TYPE_CHECK_SQL = "access_type IN (" + ", ".join(f"'{a}'" for a in ACCESS_TYPES) + ")"

# Access types whose `protected_file_path` (see Resource below) may
# actually be served through a short-lived download token —
# app/services/resource_downloads.py's resolve_download_token() and
# app/api/v1/resources.py's _resolve_target_url() both import this rather
# than re-listing it. external_link never has a protected file to serve
# (its whole point is an off-site URL). "premium" is included now that
# one-time Resource purchase entitlement exists (see ResourcePurchase
# below and app/services/resource_access.py's check_resource_access) —
# a token is only ever actually issued once that function has confirmed
# the viewer holds a ResourcePurchase for this Resource, exactly the same
# as circle_only's own gate via has_circle_access().
PROTECTED_FILE_ELIGIBLE_ACCESS_TYPES = ("direct_download", "email_gate", "member_only", "circle_only", "premium")

FILE_FORMATS = ("PDF", "DOCX", "XLSX", "PPTX", "ZIP", "Image", "Video", "Other")
_FILE_FORMAT_CHECK_SQL = "file_format IS NULL OR file_format IN (" + ", ".join(f"'{f}'" for f in FILE_FORMATS) + ")"

resource_topics = db.Table(
    "resource_topics",
    db.Column("resource_id", db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    db.Column("topic_id", db.Integer, db.ForeignKey("topics.id", ondelete="CASCADE"), primary_key=True),
)

resource_tags = db.Table(
    "resource_tags",
    db.Column("resource_id", db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class ResourceImage(db.Model):
    """An ordered supplementary preview image for a Resource, beyond its
    single `cover_media` — same association-object pattern as
    commerce.ProductImage.
    """

    __tablename__ = "resource_images"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False, default=0)

    media = db.relationship("Media", foreign_keys=[media_id])


class Resource(db.Model):
    """A downloadable/accessible piece of content — the free-lead-magnet
    and (eventually) paid-digital-product side of WSF's editorial output.
    `resource_id` on commerce.Product already lets a Product wrap a
    Resource for an actual Shop listing/checkout later; nothing new is
    needed here to "prepare" that relationship — it already exists.
    """

    __tablename__ = "resources"
    __table_args__ = (
        db.CheckConstraint(_RESOURCE_TYPE_CHECK_SQL, name="ck_resources_type"),
        db.CheckConstraint(_RESOURCE_STATUS_CHECK_SQL, name="ck_resources_status"),
        db.CheckConstraint(_ACCESS_TYPE_CHECK_SQL, name="ck_resources_access_type"),
        db.CheckConstraint(_FILE_FORMAT_CHECK_SQL, name="ck_resources_file_format"),
        db.CheckConstraint("price >= 0", name="ck_resources_price_nonnegative"),
        db.CheckConstraint("download_count >= 0", name="ck_resources_download_count_nonnegative"),
        db.CheckConstraint("page_count IS NULL OR page_count >= 0", name="ck_resources_page_count_nonnegative"),
        db.CheckConstraint("file_size IS NULL OR file_size >= 0", name="ck_resources_file_size_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(220), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    subtitle = db.Column(db.String(300))
    short_description = db.Column(db.Text)  # one or two sentences, for cards
    # Ordered content-block list — same shape/sanitizer/editor as every
    # other content type in this app. The editor structures "What's
    # included", "Who it's for", "Benefits", "How to use it" etc.
    # themselves rather than the app hard-coding those sections.
    description = db.Column(db.JSON, nullable=False, default=list)

    cover_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)

    type = db.Column(db.String(50))  # see RESOURCE_TYPES
    author_id = db.Column(db.Integer, db.ForeignKey("authors.id"), nullable=True)
    author_name = db.Column(db.String(200))  # denormalized fallback when no Author is linked

    price = db.Column(db.Integer, nullable=False, default=0)  # whole currency units, paired with `currency`
    # Python-side ORM default only (no server_default) — reached whenever a
    # Resource is constructed without an explicit currency (e.g. a direct
    # `Resource()` call that bypasses ResourceInputSchema's own
    # load_default). WSF currently transacts in KES; existing rows already
    # have their own stored currency and are never touched by this. Same
    # reasoning as Product.currency in app/models/commerce.py.
    currency = db.Column(db.String(3), nullable=False, default="KES")
    is_premium = db.Column(db.Boolean, nullable=False, default=False)
    is_downloadable = db.Column(db.Boolean, nullable=False, default=True)
    is_external = db.Column(db.Boolean, nullable=False, default=False)

    access_type = db.Column(db.String(20), nullable=False, default="direct_download")
    # A legacy/external target: this app's own MEDIA_URL-rooted path or an
    # http(s) URL, whichever `is_external` says to use (see
    # app/utils/urls.py's is_safe_resource_target, the one place both are
    # validated — never a raw filesystem path, never javascript:/data:/
    # file:). Kept for backward compatibility with every Resource created
    # before protected_file_path below existed/generalized — a new upload
    # should prefer that instead. Never serialized to an anonymous/public
    # caller directly (see app/schemas/resource.py's
    # build_public_resource_payload) — only POST /resources/{slug}/access,
    # after the resource's access_type rule succeeds, ever hands this back.
    file_url = db.Column(db.String(500))
    external_url = db.Column(db.String(500))
    # A WSF-hosted private resource file stored outside the public media
    # tree (see app/services/resource_downloads.py) — a filename/relative
    # path resolved against config.PROTECTED_MEDIA_ROOT, a directory
    # outside both the deployment checkout AND the publicly-served
    # MEDIA_ROOT tree. Usable by direct_download, email_gate, member_only,
    # circle_only, and premium (PROTECTED_FILE_ELIGIBLE_ACCESS_TYPES
    # below) — a premium resource's file is served only once
    # check_resource_access() has confirmed the viewer holds a
    # ResourcePurchase for it, exactly as circle_only requires
    # has_circle_access() first. Whenever this is set and resolves to a
    # real file, POST /resources/{slug}/access hands back a short-lived,
    # resource-bound download token (see ResourceDownloadResource)
    # instead of file_url/
    # external_url — circle_only and premium never fall back to either of
    # those, even if also present (see _resolve_target_url). Every other
    # access type keeps file_url/external_url working exactly as before
    # for a Resource that has no protected_file_path at all.
    protected_file_path = db.Column(db.String(500))
    # The original filename staff uploaded (e.g. "Career Reset Workbook.pdf"),
    # kept purely as display/download metadata — protected_file_path above
    # is always the server-generated storage identity and never derived
    # from this. NULL for a legacy row whose protected_file_path was typed
    # in by hand before the upload endpoint existed (Module 13B); such a
    # row falls back to os.path.basename(protected_file_path) wherever
    # this is used (CMS display, Content-Disposition on download) — see
    # app/services/resource_downloads.py.
    protected_original_filename = db.Column(db.String(255))
    file_format = db.Column(db.String(20))  # see FILE_FORMATS
    file_size = db.Column(db.Integer)  # bytes
    page_count = db.Column(db.Integer)

    sponsor_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=True)
    sponsored = db.Column(db.Boolean, nullable=False, default=False)

    download_count = db.Column(db.Integer, nullable=False, default=0)

    featured = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="draft")
    published_date = db.Column(db.Date)
    seo = db.Column(db.JSON)  # {title, description, ogImageMediaId, canonical, robots}

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    cover_media = db.relationship("Media", foreign_keys=[cover_media_id])
    author = db.relationship("Author", foreign_keys=[author_id])
    sponsor = db.relationship("Organization", foreign_keys=[sponsor_id])
    topics = db.relationship("Topic", secondary=resource_topics, backref="resources")
    tags = db.relationship("Tag", secondary=resource_tags, backref="resources")
    images = db.relationship(
        "ResourceImage", order_by="ResourceImage.position", cascade="all, delete-orphan", backref="resource"
    )

    def is_publicly_visible(self):
        """The ONE rule for whether an anonymous/ordinary visitor may see
        this resource at all — reused by the public list, public detail,
        and /access endpoints so a future-dated scheduled resource can
        never be reached early through any of the three. A resource whose
        `published_date` is None is never treated as "past due" — it's
        simply not eligible via the scheduled branch (status must be
        flipped to "published" directly for it to become visible).
        """
        if self.status == "published":
            return True
        return self.status == "scheduled" and self.published_date is not None and self.published_date <= date.today()


class ResourceLead(db.Model):
    """One email-gate submission — the record a "Download Free Guide ->
    enter your email" flow produces. Kept separate from the general
    AnalyticsEvent stream (trackEvent) because this genuinely is a
    business record (a lead, with consent), not an ephemeral interaction
    event; view/click tracking for Resources still goes through the
    existing analytics architecture, not this table.
    """

    __tablename__ = "resource_leads"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100))
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    # Consent to be added to the newsletter list — a download is never
    # forced to also become a subscription.
    newsletter_consent = db.Column(db.Boolean, nullable=False, default=False)
    acquisition = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    resource = db.relationship("Resource", foreign_keys=[resource_id])
    country = db.relationship("Country", foreign_keys=[country_code])


class ResourceDownloadToken(db.Model):
    """A short-lived, resource-bound bearer credential for a Resource's
    protected file (see PROTECTED_FILE_ELIGIBLE_ACCESS_TYPES above and
    app/services/resource_downloads.py). Same convention as
    PasswordResetToken (app/models/password_reset.py): only a SHA-256
    digest of the raw token is ever stored; the raw token exists only in
    POST /resources/{slug}/access's one-time JSON response and the
    resulting download URL, never in Postgres or a log line.

    Deliberately reusable (no `used_at`/single-use semantics) within its
    TTL — unlike a password reset, a download link may legitimately be
    opened more than once (retried, reopened in a new tab) before it
    expires; the short TTL alone bounds how long a leaked link stays
    useful. `user_id` records who it was issued to for audit purposes
    only — redemption (GET /resources/downloads/{token}) never re-checks
    current entitlement (Circle, account, purchase, or otherwise), only
    the token's own hash/expiry/resource binding, exactly like whichever
    access_type rule was already evaluated, moments earlier, by the same
    request that issued it. Nullable because a direct_download or
    email_gate resource's protected file may be requested by an
    anonymous visitor who was never asked to sign in at all — unlike
    member_only/circle_only/premium, which always have a real `user` to
    record (premium's purchase entitlement is itself tied to a user —
    see ResourcePurchase below — so its grant is never anonymous).
    """

    __tablename__ = "resource_download_tokens"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    resource = db.relationship("Resource", foreign_keys=[resource_id])
    user = db.relationship("User", foreign_keys=[user_id])


# Premium Resource purchase — Stage 1 of the Paystack premium-resource
# integration (see app/services/resource_payments.py). Deliberately a
# SEPARATE entitlement system from WSF Circle (app/models/circle.py's
# CircleSubscription): a Circle membership never unlocks a premium
# Resource, and buying a premium Resource never grants Circle (see
# app/services/resource_access.py's check_resource_access). Also
# deliberately NOT a Product/Order (app/models/commerce.py) — a premium
# Resource purchase is a one-off, non-shippable digital entitlement with
# its own payment-verification lifecycle, which Order was never designed
# for, mirroring exactly why CirclePayment/CircleSubscription stayed
# separate from Order/OrderItem too.
#
# "active" is the only status this MVP needs — a refund/revocation
# workflow is explicitly out of scope for Stage 1 (see the task's own
# "ADMIN / REFUNDS OUT OF SCOPE" section). Kept as a real, checked column
# (rather than omitted entirely) so a future "refunded"/"revoked" value
# is a deliberate migration later, not a schema redesign.
RESOURCE_PURCHASE_STATUSES = ("active",)
_RESOURCE_PURCHASE_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_PURCHASE_STATUSES) + ")"


class ResourcePurchase(db.Model):
    """One durable, one-time purchase entitlement: `user` owns `resource`
    permanently (no expiry, no renewal) once this row exists. This is the
    ONE source of truth app/services/resource_access.py's
    check_resource_access() consults for access_type == "premium" — never
    re-derived from CirclePayment/CircleSubscription, Product/Order, or
    any frontend flag.

    A user may hold AT MOST ONE active purchase of a given Resource — see
    the unique index below. This is a plain (not partial) unique index
    because RESOURCE_PURCHASE_STATUSES currently has exactly one value;
    should a future "refunded" status ever need to coexist with a later
    legitimate re-purchase, that would require switching this to a
    partial index scoped to status == "active", the same pattern
    app/models/circle.py's CircleSubscription already uses for its own
    "one current row per user" rule — a deliberate later migration, not
    something this MVP needs to anticipate.

    `payment_reference` records which ResourcePayment originally granted
    this purchase, purely for support/reconciliation — it is NOT the
    authority for entitlement (this row's mere existence is); a payment
    row may be deleted/archived later without this purchase ever being
    affected.
    """

    __tablename__ = "resource_purchases"
    __table_args__ = (
        db.CheckConstraint(_RESOURCE_PURCHASE_STATUS_CHECK_SQL, name="ck_resource_purchases_status"),
        db.Index("uq_resource_purchases_user_resource", "user_id", "resource_id", unique=True),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # RESTRICT (the FK default) — same reasoning as CircleSubscription.plan_id
    # in app/models/circle.py: a Resource referenced by any purchase, ever,
    # can never be hard-deleted, only archived (see Resource.status and
    # app/api/v1/resources.py's _is_referenced()). Purchase history must
    # never silently disappear because a Resource row was removed.
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False, index=True)

    payment_reference = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="active")

    purchased_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id])
    resource = db.relationship("Resource", foreign_keys=[resource_id])


# Same meaning/lifecycle as app/models/circle.py's CIRCLE_PAYMENT_STATUSES
# — see that module's docstring for the full pending -> verified ->
# consumed / failed / abandoned mapping. A ResourcePayment reaches at most
# one of consumed/failed/abandoned, never more than one, and never goes
# back to pending/verified once there.
RESOURCE_PAYMENT_STATUSES = ("pending", "verified", "consumed", "failed", "abandoned")
_RESOURCE_PAYMENT_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in RESOURCE_PAYMENT_STATUSES) + ")"

# Just Paystack for now — same reasoning as app/models/circle.py's
# CIRCLE_PAYMENT_PROVIDERS: a real, checked column rather than a free-text
# string, so a second provider (if one is ever added) is a deliberate
# migration rather than a typo.
RESOURCE_PAYMENT_PROVIDERS = ("paystack",)
_RESOURCE_PAYMENT_PROVIDER_CHECK_SQL = "provider IN (" + ", ".join(f"'{p}'" for p in RESOURCE_PAYMENT_PROVIDERS) + ")"


class ResourcePayment(db.Model):
    """One Paystack transaction attempt for one premium Resource purchase.
    Mirrors app/models/circle.py's CirclePayment property-for-property —
    see that class's own docstring for the full rationale this one
    shares: `amount_subunits`/`currency`/`customer_email` are SNAPSHOTS
    taken at checkout-initialization time from whatever the Resource
    looked like at that exact moment, never re-read from the current
    Resource row afterwards (so a later price/currency edit never affects
    an in-flight payment); `reference` is the one idempotency key the
    whole payment lifecycle is built around; no raw Paystack payload is
    ever stored, only the same small allowlisted `provider_snapshot`
    subset CirclePayment uses.

    `purchase_id` is set only once consume_verified_resource_payment()
    (app/services/resource_payments.py) has created/attached the
    resulting ResourcePurchase — null for the entire pending/verified
    window, and permanently null for a payment that ends up failed/
    abandoned.
    """

    __tablename__ = "resource_payments"
    __table_args__ = (
        db.CheckConstraint(_RESOURCE_PAYMENT_STATUS_CHECK_SQL, name="ck_resource_payments_status"),
        db.CheckConstraint(_RESOURCE_PAYMENT_PROVIDER_CHECK_SQL, name="ck_resource_payments_provider"),
        # Strictly positive, not merely non-negative — same reasoning as
        # CirclePayment's identical constraint: a ResourcePayment is a
        # real Paystack transaction attempt, never a fake zero-value row.
        db.CheckConstraint("amount_subunits > 0", name="ck_resource_payments_amount_positive"),
        # Mirrors CirclePayment's identical partial unique index: a given
        # Paystack transaction id must never back two different WSF
        # payment rows. Partial (WHERE NOT NULL) because a `pending` row
        # whose Paystack initialize call never completed has no
        # transaction id at all.
        db.Index(
            "uq_resource_payments_provider_transaction_id",
            "provider_transaction_id",
            unique=True,
            postgresql_where=db.text("provider_transaction_id IS NOT NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    # WSF-generated before the Paystack initialize call is ever made — see
    # app/services/paystack.py's generate_reference(prefix="wsfresource").
    # The one key every idempotency check in app/services/resource_payments.py
    # locks/queries on.
    reference = db.Column(db.String(100), unique=True, nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # RESTRICT (the FK default) — same reasoning as ResourcePurchase.resource_id
    # above: a Resource referenced by any payment, current or historical,
    # can never be hard-deleted, only archived.
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False, index=True)
    # Set only once consume_verified_resource_payment() has created/attached
    # the resulting ResourcePurchase — see class docstring.
    purchase_id = db.Column(db.Integer, db.ForeignKey("resource_purchases.id"), nullable=True, index=True)

    provider = db.Column(db.String(30), nullable=False, default="paystack")
    # Paystack's own transaction id — present only once Paystack has
    # actually responded. String, not Integer: Paystack documents this as
    # needing to accommodate unsigned 64-bit values.
    provider_transaction_id = db.Column(db.String(64), nullable=True)

    # --- Snapshots taken at checkout-initialization time (see class
    # docstring) — never re-derived from Resource's current row. ---
    amount_subunits = db.Column(db.Integer, nullable=False)  # resource.price * 100, integer arithmetic only, > 0
    currency = db.Column(db.String(3), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending", index=True)

    # The hosted-checkout redirect target Paystack returned at
    # initialization — a customer redirect URL, never a credential.
    authorization_url = db.Column(db.String(500), nullable=True)
    # Channel Paystack reports the payment completed through once known
    # (e.g. "card", "mobile_money") — informational only.
    provider_channel = db.Column(db.String(30), nullable=True)

    # Small, explicitly allowlisted subset of Paystack's verify/webhook
    # response — see class docstring. Never the full raw provider payload.
    provider_snapshot = db.Column(db.JSON, nullable=True)

    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Last time WSF called Paystack's verify endpoint for this reference —
    # lets app/services/resource_payments.py throttle repeated verify
    # calls without needing a separate rate-limit table.
    last_verification_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id])
    resource = db.relationship("Resource", foreign_keys=[resource_id])
    purchase = db.relationship("ResourcePurchase", foreign_keys=[purchase_id])
