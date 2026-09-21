from app.extensions import db
from app.models.user import Permission, Role

# Baseline role -> permission map for the platform roles named in
# app/models/user.py. "*" grants every known permission (super_admin).
# Extend this as later phases add resource-specific permissions (e.g.
# "opportunities.manage" already covers Phase 5's Opportunity/Job models).
ROLE_PERMISSIONS = {
    "super_admin": ["*"],
    "admin": [
        "users.manage",
        "articles.manage",
        "articles.publish",
        "taxonomy.manage",
        "people.manage",
        "media.manage",
        "settings.manage",
        "opportunities.manage",
        "jobs.manage",
        "events.manage",
        "resources.manage",
        "partnerships.manage",
        "submissions.manage",
        "nominations.manage",
        "newsletter.manage",
        "analytics.view",
    ],
    "editor": ["articles.manage", "articles.publish", "taxonomy.manage", "people.manage", "media.manage"],
    "author": ["articles.create", "articles.edit_own", "media.upload"],
    "moderator": ["submissions.manage", "nominations.manage"],
    "partnerships_manager": ["partnerships.manage"],
    "opportunities_manager": ["opportunities.manage", "jobs.manage"],
    "events_manager": ["events.manage"],
    "analyst": ["analytics.view"],
    "member": ["profile.manage"],
    "employer": ["jobs.create_own"],
}


def seed_roles_and_permissions():
    """Idempotently create the standard roles and permissions. Safe to
    re-run — existing rows are reused, not duplicated.
    """
    all_permission_names = sorted(
        {name for names in ROLE_PERMISSIONS.values() for name in names if name != "*"}
    )
    permissions_by_name = {}
    for name in all_permission_names:
        permission = Permission.query.filter_by(name=name).first()
        if permission is None:
            permission = Permission(name=name)
            db.session.add(permission)
        permissions_by_name[name] = permission
    db.session.flush()

    roles_by_name = {}
    for role_name, permission_names in ROLE_PERMISSIONS.items():
        role = Role.query.filter_by(name=role_name).first()
        if role is None:
            role = Role(name=role_name)
            db.session.add(role)
        if "*" in permission_names:
            role.permissions = list(Permission.query.all())
        else:
            role.permissions = [permissions_by_name[name] for name in permission_names]
        roles_by_name[role_name] = role

    db.session.commit()
    return roles_by_name
