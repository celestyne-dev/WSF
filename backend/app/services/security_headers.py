"""HTTP security headers for every Flask response.

All responses:
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY (older browsers; CSP frame-ancestors for new ones)
  Permissions-Policy: every powerful feature WSF doesn't use is off; only
    fullscreen / picture-in-picture / encrypted-media stay available to WSF
    and the four allowlisted video players (their iframes ask for them).
  Strict-Transport-Security (HSTS_ENABLED, i.e. production, and only on an
    HTTPS request): max-age=31536000; includeSubDomains. No "preload".

HTML documents also get the Content Security Policy, built per request from
what WSF actually loads (build_csp below). It is sent as
Content-Security-Policy-Report-Only unless CSP_MODE == "enforce"; reports go
to POST /api/v1/security/csp-report (app/api/v1/security.py).

Third-party origins are added ONLY for integrations that are configured in
Studio (app/services/tracking_settings.py), so an unconfigured tracker never
appears in the policy. Paystack needs no entry: checkout is a full-page
navigation to Paystack's own site and back, never a script, frame or fetch.
"""
import secrets

from flask import current_app, has_request_context, request

VIDEO_PLAYERS = (
    "https://www.youtube-nocookie.com",
    "https://player.vimeo.com",
    "https://fast.wistia.net",
    "https://www.loom.com",
)

# Per Google's CSP guidance for Google Analytics 4: measurement hits go to
# region-specific subdomains, so these wildcards can't be narrowed further.
GA4_SOURCES = {
    "script-src": ["https://*.googletagmanager.com"],
    "img-src": ["https://*.google-analytics.com", "https://*.googletagmanager.com"],
    "connect-src": ["https://*.google-analytics.com", "https://*.analytics.google.com",
                    "https://*.googletagmanager.com"],
}
LINKEDIN_SOURCES = {
    "script-src": ["https://snap.licdn.com"],
    "img-src": ["https://px.ads.linkedin.com"],
    "connect-src": ["https://px.ads.linkedin.com"],
}
META_SOURCES = {
    "script-src": ["https://connect.facebook.net"],
    "img-src": ["https://www.facebook.com"],
    "connect-src": ["https://www.facebook.com"],
}

REPORT_PATH = "/api/v1/security/csp-report"
HSTS_VALUE = "max-age=31536000; includeSubDomains"

_POWERFUL_FEATURES_OFF = (
    "accelerometer", "ambient-light-sensor", "autoplay", "bluetooth", "browsing-topics", "camera",
    "display-capture", "geolocation", "gyroscope", "hid", "idle-detection", "magnetometer", "microphone",
    "midi", "payment", "publickey-credentials-get", "screen-wake-lock", "serial", "usb", "xr-spatial-tracking",
)


def permissions_policy():
    players = " ".join(f'"{origin}"' for origin in VIDEO_PLAYERS)
    shared = [f"{feature}=(self {players})" for feature in ("fullscreen", "picture-in-picture", "encrypted-media")]
    return ", ".join([f"{feature}=()" for feature in _POWERFUL_FEATURES_OFF] + shared)


def csp_nonce():
    """One random nonce per request (for the style tag a UI library injects)."""
    if not has_request_context():
        return None
    # Stored on the request itself (not `g`, which an outer app context can
    # share between requests): a fresh nonce for every request.
    if "wsf.csp_nonce" not in request.environ:
        request.environ["wsf.csp_nonce"] = secrets.token_urlsafe(16)
    return request.environ["wsf.csp_nonce"]


def build_csp(trackers, nonce=None):
    """The policy as {directive: [sources]}. `trackers` = configured IDs
    (tracking_settings.active_trackers())."""
    policy = {
        "default-src": ["'self'"],
        "script-src": ["'self'"],
        # The static stylesheet is 'self'; the nonce covers the one <style>
        # element react-toastify inserts at runtime (it accepts the nonce).
        "style-src": ["'self'"] + ([f"'nonce-{nonce}'"] if nonce else []),
        # data:/blob: for locally generated previews (media uploads, QR codes).
        "img-src": ["'self'", "data:", "blob:"],
        "font-src": ["'self'"],
        "connect-src": ["'self'"],
        "media-src": ["'self'"],
        "frame-src": list(VIDEO_PLAYERS),
        "object-src": ["'none'"],
        "base-uri": ["'self'"],
        "form-action": ["'self'"],
        "frame-ancestors": ["'none'"],
        "manifest-src": ["'self'"],
        "worker-src": ["'self'"],
    }
    for key, sources in (("ga4MeasurementId", GA4_SOURCES), ("linkedinPartnerId", LINKEDIN_SOURCES),
                         ("metaPixelId", META_SOURCES)):
        if trackers.get(key):
            for directive, extra in sources.items():
                policy[directive] = policy[directive] + [s for s in extra if s not in policy[directive]]
    return policy


def serialize_csp(policy, report_uri=REPORT_PATH):
    parts = [f"{name} {' '.join(sources)}" for name, sources in policy.items()]
    # report-uri only: verified end to end in Chromium (reports reach
    # app/api/v1/security.py). report-to / Reporting-Endpoints are left out on
    # purpose: when present Chromium sends ONLY through the Reporting API,
    # whose out-of-band delivery could not be verified here.
    parts.append(f"report-uri {report_uri}")
    return "; ".join(parts)


def csp_header_name():
    mode = (current_app.config.get("CSP_MODE") or "report-only").strip().lower()
    return "Content-Security-Policy" if mode == "enforce" else "Content-Security-Policy-Report-Only"


def _is_html(response):
    return (response.mimetype or "") == "text/html"


def _insert_nonce_meta(response, nonce):
    """Server-rendered HTML carries the nonce so the app can hand it to the
    library that injects a <style> element."""
    if response.direct_passthrough or response.is_streamed:
        return
    body = response.get_data(as_text=True)
    if 'name="csp-nonce"' in body or "</head>" not in body:
        return
    response.set_data(body.replace("</head>", f'<meta name="csp-nonce" content="{nonce}">\n</head>', 1))


def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers["Permissions-Policy"] = permissions_policy()
    if current_app.config.get("HSTS_ENABLED") and request.is_secure:
        response.headers["Strict-Transport-Security"] = HSTS_VALUE
    if _is_html(response):
        from app.services.tracking_settings import active_trackers

        nonce = csp_nonce()
        try:
            trackers = active_trackers()
        except Exception:  # a settings read must never break page delivery
            trackers = {}
        response.headers[csp_header_name()] = serialize_csp(build_csp(trackers, nonce))
        _insert_nonce_meta(response, nonce)
    return response
