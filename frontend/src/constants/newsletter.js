// Newsletter subscriber statuses (backend app/models/newsletter.py). Shown
// as text everywhere, never by colour alone.
export const SUBSCRIBER_STATUSES = ['pending', 'active', 'legacy_unconfirmed', 'unsubscribed', 'bounced', 'complained']

export const SUBSCRIBER_STATUS_LABELS = {
  pending: 'Awaiting confirmation (not subscribed)',
  active: 'Confirmed subscriber',
  legacy_unconfirmed: 'Legacy – not confirmed (not exported)',
  unsubscribed: 'Unsubscribed (suppressed)',
  bounced: 'Bounced (suppressed)',
  complained: 'Complaint (suppressed)',
}

// Issue workflow: WSF prepares and exports; staff send externally and record it.
export const ISSUE_STATUSES = ['draft', 'ready', 'sent', 'archived']

export const ISSUE_STATUS_LABELS = {
  draft: 'Draft',
  ready: 'Ready to export',
  sent: 'Sent externally (recorded)',
  archived: 'Archived',
}
