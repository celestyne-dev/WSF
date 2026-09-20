const STYLES = {
  published: 'bg-emerald-100 text-emerald-700',
  active: 'bg-emerald-100 text-emerald-700',
  accepted: 'bg-emerald-100 text-emerald-700',
  closed_won: 'bg-emerald-100 text-emerald-700',
  draft: 'bg-taupe-200 text-charcoal-600',
  received: 'bg-taupe-200 text-charcoal-600',
  new: 'bg-taupe-200 text-charcoal-600',
  scheduled: 'bg-blush-200 text-burgundy-700',
  reviewing: 'bg-blush-200 text-burgundy-700',
  in_discussion: 'bg-blush-200 text-burgundy-700',
  invited: 'bg-blush-200 text-burgundy-700',
  archived: 'bg-taupe-100 text-charcoal-600/70',
  ended: 'bg-taupe-100 text-charcoal-600/70',
  rejected: 'bg-rose-100 text-rose-600',
}

export default function StatusBadge({ status }) {
  const style = STYLES[status] || 'bg-taupe-200 text-charcoal-600'
  return <span className={`inline-flex items-center px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${style}`}>{status?.replace(/_/g, ' ')}</span>
}
