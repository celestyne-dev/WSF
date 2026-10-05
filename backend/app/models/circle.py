"""WSF Circle — a provider-neutral premium membership entitlement, kept
entirely separate from the three existing account concepts (see each
model's own docstring for why):

  User     (app/models/user.py)      — authenticated WSF account.
  Member   (app/models/community.py) — free WSF Community profile.
  Person   (app/models/people.py)    — public editorial profile.

CircleSubscription.user_id ties premium entitlement directly to a User.
It never touches Member.membership_type (the pre-existing "Premium
Member" designation is an unrelated, staff-managed Community label — see
Member's own docstring/MEMBERSHIP_TYPES comment), never creates a Member
or Person, and never changes a User's role or CMS permissions. See
app/services/circle.py for the one authoritative entitlement check this
all exists to support.

No payment gateway is wired up here — same principle as
app/models/commerce.py's Order ("an administrative record of a
purchase... no payment gateway is wired up"). `provider`/
`provider_customer_id`/`provider_subscription_id`/`payment_reference` are
metadata/reference fields a future pluggable payment service can fill
in; `source` instead records how THIS app came to create the row
(external/manual/complimentary) today.

CirclePayment (below) is that pluggable payment service's first concrete
piece — Paystack-backed, one-time membership-period purchases only (see
app/services/paystack.py). It is purely additive: CirclePlan's and
CircleSubscription's own columns above are unchanged by it, and creating
a CirclePayment never grants access by itself — only a later module's
activation logic, writing through these same CircleSubscription rows and
the one has_circle_access() rule, does that.
"""
from app.extensions import db

CIRCLE_PLAN_BILLING_INTERVALS = ("monthly", "yearly")
_CIRCLE_PLAN_BILLING_INTERVAL_CHECK_SQL = "billing_interval IN (" + ", ".join(
    f"'{b}'" for b in CIRCLE_PLAN_BILLING_INTERVALS
) + ")"

# draft: being configured, never public. active: live and purchasable.
# archived: retired from public view — kept (never deleted) so historical
# CircleSubscription rows always resolve a real plan.
CIRCLE_PLAN_STATUSES = ("draft", "active", "archived")
_CIRCLE_PLAN_STATUS_CHECK_SQL = "status IN (" + ", ".join(f"'{s}'" for s in CIRCLE_PLAN_STATUSES) + ")"


class CirclePlan(db.Model):
    """A publicly purchasable WSF Circle membership tier. Deliberately NOT
    a Shop Product (see app/models/commerce.py's Product) — a Product is
    a one-time catalog item fulfilled via Order/OrderItem, while a
    CirclePlan is a recurring membership tier that CircleSubscription
    rows reference across a whole billing lifecycle. Price/currency
    follow this app's one established commerce convention (see
    Product.price/Order.total_amount): integer whole currency units,
    paired with an ISO 4217 currency code — never floating-point money.
    """

    __tablename__ = "circle_plans"
    __table_args__ = (
        db.CheckConstraint(_CIRCLE_PLAN_BILLING_INTERVAL_CHECK_SQL, name="ck_circle_plans_billing_interval"),
        db.CheckConstraint(_CIRCLE_PLAN_STATUS_CHECK_SQL, name="ck_circle_plans_status"),
        db.CheckConstraint("price >= 0", name="ck_circle_plans_price_nonnegative"),
    )

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(140), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    short_description = db.Column(db.Text)
    # Ordered content-block list — same shape/sanitizer as
    # Product.description/Job.description (ArticleBlockEditor +
    # sanitize_content_blocks), not a second content system.
    description = db.Column(db.JSON, nullable=False, default=list)

    billing_interval = db.Column(db.String(10), nullable=False, default="monthly")
    price = db.Column(db.Integer, nullable=False, default=0)  # whole currency units, paired with `currency`
    # No default: WSF is global, so every plan must state its own ISO 4217
    # currency explicitly (see CirclePlanInputSchema.currency, required=True)
    # rather than silently inheriting a US-centric assumption.
    currency = db.Column(db.String(3), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="draft")
    featured = db.Column(db.Boolean, nullable=False, default=False)
    display_order = db.Column(db.Integer, nullable=False, default=0)

    # Admin-configured external secure checkout — this app never collects
    # payment itself (see module docstring). Nullable: a plan with none
    # shows a safe "enrollment coming soon / contact WSF" state instead of
    # a broken button (see api/v1/circle.py's public payload).
    checkout_url = db.Column(db.String(500), nullable=True)
    # A generic "manage your billing" destination (e.g. a future payment
    # provider's customer portal) — only ever a configured URL, never
    # built/rendered by this app.
    manage_billing_url = db.Column(db.String(500), nullable=True)

    benefits = db.Column(db.JSON, nullable=False, default=list)  # list[str] — safe, broad, not-yet-built-safe copy
    seo = db.Column(db.JSON)  # {title, description, robots}

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    subscriptions = db.relationship("CircleSubscription", back_populates="plan")

    def is_publicly_visible(self):
        return self.status == "active"


