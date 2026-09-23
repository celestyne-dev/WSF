import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Plus } from 'lucide-react'
import { fetchSponsors } from '../../api/sponsors'
import { formatDate } from '../../utils/format'
import { SPONSORSHIP_TYPES, SPONSOR_STATUSES, SPONSOR_PLACEMENT_KEYS, SPONSOR_PLACEMENT_LABELS } from '../../constants/sponsors'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminSponsors() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [placement, setPlacement] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchSponsors({ status, sponsorshipType: type, placement, q: query, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading sponsors. Please try again.'))
    return () => {
      active = false
    }
  }, [status, type, placement, query])

  return (
    <div>
      <AdminPageHeader
        title="Sponsors"
        description="Sponsorship campaigns, from draft through to active, disclosed public placements."
        actions={
          <Link to="/admin/sponsors/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New sponsor
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search campaign, organization…" className="w-64 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {SPONSOR_STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          {SPONSORSHIP_TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={placement} onChange={(e) => setPlacement(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All placements</option>
          {SPONSOR_PLACEMENT_KEYS.map((p) => (
            <option key={p} value={p}>
              {SPONSOR_PLACEMENT_LABELS[p]}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load sponsors" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Campaign</th>
                  <th className="px-4 py-3">Organization</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Placements</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Start</th>
                  <th className="px-4 py-3">End</th>
                  <th className="px-4 py-3">Public</th>
                  <th className="px-4 py-3">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/sponsors/${row.id}`} className="hover:text-burgundy-600">
                        {row.campaignName}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.organization?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.sponsorshipType || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.placements.length ? row.placements.map((p) => SPONSOR_PLACEMENT_LABELS[p.placementKey] || p.placementKey).join(', ') : '—'}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.startsAt ? formatDate(row.startsAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.endsAt ? formatDate(row.endsAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.publicVisible ? 'Visible' : 'Hidden'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No sponsors match those filters" description="Try a different search term, or create a new sponsor campaign." />
        )
      )}
    </div>
  )
}
