"""The controlled event-name registry for `POST /api/v1/analytics/events`.

Audited directly from every `trackEvent(...)` call site in
`frontend/src/**/*.jsx` (see the Analytics Dashboard final report) —
this list is not invented; it documents what the frontend already emits
today. New event names must be added here before the frontend can emit
them, so ingestion never silently accepts an unrecognized or typo'd
name (`articleView` vs `article_view` vs `view_article` never happens
because only the one canonical spelling below is accepted).

`family` groups events for reporting (a "view" family event feeds
content-performance counts; a "click" event is a CTA, not a completed
action; "conversion" events are genuinely completed actions — a
submitted form, a confirmed signup — never a mere click through).
"""

VIEW = "view"
CLICK = "click"
CONVERSION = "conversion"
SEARCH = "search"

# name -> family. Kept as one flat dict (not nested per content type) so
# ingestion validation and reporting can both do a single lookup.
EVENT_TAXONOMY = {
    # Content views
    "article_view": VIEW,
    "resource_view": VIEW,
    "job_view": VIEW,
    "opportunity_view": VIEW,
    "event_view": VIEW,
    "product_view": VIEW,
    "newsletter_archive_view": VIEW,
    "community_page_view": VIEW,
    "story_submission_page_view": VIEW,
    "mentorship_page_view": VIEW,
    "advertise_page_view": VIEW,
    "nomination_page_view": VIEW,
    # Search
    "search_performed": SEARCH,
    "search_result_click": SEARCH,
    # CTA clicks — a click is real engagement, never a completed action
    # on its own (see spec: a job-apply click is not a completed
    # application).
    "job_apply_click": CLICK,
    "job_save_click": CLICK,
    "job_share_click": CLICK,
    "opportunity_apply_click": CLICK,
    "event_registration_click": CLICK,
    "event_add_to_calendar_click": CLICK,
    "resource_download_click": CLICK,
    "resource_external_click": CLICK,
    "resource_premium_cta_click": CLICK,
    "product_cta_click": CLICK,
    "offering_cta_click": CLICK,
    "media_kit_request_click": CLICK,
    "media_kit_download": CLICK,
    "sponsor_impression": CLICK,
    "sponsor_click": CLICK,
    "article_share_click": CLICK,
    "resource_share_click": CLICK,
    "event_share_click": CLICK,
    "newsletter_share_click": CLICK,
    # Conversions — a real, completed, tracked action.
    "resource_download_success": CONVERSION,
    "newsletter_unsubscribe": CONVERSION,
    "community_join_start": CONVERSION,
    "community_join_submit": CONVERSION,
    "story_submission_start": CONVERSION,
    "story_submission_submit": CONVERSION,
    "story_submission_success": CONVERSION,
    "mentor_application_start": CONVERSION,
    "mentor_application_submit": CONVERSION,
    "mentee_application_start": CONVERSION,
    "mentee_application_submit": CONVERSION,
    "partnership_inquiry_submitted": CONVERSION,
    "advertise_inquiry_start": CONVERSION,
    "advertise_inquiry_submit": CONVERSION,
    "nomination_start": CONVERSION,
    "nomination_submit": CONVERSION,
    "nomination_success": CONVERSION,
}

KNOWN_EVENT_NAMES = tuple(sorted(EVENT_TAXONOMY.keys()))