# pending: created but not yet confirmed active (e.g. awaiting manual/
# external payment confirmation) — never grants access on its own.
# active: current, grants access (see app/services/circle.py).
# past_due: a payment lapsed but the membership hasn't been formally
# cancelled — no access by default, still "current" (not yet historical)
# so it keeps blocking a second simultaneous subscription until resolved.
# cancelled/expired/revoked: terminal/historical — never grant access,
# never casually return to active (see _CIRCLE_SUBSCRIPTION_TRANSITIONS
# in app/services/circle.py).
CIRCLE_SUBSCRIPTION_STATUSES = ("pending", "active", "past_due", "cancelled", "expired", "revoked")
_CIRCLE_SUBSCRIPTION_STATUS_CHECK_SQL = "status IN (" + ", ".join(
    f"'{s}'" for s in CIRCLE_SUBSCRIPTION_STATUSES
) + ")"

# "Current"/nonterminal — at most one such row per user at a time (see
# the partial unique index below). Historical/terminal rows may
# accumulate freely; a new membership cycle after a terminal row is
# always a NEW CircleSubscription, never a resurrected old one.
CIRCLE_SUBSCRIPTION_CURRENT_STATUSES = ("pending", "active", "past_due")
CIRCLE_SUBSCRIPTION_TERMINAL_STATUSES = ("cancelled", "expired", "revoked")

CIRCLE_SUBSCRIPTION_SOURCES = ("external", "manual", "complimentary")
_CIRCLE_SUBSCRIPTION_SOURCE_CHECK_SQL = "source IN (" + ", ".join(
    f"'{s}'" for s in CIRCLE_SUBSCRIPTION_SOURCES
) + ")"


