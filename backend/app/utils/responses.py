"""A single consistent JSON envelope for every API response.

Success:  {"success": true, "data": ..., "meta": {...}?}
Error:    {"success": false, "error": {"message": ..., "code": ..., "details": ...}}

These return plain (dict, status) tuples rather than jsonify() Response
objects on purpose: Flask-RESTful's Api monkey-patches the whole app's
exception handling (not just its own routes) to re-run any response
through its own JSON representer, and re-serializing an already-built
Response object there raises "Object of type Response is not JSON
serializable". Plain dicts survive both Flask's native auto-jsonify and
Flask-RESTful's representer without that double-wrap.
"""
from marshmallow import ValidationError as MarshmallowValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException


class ApiError(Exception):
    """Raise from a view or service to produce a consistent error response."""

    def __init__(self, message, status=400, code=None, errors=None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code
        self.errors = errors


def success_response(data=None, meta=None, status=200, message=None):
    payload = {"success": True, "data": data}
    if message is not None:
        payload["message"] = message
    if meta is not None:
        payload["meta"] = meta
    return payload, status


def error_response(message, status=400, code=None, errors=None):
    error_body = {"message": message}
    if code:
        error_body["code"] = code
    if errors:
        error_body["details"] = errors
    return {"success": False, "error": error_body}, status


def register_error_handlers(app):
    from app.extensions import db

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        return error_response(exc.message, exc.status, exc.code, exc.errors)

    @app.errorhandler(MarshmallowValidationError)
    def handle_validation_error(exc):
        return error_response(
            "Validation failed.", 422, code="validation_error", errors=exc.messages
        )

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(exc):
        db.session.rollback()
        app.logger.warning("IntegrityError: %s", exc)
        return error_response(
            "A record with these details already exists.", 409, code="conflict"
        )

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc):
        code = (exc.name or "http_error").lower().replace(" ", "_")
        return error_response(exc.description or exc.name, exc.code, code=code)

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc):
        app.logger.exception("Unhandled exception")
        return error_response(
            "An unexpected error occurred.", 500, code="internal_error"
        )
