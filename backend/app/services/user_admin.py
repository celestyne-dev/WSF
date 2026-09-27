"""Admin User / Role administration — the CMS staff directory only.

A CMS `User` (this module) is never the same record as a Community
`Member`, a public `Person`/`Author` profile, a `NewsletterSubscriber`, or
a Mentorship/StorySubmission/Nomination applicant. Creating a staff
account here never creates or links any of those, and this module never
reads from them.

Role *definitions* (which permissions a role grants) are code-defined in
app/services/rbac.py and reseeded on every app start — this module only
ever changes which roles a USER holds, never a role's own permission set.
"""

import secrets

from app.extensions import db
from app.models.user import Role, User

SUPER_ADMIN_ROLE = "super_admin"


def normalize_email(email):
    return email.strip().lower()


def generate_temporary_password():
    """A cryptographically random, human-typeable temporary password. Never
    persisted anywhere in plaintext — the caller hashes it immediately via
    User.set_password() and returns it in the API response body exactly
    once so an admin can relay it out-of-band; it is never logged or
    written to an audit record.
    """
    return secrets.token_urlsafe(12)


def count_active_super_admins():
    return (
        User.query.join(User.roles)
        .filter(Role.name == SUPER_ADMIN_ROLE, User.is_active.is_(True))
        .distinct()
        .count()
    )


def is_last_active_super_admin(user):
    """True if `user` is currently an active super_admin AND no other
    active super_admin exists — i.e. removing their active status or their
    super_admin role right now would leave the CMS with zero super admins.
    """
    if not user.is_active or not user.has_role(SUPER_ADMIN_ROLE):
        return False
    return count_active_super_admins() <= 1


class UserAdminError(Exception):
    """Raised for a rejected admin user/role operation. Callers map this
    to a 403/409 ApiError — kept as a plain exception here so this service
    has no Flask/HTTP dependency.
    """

    def __init__(self, message, code="forbidden"):
        super().__init__(message)
        self.code = code


def create_staff_user(*, email, first_name, last_name, role_names, is_active, actor):
    email = normalize_email(email)
    if User.query.filter(db.func.lower(User.email) == email).first():
        raise UserAdminError("An account with this email already exists.", code="email_taken")

    roles = _resolve_roles(role_names, actor)

    user = User(email=email, first_name=first_name, last_name=last_name, is_active=is_active)
    temporary_password = generate_temporary_password()
    user.set_password(temporary_password)
    user.roles = roles
    db.session.add(user)
    db.session.commit()
    return user, temporary_password


def update_user_identity(user, *, first_name=None, last_name=None, email=None, country_code=None):
    if first_name is not None:
        user.first_name = first_name
    if last_name is not None:
        user.last_name = last_name
    if email is not None:
        normalized = normalize_email(email)
        existing = User.query.filter(db.func.lower(User.email) == normalized, User.id != user.id).first()
        if existing:
            raise UserAdminError("An account with this email already exists.", code="email_taken")
        user.email = normalized
    if country_code is not None:
        user.country_code = country_code or None
    db.session.commit()
    return user


def set_user_status(user, is_active, *, actor):
    if user.id == actor.id:
        raise UserAdminError("You cannot change your own account status.", code="self_action_forbidden")
    if not is_active and is_last_active_super_admin(user):
        raise UserAdminError(
            "This is the last active Super Admin — deactivate another Super Admin first, "
            "or promote someone else, before deactivating this account.",
            code="last_super_admin",
        )
    user.is_active = is_active
    db.session.commit()
    return user


def reset_user_password(user):
    temporary_password = generate_temporary_password()
    user.set_password(temporary_password)
    db.session.commit()
    return temporary_password


def _resolve_roles(role_names, actor):
    role_names = list(dict.fromkeys(role_names or []))
    if not role_names:
        return []

    roles = Role.query.filter(Role.name.in_(role_names)).all()
    found_names = {r.name for r in roles}
    unknown = set(role_names) - found_names
    if unknown:
        raise UserAdminError(f"Unknown role(s): {', '.join(sorted(unknown))}.", code="validation_error")

    if SUPER_ADMIN_ROLE in found_names and not actor.has_role(SUPER_ADMIN_ROLE):
        raise UserAdminError(
            "Only a Super Admin can grant or remove the Super Admin role.", code="super_admin_required"
        )

    return roles


def assign_user_roles(user, role_names, *, actor):
    if user.id == actor.id:
        raise UserAdminError("You cannot change your own roles.", code="self_action_forbidden")

    had_super_admin = user.has_role(SUPER_ADMIN_ROLE)
    new_roles = _resolve_roles(role_names, actor)
    will_have_super_admin = any(r.name == SUPER_ADMIN_ROLE for r in new_roles)

    # Removing the actor's own super_admin isn't reachable here (self is
    # already blocked above); this guards the cross-admin case — Admin A
    # editing Super Admin B's roles — plus reordering a role set that
    # simply never re-lists super_admin for an active last super admin.
    if had_super_admin and not will_have_super_admin and is_last_active_super_admin(user):
        raise UserAdminError(
            "This is the last active Super Admin — the Super Admin role can't be removed "
            "until another active Super Admin exists.",
            code="last_super_admin",
        )

    user.roles = new_roles
    db.session.commit()
    return user
