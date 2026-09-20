export default function StatCard({ label, value, icon: Icon, hint }) {
  return (
    <div className="border border-taupe-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</p>
        {Icon && <Icon size={16} className="text-burgundy-500" />}
      </div>
      <p className="mt-2 font-serif text-3xl font-semibold text-charcoal">{value}</p>
      {hint && <p className="mt-1 text-xs text-charcoal-600">{hint}</p>}
    </div>
  )
}
