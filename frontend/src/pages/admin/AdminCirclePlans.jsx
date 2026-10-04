import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Star } from 'lucide-react'
import { fetchAdminCirclePlans } from '../../api/circle'
import { formatProductPrice } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const STATUSES = ['draft', 'active', 'archived']

export default function AdminCirclePlans() {
  const [status, setStatus] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchAdminCirclePlans({ status: status || undefined })
      .then((res) => {
        if (!active) return
        setRows(res)
        setError(null)
      })
      .catch(() => active && setError('Something went wrong loading WSF Circle plans. Please try again.'))
    return () => {
      active = false
    }
  }, [status])

  return (
    <div>
      <AdminPageHeader
        title="WSF Circle Plans"
        description="Premium membership tiers shown on the public /circle page."
        actions={
          <Link to="/admin/circle/plans/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New plan
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

      {error && <EmptyState title="Couldn't load plans" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[760px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Billing</th>
                  <th className="px-4 py-3">Price</th>
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
                    <td className="px-4 py-3 text-charcoal-600">{row.billingInterval}</td>
                    <td className="px-4 py-3 text-charcoal-600">{formatProductPrice(row.price, row.currency)}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'active' && (
                          <a href={`/circle`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/circle/plans/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
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
          <EmptyState title="No plans match those filters yet" description="Create a new plan to get started." />
        )
      )}
    </div>
  )
}
