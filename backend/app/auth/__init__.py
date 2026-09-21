# Flask-JWT-Extended setup: login/refresh/logout views (app/api/v1/auth.py),
# bcrypt password hashing (security.py), JWT callbacks including the DB-backed
# revocation blocklist (jwt_callbacks.py), and the role/permission-based
# access-control decorators (decorators.py) used across every protected
# endpoint. Roles/permissions themselves live in app/models/user.py and are
# seeded by app/services/rbac.py.
