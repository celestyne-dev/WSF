from datetime import date

# A deliberately small lifecycle graph — this is a general-inquiry inbox,
# not a ticketing system (see task spec STATUS TRANSITIONS). Reopening is
# allowed from resolved/closed since real staff workflows sometimes need
# it, but every other move is a one-way triage decision.
CONTACT_STATUS_TRANSITIONS = {
    "new": {"in_progress", "spam", "closed"},
    "in_progress": {"resolved", "spam", "closed"},
    "resolved": {"closed", "in_progress"},
    "closed": {"in_progress"},
    "spam": {"new"},
}


def generate_contact_reference(inquiry):
    """A human-friendly, unique, immutable contact reference — e.g.
    "WSF-CON-2026-000123". Called once, right after the inquiry has been
    flushed and has an id, so the id (already guaranteed unique by the
    database) can be used directly rather than maintaining a separate
    per-year sequence table. Same pattern as Order.reference.
    """
    year = inquiry.created_at.year if inquiry.created_at else date.today().year
    return f"WSF-CON-{year}-{inquiry.id:06d}"


def is_valid_contact_status_transition(from_status, to_status):
    if from_status == to_status:
        return True
    return to_status in CONTACT_STATUS_TRANSITIONS.get(from_status, set())
