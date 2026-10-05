import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search, Download } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchOrders, exportOrders } from '../../api/orders'
import { ORDER_STATUSES, PAYMENT_STATUSES, FULFILLMENT_STATUSES } from '../../constants/orders'
import { formatDate, formatProductPrice } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

// Filters here are exactly what GET /orders accepts today (see
// app/api/v1/orders.py:_build_order_query/_apply_equality_status_filters):
// order/payment/fulfillment status equality, a free-text query across
// reference/email/customer_name, and the archived toggle. No product or
// customer-name-specific filter is exposed — see the final report.
export default function AdminOrders() {
  const [query, setQuery] = useState('')
  const [orderStatus, setOrderStatus] = useState('')
  const [paymentStatus, setPaymentStatus] = useState('')
  const [fulfillmentStatus, setFulfillmentStatus] = useState('')
  const [archived, setArchived] = useState(false)
  const [page, setPage] = useState(1)

  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)

  function load() {
    let active = true
    fetchOrders({
      query: query || undefined,
      orderStatus: orderStatus || undefined,
      paymentStatus: paymentStatus || undefined,
      fulfillmentStatus: fulfillmentStatus || undefined,
      archived: archived ? 'true' : undefined,
      page,
      pageSize: 20,
    })
      .then((res) => {
        if (!active) return
        setRows(res.items)
        setPagination(res.pagination)
        setError(null)
      })
      .catch((err) => {
        if (!active) return
        setError(err?.apiError?.message || 'Something went wrong loading orders. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [query, orderStatus, paymentStatus, fulfillmentStatus, archived, page])

  async function handleExport() {
    setExporting(true)
    try {
      await exportOrders({
        query: query || undefined,
        orderStatus: orderStatus || undefined,
        paymentStatus: paymentStatus || undefined,
        fulfillmentStatus: fulfillmentStatus || undefined,
        archived: archived ? 'true' : undefined,
      })
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong exporting orders. Please try again.')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Orders"
        description="Administrative records of Shop purchases — statuses, fulfillment, and internal notes."
        actions={
          <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
            <Download size={14} /> {exporting ? 'Exporting…' : 'Export CSV'}
          </button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <label htmlFor="orders-search" className="sr-only">Search orders</label>
          <input
            id="orders-search"
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search reference, email, customer name…"
            className="w-64 text-sm focus:outline-none"
          />
        </div>
        <select
          value={orderStatus}
          onChange={(e) => {
            setPage(1)
            setOrderStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All order statuses</option>
          {ORDER_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select
          value={paymentStatus}
          onChange={(e) => {
            setPage(1)
            setPaymentStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All payment statuses</option>
          {PAYMENT_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <select
          value={fulfillmentStatus}
          onChange={(e) => {
            setPage(1)
            setFulfillmentStatus(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          <option value="">All fulfillment statuses</option>
          {FULFILLMENT_STATUSES.map((s) => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-charcoal-600">
          <input
            type="checkbox"
            checked={archived}
            onChange={(e) => {
              setPage(1)
              setArchived(e.target.checked)
            }}
          />
          Archived only
        </label>
      </div>

      {error && <EmptyState title="Couldn't load orders" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Reference</th>
                  <th className="px-4 py-3">Customer</th>
                  <th className="px-4 py-3">Items</th>
                  <th className="px-4 py-3">Total</th>
                  <th className="px-4 py-3">Order</th>
                  <th className="px-4 py-3">Payment</th>
                  <th className="px-4 py-3">Fulfillment</th>
                  <th className="px-4 py-3">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/orders/${row.uuid}`} className="hover:text-burgundy-600">
                        {row.reference || `#${row.id}`}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      <div>{row.customerName || '—'}</div>
                      <div className="text-xs text-charcoal-600/70">{row.email}</div>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.items.length}</td>
                    <td className="px-4 py-3 text-charcoal-600">{formatProductPrice(row.totalAmount, row.currency)}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.orderStatus} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.paymentStatus} />
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.fulfillmentStatus} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.createdAt ? formatDate(row.createdAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No orders match those filters" description="Try a different search term or clear your filters." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
