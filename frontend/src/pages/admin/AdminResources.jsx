import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search, Star } from 'lucide-react'
import { fetchResources } from '../../api/resources'
import { formatProductPrice } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const RESOURCE_TYPES = [
  'Guide', 'Workbook', 'Template', 'Checklist', 'Planner', 'Toolkit',
  'Ebook', 'Worksheet', 'Report', 'Download', 'Video Resource', 'External Resource',
]
const STATUSES = ['draft', 'review', 'scheduled', 'published', 'archived']
const ACCESS_LABELS = {
  direct_download: 'Direct download',
  email_gate: 'Email-gated',
  member_only: 'Member only',
  premium: 'Premium',
  external_link: 'External link',
}

export default function AdminResources() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchResources({ status, q: query, type, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading resources. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query, type])

  return (
    <div>
      <AdminPageHeader
        title="Resources"
        description="Free downloadable guides, templates, and premium resources for the Resources library."
        actions={
          <Link to="/admin/resources/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New resource
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search resources…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          {RESOURCE_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load resources" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[920px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Access</th>
                  <th className="px-4 py-3">Price</th>
                  <th className="px-4 py-3">Downloads</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      {row.name}
                      {row.featured && (
                        <span className="ml-1.5 inline-flex items-center gap-0.5 text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">
                          <Star size={10} /> Featured
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.type || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{ACCESS_LABELS[row.accessType] || row.accessType}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.isFree ? 'Free' : formatProductPrice(row.price, row.currency)}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.downloadCount}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/resources/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/resources/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
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
          <EmptyState title="No resources match those filters yet" description="Create a new resource or broaden your search." />
        )
      )}
    </div>
  )
}
