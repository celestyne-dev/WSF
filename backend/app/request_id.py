"""A minimal request/correlation ID — generated per request (or reused
from a caller-supplied X-Request-ID, validated), attached to `g`, echoed
back in the response header, and included in server logs for unexpected
errors (see app/utils/responses.py). No tracing platform, just a plain
string that lets one HTTP request be found across a handful of log lines.
"""
import re
import uuid

from flask import g, request

_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _incoming_or_new_request_id():
    incoming = request.headers.get("X-Request-ID")
    if incoming and _VALID_REQUEST_ID.match(incoming):
        return incoming
    return uuid.uuid4().hex


def register_request_id(app):
    @app.before_request
    def _assign_request_id():
        g.request_id = _incoming_or_new_request_id()

    @app.after_request
    def _echo_request_id(response):
        request_id = getattr(g, "request_id", None)
        if request_id:
            response.headers["X-Request-ID"] = request_id
        return response
