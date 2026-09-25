import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search } from 'lucide-react'
import { fetchTopicsAdmin } from '../../api/taxonomies'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminTopics() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchTopicsAdmin({ status, q: query, per_page: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading topics. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query])

  return (
    <div>
      <AdminPageHeader
        title="Topics"
        description="Editorial topics used across Articles, People, Resources, and more."
        actions={
          <Link to="/admin/taxonomy/topics/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New topic
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search topics…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {['draft', 'published', 'archived'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load topics" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Order</th>
                  <th className="px-4 py-3">Usage</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">{row.name}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.sortOrder}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.usageCount ?? 0}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/topics/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/taxonomy/topics/${row.id}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                          <Pencil size={15} />
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No topics match those filters yet" description="Create a new topic or broaden your search." />
        )
      )}
    </div>
  )
}
