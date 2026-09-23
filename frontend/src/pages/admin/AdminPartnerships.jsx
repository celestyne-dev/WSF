import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Download } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchPartnerships, exportPartnerships } from '../../api/partnerships'
import { fetchAdminUsers } from '../../api/admin'
import { formatDate } from '../../utils/format'
import { PARTNERSHIP_TYPES, PARTNERSHIP_STATUSES } from '../../constants/partnerships'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminPartnerships() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [assignedToId, setAssignedToId] = useState('')
  const [users, setUsers] = useState([])
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    fetchAdminUsers().then(setUsers).catch(() => {})
  }, [])

  useEffect(() => {
    let active = true
    setError(null)
    fetchPartnerships({ status, partnershipType: type, assignedToId, q: query, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading partnerships. Please try again.'))
    return () => {
      active = false
    }
  }, [status, type, assignedToId, query])

  async function handleExport() {
    setExporting(true)
    try {
      await exportPartnerships({ status: status || undefined, partnershipType: type || undefined, assignedToId: assignedToId || undefined, q: query || undefined })
    } catch (err) {
      const message =
        err?.response?.status === 403
          ? "You don't have permission to export partnerships."
          : 'Something went wrong exporting partnerships. Please try again.'
      toast.error(message)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Partnerships"
        description="Inbound partnership inquiries, from first contact through to active partnerships."
        actions={
          <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
            <Download size={14} /> {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search organization, contact, email, subject…"
            className="w-72 text-sm focus:outline-none"
          />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {PARTNERSHIP_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s.replace(/_/g, ' ')}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          {PARTNERSHIP_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={assignedToId} onChange={(e) => setAssignedToId(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All owners</option>
          {users.map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load partnerships" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Organization</th>
                  <th className="px-4 py-3">Contact</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Owner</th>
                  <th className="px-4 py-3">Submitted</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/partnerships/${row.id}`} className="hover:text-burgundy-600">
                        {row.company}
                      </Link>
                      {row.subject && <div className="mt-0.5 truncate text-xs font-normal text-charcoal-600/70">{row.subject}</div>}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      <div>{row.contactName}</div>
                      <div className="text-xs text-charcoal-600/70">{row.email}</div>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.partnershipType || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.assignedTo?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.submittedAt ? formatDate(row.submittedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No partnerships match those filters" description="Try a different search term or clear your filters." />
        )
      )}
    </div>
  )
}
