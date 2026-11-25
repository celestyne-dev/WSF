import uuid as uuid_lib

from sqlalchemy.dialects.postgresql import JSONB

from app.extensions import db

user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = db.Table(
    "role_permissions",
    db.Column("role_id", db.Integer, db.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    db.Column("permission_id", db.Integer, db.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))


class Role(db.Model):
    """Roles for the platform: super_admin, admin, editor, author,
    moderator, partnerships_manager, opportunities_manager, events_manager,
    analyst, member, employer. Seeded via `flask seed-roles`
    (app/services/rbac.py) rather than hard-coded into views.
    """

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))

    permissions = db.relationship("Permission", secondary=role_permissions, backref="roles")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid_lib.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    display_name = db.Column(db.String(150))
    bio = db.Column(db.Text)
    country_code = db.Column(db.String(10), db.ForeignKey("countries.code"), nullable=True)
    avatar_media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    is_verified = db.Column(db.Boolean, nullable=False, default=False)
    # True from staff creation/admin password reset (a temporary password
    # was generated) until the user successfully completes
    # POST /auth/change-password herself. Never cleared by logging in —
    # see app/auth/decorators.py's centralized enforcement.
    must_change_password = db.Column(db.Boolean, nullable=False, default=False)
    # Bumped by app/services/refresh_sessions.py's invalidate_user_sessions()
    # whenever the account's trust changes (role change, deactivation,
    # password reset by link or by an administrator, two-factor enabled or
    # reset) to invalidate every access token and refresh
    # session issued before that point — see app/auth/jwt_callbacks.py's
    # check_if_revoked, which rejects a token whose auth_version claim
    # doesn't match this column. A token with no auth_version claim at all
    # (issued before this column existed) is treated as version 0, so
    # deploying this does not retroactively log anyone out. Never bumped
    # merely by requesting a reset email, logging in, or changing a
    # password through the normal /auth/change-password flow.
    auth_version = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    last_login_at = db.Column(db.DateTime(timezone=True))
    # Self-service account deletion (Step 16, app/services/account_deletion.py):
    # requested -> scheduled for +14 days (grace period, cancellable); every
    # session is revoked at request time and the account can't be used;
    # after the date it is purged automatically.
    deletion_requested_at = db.Column(db.DateTime(timezone=True))
    deletion_scheduled_for = db.Column(db.DateTime(timezone=True), index=True)
    deletion_remove_comments = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    # Retention (Step 17): when the "account will be deleted for inactivity"
    # email was handed off; cleared when the member uses the account again.
    inactivity_warning_sent_at = db.Column(db.DateTime(timezone=True))
    # Signup confirmations (Step 18; app/services/account_policy.py). No date
    # of birth is ever collected: only the explicit "at least N years old"
    # confirmation, the age it was confirmed against, and the Terms/Privacy
    # versions accepted. Null for accounts created before Step 18 or by staff.
    age_confirmed_at = db.Column(db.DateTime(timezone=True))
    age_confirmed_minimum = db.Column(db.SmallInteger)
    terms_version_accepted = db.Column(db.String(120))
    privacy_version_accepted = db.Column(db.String(120))
    legal_accepted_at = db.Column(db.DateTime(timezone=True))
    # How the learner's name appears on PUBLIC certificate verification
    # (Step 20): "full" or "initials". A live display preference applied to
    # each certificate's immutable recipient_name; never rewrites a
    # certificate. The PDF (owner/staff only) always carries the full name.
    certificate_public_name = db.Column(db.String(10), nullable=False, default="full", server_default="full")
    # Email ownership (Batch 4 corrections). is_verified above is NOT proof
    # of ownership: it was only ever set by create-superadmin. Only
    # email_verified_at (set by clicking a first-party verification link)
    # proves the account holder controls the address.
    email_verified_at = db.Column(db.DateTime(timezone=True))
    # True for accounts registered under the verification-required flow:
    # they get no normal authenticated access until verified. False for
    # every account that predates it (access preserved; verification offered).
    email_verification_required = db.Column(db.Boolean, nullable=False, default=False, server_default="false")
    # Private career-goal preferences (Career Hub CAREER_GOALS keys, at
    # most 3), used only to personalize this user's own Career Hub. Never
    # exposed publicly. `career_goals_prompted_at` records that the
    # optional goal prompt was answered or skipped, so it is never nagging.
    # JSONB on Postgres (not plain JSON): existing queries run SELECT
    # DISTINCT over users, and Postgres `json` has no equality operator.
    career_goals = db.Column(db.JSON().with_variant(JSONB(), "postgresql"))
    career_goals_prompted_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    roles = db.relationship("Role", secondary=user_roles, backref="users")
    country = db.relationship("Country", foreign_keys=[country_code])
    avatar = db.relationship("Media", foreign_keys=[avatar_media_id])

    def set_password(self, raw_password):
        from app.auth.security import hash_password

        self.password_hash = hash_password(raw_password)

    def check_password(self, raw_password):
        from app.auth.security import verify_password

        return verify_password(raw_password, self.password_hash)

    def role_names(self):
        return {role.name for role in self.roles}

    def permission_names(self):
        names = set()
        for role in self.roles:
            names.update(permission.name for permission in role.permissions)
        return names

    def has_role(self, *names):
        return bool(self.role_names() & set(names))

    def has_permission(self, *names):
        return bool(self.permission_names() & set(names))

    @property
    def full_name(self):
        return self.display_name or f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f"<User {self.email}>"
