import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchContactInquiries } from '../../api/contact'
import { CONTACT_STATUSES, CONTACT_STATUS_LABELS, CONTACT_INQUIRY_TYPES, CONTACT_INQUIRY_TYPE_LABELS } from '../../constants/contact'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

export default function AdminContactInquiries() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [inquiryType, setInquiryType] = useState('')
  const [page, setPage] = useState(1)

  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchContactInquiries({
      query: query || undefined,
      status: status || undefined,
      inquiryType: inquiryType || undefined,
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
            ? "You don't have permission to view contact inquiries."
            : 'Something went wrong loading inquiries. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [query, status, inquiryType, page])

  return (
    <div>
      <AdminPageHeader title="Contact Inquiries" description="General inquiries submitted through the public Contact form." />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <label htmlFor="ci-search" className="sr-only">Search inquiries</label>
          <input
            id="ci-search"
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search reference, name, email, subject…"
            className="w-64 text-sm focus:outline-none"
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
          {CONTACT_STATUSES.map((s) => (
            <option key={s} value={s}>{CONTACT_STATUS_LABELS[s]}</option>
          ))}
        </select>
        <select
          value={inquiryType}
          onChange={(e) => {
            setPage(1)
            setInquiryType(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All inquiry types</option>
          {CONTACT_INQUIRY_TYPES.map((t) => (
            <option key={t} value={t}>{CONTACT_INQUIRY_TYPE_LABELS[t]}</option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load inquiries" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">From</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Subject</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Assigned</th>
                  <th className="px-4 py-3">Received</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/contact/${row.id}`} className="hover:text-burgundy-600">
                        {row.reference || `#${row.id}`}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      <Link to={`/admin/contact/${row.id}`} className="hover:text-burgundy-600">{row.fullName}</Link>
                      <div className="text-xs text-charcoal-600/70">{row.email}</div>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{CONTACT_INQUIRY_TYPE_LABELS[row.inquiryType] || row.inquiryType}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.subject}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.assignedTo?.fullName || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.createdAt ? formatDate(row.createdAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No inquiries match those filters" description="Try a different search term or clear your filters." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
