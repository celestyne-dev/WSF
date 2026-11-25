"""Named rate limits for public, abuse-prone endpoints (one place to review).

Strings use Flask-Limiter syntax; several limits separated by ";" all apply.
Counters are per client IP and live in Redis (database fallback), see
app/services/rate_limit_storage.py.

comment_* are used by the article comments API (app/api/v1/comments.py), keyed per
signed-in account rather than per client IP (comments require sign-in, and people
sharing an office or mobile network should not share one budget).
"""

LIMITS = {
    # Accounts and sessions
    "login": "10 per minute; 100 per day",
    "signup": "5 per minute; 20 per hour",
    "password_reset_request": "5 per hour",
    "password_reset_submit": "10 per hour",
    "session_refresh": "60 per minute",
    "two_factor_challenge": "5 per minute; 30 per hour",
    "two_factor_setup": "10 per minute; 60 per hour",
    "two_factor_manage": "10 per minute",
    # Newsletter
    "newsletter_subscribe": "5 per minute",
    "newsletter_unsubscribe": "5 per minute; 30 per hour",
    "newsletter_unsubscribe_link": "30 per minute",
    "newsletter_confirm": "30 per minute",
    # Step 16 account self-service (per client IP, shared store)
    "account_export": "5 per hour",
    "account_deletion": "10 per hour",
    "privacy_request": "5 per day",
    # Email verification (per client IP, shared Redis/PostgreSQL store)
    "email_verification_resend": "3 per 10 minutes; 10 per day",
    "email_verification_confirm": "30 per minute",
    # Public forms
    "contact": "5 per minute; 30 per day",
    "story_submission": "5 per minute; 20 per day",
    "story_image_upload": "10 per minute; 60 per day",
    # Comments (Batch 3)
    "comment_create": "6 per minute; 60 per day",
    "comment_edit": "20 per minute",
    "comment_report": "10 per minute; 50 per day",
}


def limit(name):
    """The limit string for `name` (KeyError for an unknown name, so a typo
    can never silently disable a limit)."""
    return LIMITS[name]
