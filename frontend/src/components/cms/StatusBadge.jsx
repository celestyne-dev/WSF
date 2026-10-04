import { Clock, Eye, AlertCircle, CheckCircle2 } from 'lucide-react'

const STYLES = {
  published: 'bg-emerald-100 text-emerald-700',
  active: 'bg-emerald-100 text-emerald-700',
  accepted: 'bg-emerald-100 text-emerald-700',
  closed_won: 'bg-emerald-100 text-emerald-700',
  completed: 'bg-emerald-100 text-emerald-700',
  draft: 'bg-taupe-200 text-charcoal-600',
  received: 'bg-taupe-200 text-charcoal-600',
  new: 'bg-taupe-200 text-charcoal-600',
  pending: 'bg-taupe-200 text-charcoal-600',
  scheduled: 'bg-blush-200 text-burgundy-700',
  reviewing: 'bg-blush-200 text-burgundy-700',
  under_review: 'bg-blush-200 text-burgundy-700',
  in_review: 'bg-blush-200 text-burgundy-700',
  changes_requested: 'bg-amber-100 text-amber-700',
  approved: 'bg-blush-200 text-burgundy-700',
  matched: 'bg-blush-200 text-burgundy-700',
  converted: 'bg-emerald-100 text-emerald-700',
  duplicate: 'bg-amber-100 text-amber-700',
  verified: 'bg-emerald-100 text-emerald-700',
  self_attested: 'bg-blush-200 text-burgundy-700',
  unverified: 'bg-taupe-200 text-charcoal-600',
  reviewed: 'bg-blush-200 text-burgundy-700',
  in_discussion: 'bg-blush-200 text-burgundy-700',
  invited: 'bg-blush-200 text-burgundy-700',
  contacted: 'bg-blush-200 text-burgundy-700',
  qualified: 'bg-blush-200 text-burgundy-700',
  proposal: 'bg-blush-200 text-burgundy-700',
  negotiating: 'bg-blush-200 text-burgundy-700',
  archived: 'bg-taupe-100 text-charcoal-600/70',
  unavailable: 'bg-amber-100 text-amber-700',
  ended: 'bg-taupe-100 text-charcoal-600/70',
  past: 'bg-taupe-100 text-charcoal-600/70',
  rejected: 'bg-rose-100 text-rose-600',
  cancelled: 'bg-rose-100 text-rose-600',
  declined: 'bg-rose-100 text-rose-600',
  registered: 'bg-blush-200 text-burgundy-700',
  attended: 'bg-emerald-100 text-emerald-700',
  current: 'bg-blush-200 text-burgundy-700',
  withdrawn: 'bg-rose-100 text-rose-600',
}

// Editorial workflow states must not be distinguished by color alone (see
// AdminArticleEditor/AdminArticles/AdminEditorialCalendar) — a small icon
// is added only for this curated set so every other module's StatusBadge
// usage renders exactly as before.
const ICONS = {
  in_review: Eye,
  changes_requested: AlertCircle,
  approved: CheckCircle2,
  scheduled: Clock,
}

export default function StatusBadge({ status }) {
  const style = STYLES[status] || 'bg-taupe-200 text-charcoal-600'
  const Icon = ICONS[status]
  return (
    <span className={`inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${style}`}>
      {Icon && <Icon size={11} aria-hidden="true" />}
      {status?.replace(/_/g, ' ')}
    </span>
  )
}
