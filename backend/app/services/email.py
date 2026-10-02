"""Minimal, provider-neutral outbound email service.

Two backends, selected by the EMAIL_BACKEND config value (see config.py):

- "console": logs the email instead of sending it. Local development/
  testing only — require_production_settings() (config.py) refuses to
  start ProductionConfig with this backend, so a raw reset link can
  never be printed in a real deployment.
- "smtp": sends via Python's stdlib smtplib/email, no vendor SDK. Reads
  SMTP_HOST/PORT/USERNAME/PASSWORD/USE_TLS/FROM_EMAIL/FROM_NAME from
  config — all environment-variable-backed, never hard-coded, never
  logged.

send_email() never raises: a delivery failure is a boundary every caller
must be able to handle without crashing a request or leaking an SMTP
error to an anonymous client (see app/services/password_reset.py, the
only current caller).
"""
import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(to, subject, text_body, html_body=None):
    """Returns True if the message was handed off successfully (console
    backend: always; smtp backend: if the SMTP conversation completed
    without error), False otherwise.
    """
    backend = current_app.config.get("EMAIL_BACKEND", "console")
    if backend == "console":
        return _send_console(to, subject, text_body)
    if backend == "smtp":
        return _send_smtp(to, subject, text_body, html_body)
    current_app.logger.error("Unknown EMAIL_BACKEND=%r; email not sent.", backend)
    return False


def _send_console(to, subject, text_body):
    # This is the only place in the codebase allowed to output full email
    # content (including a reset URL, when that's what's being sent) —
    # and only because create_app("production") refuses to start with
    # this backend selected (see config.require_production_settings),
    # so this branch is structurally unreachable outside dev/testing.
    current_app.logger.info(
        "---- DEV EMAIL (console backend; not actually sent) ----\nTo: %s\nSubject: %s\n\n%s\n"
        "----------------------------------------------------------",
        to,
        subject,
        text_body,
    )
    return True


def _send_smtp(to, subject, text_body, html_body):
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    from_email = cfg.get("SMTP_FROM_EMAIL")

    if not host or not from_email:
        current_app.logger.error(
            "SMTP email backend is selected but SMTP_HOST/SMTP_FROM_EMAIL is not configured; email not sent."
        )
        return False

    from_name = cfg.get("SMTP_FROM_NAME") or "Women Shaping Futures"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    try:
        with smtplib.SMTP(host, cfg.get("SMTP_PORT") or 587, timeout=10) as server:
            if cfg.get("SMTP_USE_TLS", True):
                server.starttls()
            username = cfg.get("SMTP_USERNAME")
            password = cfg.get("SMTP_PASSWORD")
            if username and password:
                server.login(username, password)
            server.send_message(message)
        return True
    except Exception:
        # Never leak the SMTP host, credentials, or a stack trace to the
        # caller — log only that delivery failed. The caller
        # (app/services/password_reset.py) already handles a False
        # return by invalidating the token and still returning the same
        # generic public response regardless.
        current_app.logger.exception("SMTP email delivery failed (to=%s).", to)
        return False
