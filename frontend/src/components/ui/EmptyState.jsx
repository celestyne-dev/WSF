export default function EmptyState({ title = 'Nothing here yet', description, action }) {
  return (
    <div className="flex flex-col items-center justify-center border border-dashed border-taupe-300 px-6 py-16 text-center">
      <h3 className="font-serif text-xl font-semibold text-charcoal">{title}</h3>
      {description && <p className="mt-2 max-w-md text-sm text-charcoal-600">{description}</p>}
      {action}
    </div>
  )
}
