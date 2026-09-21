import uuid as uuid_lib

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
    last_login_at = db.Column(db.DateTime(timezone=True))
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
