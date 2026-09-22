import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search } from 'lucide-react'
import { fetchOrganizations } from '../../api/taxonomies'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const TYPE_LABELS = {
  company: 'Company',
  nonprofit: 'Nonprofit',
  foundation: 'Foundation',
  government: 'Government',
  educational_institution: 'Educational institution',
  media_organization: 'Media organization',
  professional_association: 'Professional association',
  social_enterprise: 'Social enterprise',
  community_organization: 'Community organization',
  other: 'Other',
}

export default function AdminOrganizations() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchOrganizations({ status, query, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading organizations. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query])

  return (
    <div>
      <AdminPageHeader
        title="Organizations"
        description="Companies, foundations, and institutions in the Women Shaping Futures network."
        actions={
          <Link to="/admin/organizations/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New organization
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search organizations…" className="w-56 text-sm focus:outline-none" />
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

      {error && <EmptyState title="Couldn't load organizations" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">People</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      {row.name} {row.featured && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</span>}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{TYPE_LABELS[row.type] || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.country?.name || row.countryCode || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.peopleCount ?? 0}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/organizations/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/organizations/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
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
          <EmptyState title="No organizations match those filters yet" description="Create a new organization or broaden your search." />
        )
      )}
    </div>
  )
}
