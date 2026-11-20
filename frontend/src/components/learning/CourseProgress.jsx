// Real progress only (from the learner's enrollment). The bar is
// decorative; the text says the same thing for screen readers and for
// anyone who can't see the colour.
export default function CourseProgress({ enrollment, compact = false, label = 'Your progress' }) {
  if (!enrollment || enrollment.status !== 'active' || !enrollment.totalLessons) return null
  const percent = Math.max(0, Math.min(100, Math.round(enrollment.progressPercent || 0)))
  return (
    <div className={compact ? '' : 'rounded-card border border-taupe-200 bg-white p-4'}>
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">{label}</p>
        <p className="font-serif text-2xl font-semibold text-charcoal">{percent}%</p>
      </div>
      <div
        className="mt-2 h-2 overflow-hidden rounded-full bg-taupe-100"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        aria-label={`${label}: ${percent}%`}
      >
        <div className="h-full rounded-full bg-plum-600 transition-[width]" style={{ width: `${percent}%` }} />
      </div>
      <p className="mt-2 text-sm text-charcoal-600">
        {enrollment.completedLessons} of {enrollment.totalLessons} lessons complete
      </p>
    </div>
  )
}
