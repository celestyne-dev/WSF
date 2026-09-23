import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil } from 'lucide-react'
import { fetchNewsletterIssues } from '../../api/newsletter'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const STATUSES = ['draft', 'scheduled', 'sent', 'archived']

export default function AdminNewsletterIssues() {
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchNewsletterIssues({ status, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading newsletter issues. Please try again.'))
    return () => {
      active = false
    }
  }, [status])

  return (
    <div>
      <AdminPageHeader
        title="Issues / Campaigns"
        description="Newsletter editions — draft, scheduled, sent, or archived."
        actions={
          <Link to="/admin/newsletter/issues/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New issue
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load newsletter issues" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Internal title</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Audience est.</th>
                  <th className="px-4 py-3">Scheduled</th>
                  <th className="px-4 py-3">Sent</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">{row.title}</td>
                    <td className="max-w-xs truncate px-4 py-3 text-charcoal-600">{row.subject}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.estimatedRecipients ?? '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.scheduledAt ? formatDate(row.scheduledAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.sentAt ? formatDate(row.sentAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <Link to={`/admin/newsletter/issues/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                        <Pencil size={15} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No newsletter issues yet" description="Create your first issue to get started." />
        )
      )}
    </div>
  )
}
