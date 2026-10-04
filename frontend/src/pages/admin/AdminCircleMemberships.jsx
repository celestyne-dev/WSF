import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { fetchCircleSubscriptions } from '../../api/circle'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const STATUSES = ['', 'pending', 'active', 'past_due', 'cancelled', 'expired', 'revoked']

export default function AdminCircleMemberships() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchCircleSubscriptions({ q: query || undefined, status: status || undefined, page, perPage: 25 })
      .then((res) => active && setResult(res))
      .catch(() => active && setError('Something went wrong loading WSF Circle memberships. Please try again.'))
    return () => {
      active = false
    }
  }, [query, status, page])

  return (
    <div>
      <AdminPageHeader
        title="WSF Circle Memberships"
        description="Staff-recorded subscriptions — manual, externally-confirmed, or complimentary. No payment gateway is connected."
        actions={
          <Link to="/admin/circle/memberships/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> Record subscription
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search name or email…"
            className="w-64 text-sm focus:outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setPage(1)
            setStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s || 'All statuses'}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load memberships" description={error} />}
      {!error && result === null && <PageLoader />}
      {!error && result !== null && (
        result.items.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[840px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Account</th>
                  <th className="px-4 py-3">Plan</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {result.items.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      {row.user?.fullName || '—'}
                      <p className="text-xs text-charcoal-600/70">{row.user?.email}</p>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.plan?.name || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600 capitalize">{row.source}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.createdAt ? formatDate(row.createdAt) : '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <Link to={`/admin/circle/memberships/${row.id}`} className="text-xs font-semibold text-burgundy-600 hover:underline">
                        View &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No memberships match those filters" description="Try a different search term or clear your filters." />
        )
      )}

      {result?.meta && result.meta.total_pages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-4">
          <button type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60">
            Previous
          </button>
          <span className="text-sm text-charcoal-600">
            Page {result.meta.page} of {result.meta.total_pages}
          </span>
          <button
            type="button"
            disabled={page >= result.meta.total_pages}
            onClick={() => setPage((p) => Math.min(result.meta.total_pages, p + 1))}
            className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
