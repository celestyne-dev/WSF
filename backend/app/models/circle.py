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
    currency = db.Column(db.String(3), nullable=False, default="USD")

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
