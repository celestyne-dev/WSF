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

send_email() never raises on delivery: a failure is a boundary every caller
must handle without crashing a request or leaking an SMTP error. It returns
True only when the message was handed off.

Email classes (Step 15) — every message gets the common footer:
  "Women Shaping Futures · <postal address from Studio> · Privacy Policy"
  (the address is omitted, never invented, while Studio leaves it blank).
  * TRANSACTIONAL (default): essential, answers something the person did
    (password reset, sign-in/security, event registration, learning
    enrolment, newsletter double-opt-in confirmation). No unsubscribe
    action: it would only switch off email the person needs.
  * OPTIONAL: non-essential email a person opted into (comment reply
    notifications). MUST carry its own unsubscribe link; it is shown in
    the footer and sent as RFC 2369 List-Unsubscribe with RFC 8058
    one-click (List-Unsubscribe-Post: List-Unsubscribe=One-Click).
"""
import smtplib
from email.message import EmailMessage

from flask import current_app

TRANSACTIONAL = "transactional"
OPTIONAL = "optional"
CATEGORIES = (TRANSACTIONAL, OPTIONAL)


def _site_base():
    return current_app.config["FRONTEND_URL"].rstrip("/")


def footer_text(unsubscribe_url=None):
    from app.services.site_settings import get_site_identity_raw

    identity = get_site_identity_raw()
    address = (identity.get("postal_address") or "").strip()
    name = identity.get("site_name") or "Women Shaping Futures"
    parts = [name] + ([" ".join(address.split())] if address else []) + [f"Privacy Policy: {_site_base()}/privacy"]
    lines = ["", "--", " · ".join(parts)]
    if unsubscribe_url:
        lines.append(f"Unsubscribe from these emails: {unsubscribe_url}")
    return "\n".join(lines) + "\n"


def footer_html(unsubscribe_url=None):
    from html import escape

    from app.services.site_settings import get_site_identity_raw

    identity = get_site_identity_raw()
    address = (identity.get("postal_address") or "").strip()
    name = escape(identity.get("site_name") or "Women Shaping Futures")
    parts = [name] + ([escape(" ".join(address.split()))] if address else [])
    parts.append(f'<a href="{escape(_site_base())}/privacy">Privacy Policy</a>')
    unsubscribe = (f'<br><a href="{escape(unsubscribe_url)}">Unsubscribe from these emails</a>'
                   if unsubscribe_url else "")
    return (f'<hr style="border:none;border-top:1px solid #ddd;margin:24px 0 12px">'
            f'<p style="font-size:12px;color:#666">{" · ".join(parts)}{unsubscribe}</p>')


def build_message(to, subject, text_body, html_body=None, *, category=TRANSACTIONAL, unsubscribe_url=None,
                  one_click_url=None):
    """The complete message (footer + headers). Raises ValueError for a
    programming error: an unknown category, or optional email without an
    unsubscribe link."""
    if category not in CATEGORIES:
        raise ValueError(f"Unknown email category {category!r}")
    if category == OPTIONAL and not (unsubscribe_url and one_click_url):
        raise ValueError("Optional email needs an unsubscribe link and a one-click unsubscribe URL")
    if category == TRANSACTIONAL:
        unsubscribe_url = one_click_url = None
    cfg = current_app.config
    from_name = cfg.get("SMTP_FROM_NAME") or "Women Shaping Futures"
    from_email = cfg.get("SMTP_FROM_EMAIL") or "no-reply@localhost"
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{from_name} <{from_email}>"
    message["To"] = to
    message["X-WSF-Email-Class"] = category
    if category == OPTIONAL:
        message["List-Unsubscribe"] = f"<{one_click_url}>"
        message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    message.set_content(text_body.rstrip("\n") + "\n" + footer_text(unsubscribe_url))
    if html_body:
        marker = "</body>"
        footer = footer_html(unsubscribe_url)
        html = html_body.replace(marker, footer + marker) if marker in html_body else html_body + footer
        message.add_alternative(html, subtype="html")
    return message


def send_email(to, subject, text_body, html_body=None, *, category=TRANSACTIONAL, unsubscribe_url=None,
               one_click_url=None):
    """Returns True if the message was handed off successfully (console
    backend: always; smtp backend: if the SMTP conversation completed
    without error), False otherwise."""
    message = build_message(to, subject, text_body, html_body, category=category, unsubscribe_url=unsubscribe_url,
                            one_click_url=one_click_url)
    backend = current_app.config.get("EMAIL_BACKEND", "console")
    if backend == "console":
        return _send_console(message)
    if backend == "smtp":
        return _send_smtp(message)
    current_app.logger.error("Unknown EMAIL_BACKEND=%r; email not sent.", backend)
    return False


def _send_console(message):
    # This is the only place in the codebase allowed to output full email
    # content (including a reset URL, when that's what's being sent) —
    # and only because create_app("production") refuses to start with
    # this backend selected (see config.require_production_settings),
    # so this branch is structurally unreachable outside dev/testing.
    headers = "\n".join(f"{k}: {v}" for k, v in message.items() if k not in ("Content-Type", "MIME-Version",
                                                                           "Content-Transfer-Encoding"))
    body = message.get_body(("plain",))
    current_app.logger.info(
        "---- DEV EMAIL (console backend; not actually sent) ----\n%s\n\n%s\n"
        "----------------------------------------------------------",
        headers,
        body.get_content() if body is not None else "",
    )
    return True


def _send_smtp(message):
    cfg = current_app.config
    host = cfg.get("SMTP_HOST")
    from_email = cfg.get("SMTP_FROM_EMAIL")

    if not host or not from_email:
        current_app.logger.error(
            "SMTP email backend is selected but SMTP_HOST/SMTP_FROM_EMAIL is not configured; email not sent."
        )
        return False

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
        # caller — log only that delivery failed (the class, never the
        # recipient address).
        current_app.logger.exception("SMTP email delivery failed (class=%s).", message.get("X-WSF-Email-Class"))
        return False
