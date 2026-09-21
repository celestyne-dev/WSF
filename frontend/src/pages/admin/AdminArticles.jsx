import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search } from 'lucide-react'
import { fetchAdminArticles } from '../../api/admin'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminArticles() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchAdminArticles({ status, query, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading articles. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query])

  return (
    <div>
      <AdminPageHeader
        title="Articles"
        description="Every story in the editorial pipeline, from draft to published."
        actions={
          <Link to="/admin/articles/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New article
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search articles…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {['draft', 'in_review', 'scheduled', 'published', 'archived'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load articles" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        <div className="overflow-x-auto border border-taupe-200 bg-white">
          <table className="w-full min-w-[700px] text-left text-sm">
            <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
              <tr>
                <th className="px-4 py-3">Title</th>
                <th className="px-4 py-3">Author</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-taupe-200">
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">{row.title}</td>
                  <td className="px-4 py-3 text-charcoal-600">{row.authorName}</td>
                  <td className="px-4 py-3">
                    <StatusBadge status={row.status} />
                  </td>
                  <td className="px-4 py-3 text-charcoal-600">{row.date ? formatDate(row.date, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      {row.slug && (
                        <a href={`/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                          <ExternalLink size={15} />
                        </a>
                      )}
                      <Link to={`/admin/articles/${row.slug || row.id}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                        <Pencil size={15} />
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