class CircleSubscription(db.Model):
    """One WSF Circle membership lifecycle row for a User. Entirely
    separate from Order/OrderItem (see module docstring) — recording a
    subscription here never creates or touches an Order, and purchasing
    an unrelated Product never grants Circle access (see
    app/services/circle.py's has_circle_access, the one place access is
    decided). `provider`/`provider_customer_id`/`provider_subscription_id`/
    `payment_reference` are metadata/reference fields only — no raw
    payment/card details are ever stored anywhere on this row.
    """

    __tablename__ = "circle_subscriptions"
    __table_args__ = (
        db.CheckConstraint(_CIRCLE_SUBSCRIPTION_STATUS_CHECK_SQL, name="ck_circle_subscriptions_status"),
        db.CheckConstraint(_CIRCLE_SUBSCRIPTION_SOURCE_CHECK_SQL, name="ck_circle_subscriptions_source"),
        db.CheckConstraint(
            "current_period_end IS NULL OR current_period_start IS NULL OR current_period_end >= current_period_start",
            name="ck_circle_subscriptions_period_order",
        ),
        # Enforces "a User must not have multiple simultaneously-current
        # Circle subscriptions" (pending/active/past_due) at the database
        # level, not just in application code — a second current row for
        # the same user is rejected outright. Historical/terminal rows
        # (cancelled/expired/revoked) are NOT covered by this partial
        # index, so they may accumulate freely and a brand-new cycle can
        # always be created once the prior one is terminal. See
        # app/services/circle.py for the matching application-level guard
        # that turns the resulting IntegrityError into a clean 409.
        db.Index(
            "uq_circle_subscriptions_one_current_per_user",
            "user_id",
            unique=True,
            postgresql_where=db.text("status IN ('pending', 'active', 'past_due')"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # RESTRICT (the FK default): a plan referenced by any subscription —
    # current or historical — can never be deleted, only archived (see
    # CirclePlan.status), so a subscription never loses its plan.
    plan_id = db.Column(db.Integer, db.ForeignKey("circle_plans.id"), nullable=False, index=True)

    status = db.Column(db.String(20), nullable=False, default="pending")
    source = db.Column(db.String(20), nullable=False)

    # Metadata/reference fields only — never raw payment/card data, never
    # read by anything other than authorized staff (see
    # app/schemas/circle.py's owner/public payload builders, which
    # exclude every one of these).
    provider = db.Column(db.String(50), nullable=True)
    provider_customer_id = db.Column(db.String(200), nullable=True)
    provider_subscription_id = db.Column(db.String(200), nullable=True)
    payment_reference = db.Column(db.String(200), nullable=True)

    starts_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_start = db.Column(db.DateTime(timezone=True), nullable=True)
    current_period_end = db.Column(db.DateTime(timezone=True), nullable=True)

    cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id])
    plan = db.relationship("CirclePlan", back_populates="subscriptions", foreign_keys=[plan_id])


# pending: Paystack transaction initialized, not yet confirmed either way.
# verified: Paystack has confirmed a successful charge, but WSF has not
# yet created/extended the resulting CircleSubscription — kept distinct
# from "consumed" so a crash or restart between verifying and activating
# is resumable and never silently mistaken for "nothing happened yet".
# consumed: fully processed — the CircleSubscription this payment was
# for has been created/extended. A payment reaches at most one of
# consumed/failed/abandoned, never more than one, and never goes back to
# pending/verified once there (see app/services/paystack.py for the
# normalized provider status this maps from). failed/abandoned: the
# charge did not complete — mirrors Paystack's own "failed"/"abandoned"
# transaction statuses one-for-one, so every provider status this app
# normalizes always has a matching WSF status.
CIRCLE_PAYMENT_STATUSES = ("pending", "verified", "consumed", "failed", "abandoned")
_CIRCLE_PAYMENT_STATUS_CHECK_SQL = "status IN (" + ", ".join(
    f"'{s}'" for s in CIRCLE_PAYMENT_STATUSES
) + ")"

# Just Paystack for now (see Module 1's approved scope) — kept as a real,
# checked column rather than a free-text string so a second provider,
# if one is ever added, is a deliberate migration rather than a typo.
CIRCLE_PAYMENT_PROVIDERS = ("paystack",)
_CIRCLE_PAYMENT_PROVIDER_CHECK_SQL = "provider IN (" + ", ".join(
    f"'{p}'" for p in CIRCLE_PAYMENT_PROVIDERS
) + ")"


class CirclePayment(db.Model):
    """One Paystack transaction attempt for one WSF Circle membership-
    period purchase. Deliberately NOT an Order/OrderItem (see this
    module's docstring and app/models/commerce.py's own docstring) — a
    CirclePayment buys Circle access, never a Shop product, and needs an
    idempotency/verification lifecycle Order was never designed for.

    `amount_subunits`/`currency`/`billing_interval`/`customer_email` are
    SNAPSHOTS taken at checkout-initialization time, from whatever
    CirclePlan looked like at that exact moment — never re-read from the
    current CirclePlan row afterwards. This is deliberate: if an admin
    edits a plan's price/interval/currency after a payment against it was
    already initialized, that in-flight payment must still buy exactly
    what it was initialized for. Verification/activation (a later module)
    must always compare Paystack's response against these snapshots, not
    against CirclePlan's current, possibly-since-edited fields.

    `reference` is the one idempotency key this whole payment lifecycle
    is built around — generated by WSF before Paystack is ever called,
    and the one value every later step (the user's browser returning via
    callback, Paystack's webhook, a manual reconciliation lookup) keys
    off. `provider_transaction_id` is Paystack's own identifier for the
    transaction, kept as a string per Paystack's documented unsigned
    64-bit range — informational/reconciliation only, never used as the
    idempotency key itself.

    No raw Paystack payload is ever stored. `provider_snapshot` is a
    small, explicitly allowlisted subset of Paystack's verify/webhook
    response (status, gateway_response, channel, amount, currency,
    paid_at) kept for reconciliation and support — never the card/PIN/
    authorization/customer metadata Paystack's response may also contain,
    which this app has no need to retain and must never persist (enforced
    by app/services/paystack.py's normalization before any value reaches
    this column, not by this model).
    """

    __tablename__ = "circle_payments"
    __table_args__ = (
        db.CheckConstraint(_CIRCLE_PAYMENT_STATUS_CHECK_SQL, name="ck_circle_payments_status"),
        db.CheckConstraint(_CIRCLE_PAYMENT_PROVIDER_CHECK_SQL, name="ck_circle_payments_provider"),
        db.CheckConstraint(_CIRCLE_PLAN_BILLING_INTERVAL_CHECK_SQL, name="ck_circle_payments_billing_interval"),
        # Strictly positive, not merely non-negative: a CirclePayment is a
        # real Paystack transaction attempt. A future zero-value/
        # complimentary membership scenario belongs to the existing
        # manual/complimentary CircleSubscription pathway (see
        # CIRCLE_SUBSCRIPTION_SOURCES above) — it must never be
        # represented as a fake zero-value provider payment here.
        db.CheckConstraint("amount_subunits > 0", name="ck_circle_payments_amount_positive"),
        # Mirrors uq_circle_subscriptions_one_current_per_user's role: a
        # given Paystack transaction id must never back two different WSF
        # payment rows. Partial (WHERE NOT NULL) because a `pending` row
        # that hasn't heard back from Paystack yet (or whose initialize
        # call never completed) has no transaction id at all.
        db.Index(
            "uq_circle_payments_provider_transaction_id",
            "provider_transaction_id",
            unique=True,
            postgresql_where=db.text("provider_transaction_id IS NOT NULL"),
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    # WSF-generated before the Paystack initialize call is ever made —
    # alphanumeric plus "-"/"."/"=" only, per Paystack's documented
    # reference charset (see app/services/paystack.py's generator). The
    # one key every idempotency check in later modules locks/queries on.
    reference = db.Column(db.String(100), unique=True, nullable=False, index=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # RESTRICT (the FK default), same reasoning as CircleSubscription.plan_id
    # above: a plan referenced by any payment — current or historical —
    # can never be deleted, only archived.
    plan_id = db.Column(db.Integer, db.ForeignKey("circle_plans.id"), nullable=False, index=True)
    # Set only once a later module's activation logic creates/extends the
    # resulting CircleSubscription — null for the entire pending/verified
    # window, and permanently null for a payment that ends up failed/
    # abandoned.
    subscription_id = db.Column(db.Integer, db.ForeignKey("circle_subscriptions.id"), nullable=True, index=True)

    provider = db.Column(db.String(30), nullable=False, default="paystack")
    # Paystack's own transaction id — present only once Paystack has
    # actually responded (a failed/abandoned transaction still gets one).
    # String, not Integer: see class docstring.
    provider_transaction_id = db.Column(db.String(64), nullable=True)

    # --- Snapshots taken at checkout-initialization time (see class
    # docstring) — never re-derived from CirclePlan's current row. ---
    amount_subunits = db.Column(db.Integer, nullable=False)  # plan.price * 100, integer arithmetic only, > 0
    currency = db.Column(db.String(3), nullable=False)
    billing_interval = db.Column(db.String(10), nullable=False)
    customer_email = db.Column(db.String(255), nullable=False)

    status = db.Column(db.String(20), nullable=False, default="pending", index=True)

    # The hosted-checkout redirect target Paystack returned at
    # initialization — a customer redirect URL, never a credential. Kept
    # so a near-duplicate checkout click within the (separately
    # implemented) dedupe window can redirect back to this same still-
    # valid page instead of calling Paystack again.
    authorization_url = db.Column(db.String(500), nullable=True)
    # Channel Paystack reports the payment completed through once known
    # (e.g. "card", "mobile_money") — informational only.
    provider_channel = db.Column(db.String(30), nullable=True)

    # Small, explicitly allowlisted subset of Paystack's verify/webhook
    # response — see class docstring. Never the full raw provider payload.
    provider_snapshot = db.Column(db.JSON, nullable=True)

    # When Paystack reports the charge was paid (their timestamp) vs. when
    # WSF's own verify call actually confirmed it — kept distinct since
    # they can differ (network delay, a late-arriving webhook).
    paid_at = db.Column(db.DateTime(timezone=True), nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Last time WSF called Paystack's verify endpoint for this reference,
    # kept regardless of outcome — lets a later module throttle repeated
    # verify calls (e.g. a user spamming refresh on a pending checkout
    # page) without needing a separate rate-limit table.
    last_verification_attempt_at = db.Column(db.DateTime(timezone=True), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id])
    plan = db.relationship("CirclePlan", foreign_keys=[plan_id])
    subscription = db.relationship("CircleSubscription", foreign_keys=[subscription_id])
