import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, AlertTriangle } from 'lucide-react'
import { fetchAdminDirectorySubmissions } from '../../api/directory'
import { DIRECTORY_SUBMISSION_STATUSES, DIRECTORY_SUBMISSION_STATUS_LABELS } from '../../constants/directory'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminDirectorySubmissions() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)

  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchAdminDirectorySubmissions({ query: query || undefined, status: status || undefined, page, pageSize: 20 })
      .then((res) => {
        if (!active) return
        setRows(res.items)
        setPagination(res.pagination)
      })
      .catch((err) => {
        if (!active) return
        setError(
          err?.response?.status === 403
            ? "You don't have permission to view directory submissions."
            : 'Something went wrong loading submissions. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [query, status, page])

  return (
    <div>
      <AdminPageHeader title="Directory Submissions" description="Public business claims awaiting staff review — nothing here is published automatically." />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <label htmlFor="ds-search" className="sr-only">Search submissions</label>
          <input
            id="ds-search"
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search reference, business, submitter…"
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
          <option value="">All statuses</option>
          {DIRECTORY_SUBMISSION_STATUSES.map((s) => (
            <option key={s} value={s}>{DIRECTORY_SUBMISSION_STATUS_LABELS[s]}</option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load submissions" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">Business</th>
                  <th className="px-4 py-3">Submitter</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Received</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/directory/submissions/${row.id}`} className="hover:text-burgundy-600">
                        {row.reference || `#${row.id}`}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.businessName}
                      {row.possibleDuplicateOrganizationId && (
                        <span className="ml-2 inline-flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-amber-700">
                          <AlertTriangle size={11} /> Possible duplicate
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.submitterName}
                      <div className="text-xs text-charcoal-600/70">{row.submitterEmail}</div>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.country?.name || '—'}</td>
                    <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
                    <td className="px-4 py-3 text-charcoal-600">{row.createdAt ? formatDate(row.createdAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No submissions match those filters" description="Try a different search term or clear your filters." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
