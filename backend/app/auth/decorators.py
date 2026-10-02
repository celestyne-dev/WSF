from functools import wraps

from flask_jwt_extended import current_user, verify_jwt_in_request

from app.utils.responses import error_response


def _require_active_user():
    verify_jwt_in_request()
    # current_user is a LocalProxy — `is None` is always False even when it
    # wraps None (e.g. the JWT's user was deleted after the token was
    # issued), so check truthiness instead, which the proxy correctly
    # delegates to the wrapped object.
    if not current_user or not current_user.is_active:
        return error_response("Account is inactive or no longer exists.", 403, code="forbidden")
    # A temporary/reset password forces a change before anything else —
    # checked here, ahead of the permission/role evaluation each wrapper
    # below does next, so it can't be bypassed by holding any particular
    # permission. Read fresh off the DB-backed User on every request (never
    # cached in the JWT), so the moment POST /auth/change-password clears
    # it, the very next request is let through — no re-login required. The
    # small set of session/auth endpoints a forced-change user still needs
    # (login, /auth/me, /auth/change-password, logout, refresh) are all
    # plain @jwt_required() views that never call this helper, so they are
    # exempt by construction, not by a bypass list here.
    if current_user.must_change_password:
        return error_response(
            "You must change your password before continuing.", 403, code="password_change_required"
        )
    return None


def active_user_required(fn):
    """For a protected endpoint that needs no specific permission/role —
    just a valid, active, non-forced-change session (e.g. MediaDetailResource.get,
    which any authenticated staff member may read). Prefer
    permission_required()/roles_required() when the endpoint does have a
    permission or role to check; this exists so such endpoints don't have to
    fall back to a bare @jwt_required() that would skip the
    must_change_password guard above.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        denied = _require_active_user()
        if denied:
            return denied
        return fn(*args, **kwargs)

    return wrapper


def permission_required(*permission_names):
    """Allow the request through if the current user holds ANY of the
    named permissions (see app/services/rbac.py for the role -> permission
    map). Use several names to accept alternatives, e.g.
    permission_required("media.upload", "media.manage").
    """

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            denied = _require_active_user()
            if denied:
                return denied
            if not current_user.has_permission(*permission_names):
                return error_response(
                    "You do not have permission to perform this action.", 403, code="forbidden"
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def roles_required(*role_names):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            denied = _require_active_user()
            if denied:
                return denied
            if not current_user.has_role(*role_names):
                return error_response("You do not have the required role.", 403, code="forbidden")
            return fn(*args, **kwargs)

        return wrapper

    return decorator
