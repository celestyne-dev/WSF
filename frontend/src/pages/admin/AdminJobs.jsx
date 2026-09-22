import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search } from 'lucide-react'
import { fetchJobs } from '../../api/jobs'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminJobs() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [workMode, setWorkMode] = useState('')
  const [featuredOnly, setFeaturedOnly] = useState(false)
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchJobs({ status, query, workMode, featured: featuredOnly || undefined, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading jobs. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query, workMode, featuredOnly])

  return (
    <div>
      <AdminPageHeader
        title="Jobs"
        description="Job listings from employers across the Women Shaping Futures network."
        actions={
          <Link to="/admin/jobs/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New job
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search jobs…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {['draft', 'review', 'scheduled', 'published', 'expired', 'archived'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={workMode} onChange={(e) => setWorkMode(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All work modes</option>
          {['On-site', 'Hybrid', 'Remote'].map((w) => (
            <option key={w} value={w}>
              {w}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-charcoal-600">
          <input type="checkbox" checked={featuredOnly} onChange={(e) => setFeaturedOnly(e.target.checked)} />
          Featured only
        </label>
      </div>

      {error && <EmptyState title="Couldn't load jobs" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[800px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Organization</th>
                  <th className="px-4 py-3">Location</th>
                  <th className="px-4 py-3">Work mode</th>
                  <th className="px-4 py-3">Deadline</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      {row.title}
                      {row.featured && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</span>}
                      {row.sponsored && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-charcoal-600/60">Sponsored</span>}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.company}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.location || row.country?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.workMode || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.deadline ? formatDate(row.deadline, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.isClosed && row.status === 'published' ? 'closed' : row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/jobs/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/jobs/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
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
          <EmptyState title="No jobs match those filters yet" description="Create a new job or broaden your search." />
        )
      )}
    </div>
  )
}
