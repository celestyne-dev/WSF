"""The ONE authority for Job and Opportunity date lifecycle.

Every public surface (list APIs, homepage modules, hubs, search, sitemap,
prerender, structured data, access endpoints) asks this module instead of
comparing dates itself, so "is this still live?" can never drift.

Dates are calendar dates (no time of day). A listing whose deadline is
today is still open today; it closes when the date has passed. "Today" is
the server's calendar date (date.today()).

JOBS
  reachable  the detail URL answers: published, scheduled once its
             published_date has arrived, or expired (shown as closed).
             draft/review/future-scheduled/archived never answer.
  live       reachable AND not expired AND the effective close date
             (the earlier of deadline / expiry_date) has not passed.
             Only live Jobs appear in listings, homepage modules, hubs,
             search, the sitemap and JobPosting structured data, and only
             a live Job's application destination is ever served.

OPPORTUNITIES
  reachable  published or closed (closed is shown as closed).
  state      draft | archived | closed | upcoming | open
             closed:   status closed, or deadline/expiry_date passed
             upcoming: published, opening_date in the future
             open:     published, opened (or no opening_date), not closed
  Listings default to OPEN only; UPCOMING is a separate filter. Only an
  open Opportunity serves its application destination.

A legacy row with no deadline and no expiry_date simply stays live until
an editor closes it (never closed by default).

Stored statuses follow the dates through expire_closed_listings(), run by
the existing publish-due-content maintenance command. Public behavior never
depends on that having run.
"""
from datetime import date, timedelta

from sqlalchemy import and_, func, or_

CLOSING_SOON_DAYS = 7


def today():
    return date.today()


def _earliest(*dates):
    present = [d for d in dates if d]
    return min(present) if present else None


# --- Jobs --------------------------------------------------------------------------------

def job_close_date(job):
    """The date after which applications are closed (deadline or expiry,
    whichever comes first), or None for an open-ended listing."""
    return _earliest(job.deadline, job.expiry_date)


def job_is_reachable(job, on=None):
    on = on or today()
    if job.status in ("published", "expired"):
        return True
    return job.status == "scheduled" and bool(job.published_date) and job.published_date <= on


def job_is_live(job, on=None):
    on = on or today()
    if job.status not in ("published", "scheduled") or not job_is_reachable(job, on):
        return False
    close = job_close_date(job)
    return close is None or close >= on


def live_jobs_clause(model, on=None):
    """SQL form of job_is_live, for list queries."""
    on = on or today()
    return and_(
        or_(model.status == "published", and_(model.status == "scheduled", model.published_date <= on)),
        or_(model.deadline.is_(None), model.deadline >= on),
        or_(model.expiry_date.is_(None), model.expiry_date >= on),
    )


# --- Opportunities -----------------------------------------------------------------------

def opportunity_close_date(opportunity):
    return _earliest(opportunity.deadline, opportunity.expiry_date)


def opportunity_state(opportunity, on=None):
    on = on or today()
    if opportunity.status in ("draft", "archived"):
        return opportunity.status
    close = opportunity_close_date(opportunity)
    if opportunity.status == "closed" or (close is not None and close < on):
        return "closed"
    if opportunity.opening_date and opportunity.opening_date > on:
        return "upcoming"
    return "open"


def opportunity_is_reachable(opportunity):
    return opportunity.status in ("published", "closed")


def opportunity_is_open(opportunity, on=None):
    return opportunity_state(opportunity, on) == "open"


def _opportunity_not_closed(model, on):
    return and_(
        model.status == "published",
        or_(model.deadline.is_(None), model.deadline >= on),
        or_(model.expiry_date.is_(None), model.expiry_date >= on),
    )


def open_opportunities_clause(model, on=None):
    on = on or today()
    return and_(_opportunity_not_closed(model, on), or_(model.opening_date.is_(None), model.opening_date <= on))


def upcoming_opportunities_clause(model, on=None):
    on = on or today()
    return and_(_opportunity_not_closed(model, on), model.opening_date.isnot(None), model.opening_date > on)


# --- Shared ------------------------------------------------------------------------------

def closing_info(close_date, on=None):
    """{closesOn, daysLeft, closingSoon} for a live listing's close date, or
    None when there is no close date. daysLeft is whole calendar days
    (0 = closes today)."""
    if not close_date:
        return None
    on = on or today()
    days = (close_date - on).days
    return {"closesOn": close_date.isoformat(), "daysLeft": days, "closingSoon": 0 <= days <= CLOSING_SOON_DAYS}


def closing_soon_clause(model, on=None, days=CLOSING_SOON_DAYS):
    on = on or today()
    close = func.least(func.coalesce(model.deadline, model.expiry_date), func.coalesce(model.expiry_date, model.deadline))
    return and_(close.isnot(None), close >= on, close <= on + timedelta(days=days))


def job_effective_state(job, on=None):
    """Admin label: Draft, In review, Scheduled, Open, Closing soon,
    Deadline passed (still stored as published), Expired, Archived."""
    on = on or today()
    if job.status in ("draft", "archived", "expired"):
        return job.status
    if job.status == "review":
        return "review"
    if job.status == "scheduled" and (not job.published_date or job.published_date > on):
        return "scheduled"
    close = job_close_date(job)
    if close is not None and close < on:
        return "deadline_passed"
    info = closing_info(close, on)
    return "closing_soon" if info and info["closingSoon"] else "open"


def opportunity_effective_state(opportunity, on=None):
    on = on or today()
    state = opportunity_state(opportunity, on)
    if state == "closed" and opportunity.status == "published":
        return "deadline_passed"
    if state == "open":
        info = closing_info(opportunity_close_date(opportunity), on)
        return "closing_soon" if info and info["closingSoon"] else "open"
    return state
