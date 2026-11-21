"""Keeps stored Job/Opportunity statuses in step with their dates.

Public behavior never depends on this having run (listing_lifecycle decides
from the dates); this only keeps Studio accurate:

  Job          published / scheduled  + close date passed  -> expired
  Opportunity  published              + close date passed  -> closed

Nothing is deleted, archived or otherwise rewritten; rows without a close
date are never touched. Idempotent (a second run finds nothing to change)
and transaction-safe: one UPDATE per model in a single commit. Called by
`flask publish-due-content` (the existing scheduled maintenance command) and
available on its own as `flask expire-closed-listings`.
"""
from sqlalchemy import and_, or_

from app.extensions import db
from app.services.listing_lifecycle import today as lifecycle_today


def _past_close(model, on):
    return or_(and_(model.deadline.isnot(None), model.deadline < on), and_(model.expiry_date.isnot(None), model.expiry_date < on))


def expire_closed_listings(on=None):
    """Returns {"jobs": [ids], "opportunities": [ids]} that changed."""
    from app.models.opportunity import Job, Opportunity

    on = on or lifecycle_today()
    job_ids = [row.id for row in Job.query.with_entities(Job.id).filter(
        Job.status.in_(["published", "scheduled"]), _past_close(Job, on)).all()]
    opp_ids = [row.id for row in Opportunity.query.with_entities(Opportunity.id).filter(
        Opportunity.status == "published", _past_close(Opportunity, on)).all()]
    try:
        if job_ids:
            Job.query.filter(Job.id.in_(job_ids), Job.status.in_(["published", "scheduled"])).update(
                {Job.status: "expired"}, synchronize_session=False)
        if opp_ids:
            Opportunity.query.filter(Opportunity.id.in_(opp_ids), Opportunity.status == "published").update(
                {Opportunity.status: "closed"}, synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {"jobs": job_ids, "opportunities": opp_ids}
