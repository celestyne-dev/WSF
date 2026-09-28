import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Star, ShieldCheck } from 'lucide-react'
import { fetchAdminDirectoryListings } from '../../api/directory'
import {
  DIRECTORY_LISTING_STATUSES,
  DIRECTORY_LISTING_STATUS_LABELS,
  DIRECTORY_OWNERSHIP_LABELS,
  DIRECTORY_VERIFICATION_STATUSES,
  DIRECTORY_VERIFICATION_LABELS,
} from '../../constants/directory'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

export default function AdminDirectoryListings() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [verificationStatus, setVerificationStatus] = useState('')
  const [featured, setFeatured] = useState('')
  const [page, setPage] = useState(1)

  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchAdminDirectoryListings({
      query: query || undefined,
      status: status || undefined,
      verificationStatus: verificationStatus || undefined,
      featured: featured || undefined,
      page,
      pageSize: 20,
    })
      .then((res) => {
        if (!active) return
        setRows(res.items)
        setPagination(res.pagination)
      })
      .catch((err) => {
        if (!active) return
        setError(
          err?.response?.status === 403
            ? "You don't have permission to view the directory."
            : 'Something went wrong loading directory listings. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [query, status, verificationStatus, featured, page])

  return (
    <div>
      <AdminPageHeader title="Directory Listings" description="Business & Professional Directory — submissions become listings here once linked to an Organization." />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <label htmlFor="dl-search" className="sr-only">Search listings</label>
          <input
            id="dl-search"
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search organization name…"
            className="w-56 text-sm focus:outline-none"
          />
        </div>
        <select
          value={status}
          onChange={(e) => {
            setPage(1)
            setStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All statuses</option>
          {DIRECTORY_LISTING_STATUSES.map((s) => (
            <option key={s} value={s}>{DIRECTORY_LISTING_STATUS_LABELS[s]}</option>
          ))}
        </select>
        <select
          value={verificationStatus}
          onChange={(e) => {
            setPage(1)
            setVerificationStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All verification states</option>
          {DIRECTORY_VERIFICATION_STATUSES.map((s) => (
            <option key={s} value={s}>{DIRECTORY_VERIFICATION_LABELS[s]}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-charcoal-600">
          <input
            type="checkbox"
            checked={featured === 'true'}
            onChange={(e) => {
              setPage(1)
              setFeatured(e.target.checked ? 'true' : '')
            }}
          />
          Featured only
        </label>
      </div>

      {error && <EmptyState title="Couldn't load directory listings" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Organization</th>
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Classification</th>
                  <th className="px-4 py-3">Verification</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Promoted</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/directory/listings/${row.id}`} className="hover:text-burgundy-600">
                        {row.organization?.name || '—'}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.categories?.map((c) => c.name).join(', ') || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.organization?.country?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{DIRECTORY_OWNERSHIP_LABELS[row.ownershipClassification] || '—'}</td>
                    <td className="px-4 py-3">
                      <span className="inline-flex items-center gap-1 text-xs text-charcoal-600">
                        {row.verificationStatus === 'verified' && <ShieldCheck size={13} className="text-emerald-600" />}
                        {DIRECTORY_VERIFICATION_LABELS[row.verificationStatus] || row.verificationStatus}
                      </span>
                    </td>
                    <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
                    <td className="px-4 py-3">
                      {row.isCurrentlyFeatured ? <Star size={15} className="text-burgundy-600" fill="currentColor" /> : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No listings match those filters" description="Try a different search term or clear your filters." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
