export default function Pagination({ pagination, onPageChange }) {
  if (!pagination || pagination.totalPages <= 1) return null
  const { page, totalPages } = pagination
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1)

  return (
    <nav aria-label="Pagination" className="mt-10 flex items-center justify-center gap-2">
      <button
        type="button"
        disabled={page <= 1}
        onClick={() => onPageChange(page - 1)}
        className="border border-taupe-300 px-3 py-2 text-sm font-medium text-charcoal disabled:opacity-40"
      >
        Previous
      </button>
      {pages.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPageChange(p)}
          aria-current={p === page ? 'page' : undefined}
          className={`h-9 w-9 text-sm font-medium ${p === page ? 'bg-plum-600 text-ivory' : 'border border-taupe-300 text-charcoal hover:border-burgundy-500/40'}`}
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        disabled={page >= totalPages}
        onClick={() => onPageChange(page + 1)}
        className="border border-taupe-300 px-3 py-2 text-sm font-medium text-charcoal disabled:opacity-40"
      >
        Next
      </button>
    </nav>
  )
}
