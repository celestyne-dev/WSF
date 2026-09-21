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
    return None


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
