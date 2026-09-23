import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Download } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchSubscribers, exportSubscribers } from '../../api/newsletter'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const STATUSES = ['active', 'unsubscribed', 'bounced', 'complained']

export default function AdminSubscribers() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    let active = true
    setError(null)
    fetchSubscribers({ status, q: query, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading subscribers. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query])

  async function handleExport() {
    setExporting(true)
    try {
      await exportSubscribers({ status: status || undefined })
    } catch (err) {
      const message =
        err?.response?.status === 403
          ? "You don't have permission to export subscribers."
          : 'Something went wrong exporting subscribers. Please try again.'
      toast.error(message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Subscribers"
        description="Everyone who has subscribed to WSF Weekly, and their current status."
        actions={
          <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
            <Download size={14} /> {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search email or name…" className="w-64 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load subscribers" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Source</th>
                  <th className="px-4 py-3">Subscribed</th>
                  <th className="px-4 py-3">Unsubscribed</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/newsletter/subscribers/${row.id}`} className="hover:text-burgundy-600">
                        {row.email}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{[row.firstName, row.lastName].filter(Boolean).join(' ') || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.source || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.subscribedAt ? formatDate(row.subscribedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.unsubscribedAt ? formatDate(row.unsubscribedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No subscribers match those filters" description="Try a different search term or clear your filters." />
        )
      )}
    </div>
  )
}
