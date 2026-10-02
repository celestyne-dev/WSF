from app.extensions import db, jwt
from app.utils.responses import error_response


def register_jwt_callbacks(app):
    from app.models.token_blocklist import TokenBlocklist
    from app.models.user import User

    @jwt.user_identity_loader
    def user_identity_lookup(user):
        return str(user.id) if hasattr(user, "id") else str(user)

    @jwt.user_lookup_loader
    def user_lookup_callback(_jwt_header, jwt_data):
        return db.session.get(User, int(jwt_data["sub"]))

    @jwt.additional_claims_loader
    def add_claims(identity_user):
        claims = {}
        if hasattr(identity_user, "role_names"):
            claims["roles"] = sorted(identity_user.role_names())
        if hasattr(identity_user, "auth_version"):
            # Stamped into every newly issued access/refresh token (this
            # loader is used by both create_access_token() and
            # create_refresh_token() for any identity) — see
            # check_if_revoked below, and app/services/password_reset.py,
            # which is the only thing that ever bumps User.auth_version.
            claims["auth_version"] = identity_user.auth_version
        return claims

    @jwt.token_in_blocklist_loader
    def check_if_revoked(_jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        if db.session.query(TokenBlocklist.id).filter_by(jti=jti).first() is not None:
            return True

        # A token minted before this claim existed carries no
        # auth_version at all — treated as version 0 so deploying this
        # doesn't retroactively revoke every already-issued session.
        # Comparison is skipped (not revoked) if the user is gone by now;
        # @jwt_required()'s identity lookup is the right place to reject
        # a since-deleted user, not this blocklist check.
        token_auth_version = jwt_payload.get("auth_version", 0)
        user_id = jwt_payload.get("sub")
        if user_id is None:
            return False
        user = db.session.get(User, int(user_id))
        if user is None:
            return False
        return token_auth_version != user.auth_version

    @jwt.unauthorized_loader
    def missing_token_callback(reason):
        return error_response(reason, 401, code="authorization_required")

    @jwt.invalid_token_loader
    def invalid_token_callback(reason):
        return error_response(reason, 422, code="invalid_token")

    @jwt.expired_token_loader
    def expired_token_callback(_jwt_header, _jwt_payload):
        return error_response("Token has expired.", 401, code="token_expired")

    @jwt.revoked_token_loader
    def revoked_token_callback(_jwt_header, _jwt_payload):
        return error_response("Token has been revoked.", 401, code="token_revoked")

    @jwt.needs_fresh_token_loader
    def needs_fresh_token_callback(_jwt_header, _jwt_payload):
        return error_response("A fresh token is required for this action.", 401, code="fresh_token_required")
