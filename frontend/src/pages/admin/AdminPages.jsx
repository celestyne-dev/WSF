import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchPagesAdmin, deletePage } from '../../api/pages'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminPages() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [pageType, setPageType] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  function load() {
    setError(null)
    fetchPagesAdmin({ status, page_type: pageType, q: query, per_page: 100 })
      .then((res) => setRows(res.items))
      .catch(() => setError('Something went wrong loading pages. Please try again.'))
  }

  useEffect(load, [status, pageType, query])

  async function handleDelete(row) {
    if (!window.confirm(`Delete "${row.title}"? This can't be undone.`)) return
    try {
      await deletePage(row.id)
      toast.success('Page deleted.')
      load()
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || "This page can't be deleted right now.")
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Pages"
        description="Core static and legal pages — About, Contact, Privacy, Terms, Cookies, Editorial Policy — plus any general informational pages."
        actions={
          <Link to="/admin/pages/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New page
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search title or route…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={pageType} onChange={(e) => setPageType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          <option value="system">System</option>
          <option value="general">General</option>
        </select>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {['draft', 'published', 'archived'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load pages" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Page</th>
                  <th className="px-4 py-3">Route</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Last updated</th>
                  <th className="px-4 py-3">Last reviewed</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      {row.isSystem && <ShieldCheck size={13} className="mr-1 inline text-burgundy-600" aria-label="System page" />}
                      {row.title}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">/{row.slug}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.isSystem ? 'System' : 'General'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.lastReviewedAt ? formatDate(row.lastReviewedAt) : '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/pages/${row.id}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
                          <Pencil size={15} />
                        </Link>
                        {!row.isSystem && (
                          <button type="button" onClick={() => handleDelete(row)} aria-label="Delete" className="text-charcoal-600 hover:text-rose-600">
                            ×
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No pages match those filters yet" description="Create a new page or broaden your search." />
        )
      )}
    </div>
  )
}
