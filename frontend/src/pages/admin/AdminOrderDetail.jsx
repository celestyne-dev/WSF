import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Archive, ArchiveRestore, Ban, MessageSquarePlus, Trash2 } from 'lucide-react'
import {
  fetchOrder,
  updateOrder,
  cancelOrder,
  archiveOrder,
  unarchiveOrder,
  addOrderNote,
  fetchOrderHistory,
  deleteOrder,
} from '../../api/orders'
import { ORDER_STATUSES, ORDER_STATUS_TERMINAL, PAYMENT_STATUSES, PAYMENT_STATUS_TERMINAL, FULFILLMENT_STATUSES } from '../../constants/orders'
import { formatDate, formatProductPrice } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import ConfirmDialog from '../../components/cms/ConfirmDialog'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const selectClass = 'w-full border border-taupe-300 bg-white px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'
const inputClass = 'w-full border border-taupe-300 px-3 py-2.5 text-sm focus:border-burgundy-500 focus:outline-none'

function Field({ label, hint, children }) {
  return (
    <div>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
        {label} {hint && <span className="normal-case text-charcoal-600/60">— {hint}</span>}
      </label>
      <div className="mt-1.5">{children}</div>
    </div>
  )
}

function AddressBlock({ title, address }) {
  if (!address) return null
  const line = [address.line1, address.line2].filter(Boolean).join(', ')
  const cityLine = [address.city, address.region, address.postalCode].filter(Boolean).join(', ')
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{title}</p>
      <p className="mt-1 text-sm text-charcoal-600">
        {line && <>{line}<br /></>}
        {cityLine && <>{cityLine}<br /></>}
        {address.countryCode}
      </p>
    </div>
  )
}

export default function AdminOrderDetail() {
  const { uuid } = useParams()

  const [order, setOrder] = useState(undefined)
  const [history, setHistory] = useState(null)
  const [notFound, setNotFound] = useState(false)
  const [loadError, setLoadError] = useState(null)

  const [orderStatusValue, setOrderStatusValue] = useState('')
  const [savingOrderStatus, setSavingOrderStatus] = useState(false)

  const [paymentForm, setPaymentForm] = useState(null)
  const [savingPayment, setSavingPayment] = useState(false)

  const [fulfillmentValue, setFulfillmentValue] = useState('')
  const [savingFulfillment, setSavingFulfillment] = useState(false)

  const [noteBody, setNoteBody] = useState('')
  const [savingNote, setSavingNote] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [actionPending, setActionPending] = useState(false)

  function load() {
    let active = true
    Promise.all([fetchOrder(uuid), fetchOrderHistory(uuid)])
      .then(([o, historyEntries]) => {
        if (!active) return
        setOrder(o)
        setOrderStatusValue(o.orderStatus)
        setPaymentForm({
          paymentStatus: o.paymentStatus,
          paymentProvider: o.paymentProvider,
          paymentReference: o.paymentReference,
          refundAmount: o.refundAmount ?? '',
          refundReason: o.refundReason,
        })
        setFulfillmentValue(o.fulfillmentStatus)
        setHistory(historyEntries)
      })
      .catch((err) => {
        if (!active) return
        if (err?.response?.status === 404) setNotFound(true)
        else setLoadError(err?.apiError?.message || 'Something went wrong loading this order. Please try again.')
      })
    return () => {
      active = false
    }
  }

  useEffect(load, [uuid])

  async function refreshHistory() {
    try {
      setHistory(await fetchOrderHistory(uuid))
    } catch {
      // history is supplementary — a failed refresh shouldn't block the page
    }
  }

  async function handleOrderStatusSubmit() {
    if (orderStatusValue === order.orderStatus) return
    setSavingOrderStatus(true)
    try {
      const updated = await updateOrder(uuid, { orderStatus: orderStatusValue })
      setOrder(updated)
      toast.success('Order status updated.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating the order status.')
      setOrderStatusValue(order.orderStatus)
    } finally {
      setSavingOrderStatus(false)
    }
  }

  async function handlePaymentSubmit() {
    setSavingPayment(true)
    try {
      const updated = await updateOrder(uuid, paymentForm)
      setOrder(updated)
      setPaymentForm({
        paymentStatus: updated.paymentStatus,
        paymentProvider: updated.paymentProvider,
        paymentReference: updated.paymentReference,
        refundAmount: updated.refundAmount ?? '',
        refundReason: updated.refundReason,
      })
      toast.success('Payment details updated.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating payment details.')
    } finally {
      setSavingPayment(false)
    }
  }

  async function handleFulfillmentSubmit() {
    if (fulfillmentValue === order.fulfillmentStatus) return
    setSavingFulfillment(true)
    try {
      const updated = await updateOrder(uuid, { fulfillmentStatus: fulfillmentValue })
      setOrder(updated)
      toast.success('Fulfillment status updated.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong updating fulfillment status.')
      setFulfillmentValue(order.fulfillmentStatus)
    } finally {
      setSavingFulfillment(false)
    }
  }

  async function handleAddNote() {
    if (!noteBody.trim()) return
    setSavingNote(true)
    try {
      const updated = await addOrderNote(uuid, noteBody.trim())
      setOrder(updated)
      setNoteBody('')
      toast.success('Note added.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong adding this note.')
    } finally {
      setSavingNote(false)
    }
  }

  async function handleCancel() {
    setActionPending(true)
    try {
      const updated = await cancelOrder(uuid)
      setOrder(updated)
      setOrderStatusValue(updated.orderStatus)
      toast.success('Order cancelled.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong cancelling this order.')
    } finally {
      setActionPending(false)
      setConfirmAction(null)
    }
  }

  async function handleArchiveToggle() {
    setActionPending(true)
    try {
      const updated = order.archived ? await unarchiveOrder(uuid) : await archiveOrder(uuid)
      setOrder(updated)
      toast.success(updated.archived ? 'Order archived.' : 'Order unarchived.')
      refreshHistory()
    } catch (err) {
      toast.error(err?.apiError?.message || 'Something went wrong archiving this order.')
    } finally {
      setActionPending(false)
    }
  }

  async function handleDelete() {
    setActionPending(true)
    try {
      await deleteOrder(uuid)
      toast.success('Order deleted.')
      window.location.href = '/admin/orders'
    } catch (err) {
      toast.error(err?.apiError?.message || "This order can't be deleted — it may already carry payment or fulfillment history.")
      setActionPending(false)
      setConfirmAction(null)
    }
  }

  if (loadError) return <EmptyState title="Couldn't load this order" description={loadError} />
  if (notFound) return <EmptyState title="Order not found" description="This order may have been removed or the URL is incorrect." />
  if (order === undefined || paymentForm === null) return <PageLoader />

  const orderTerminal = ORDER_STATUS_TERMINAL.includes(order.orderStatus)
  const paymentTerminal = PAYMENT_STATUS_TERMINAL.includes(order.paymentStatus)
  const canCancel = !ORDER_STATUS_TERMINAL.includes(order.orderStatus)
  const canDelete = ['unpaid', 'pending', 'failed'].includes(order.paymentStatus) && ['pending', 'cancelled'].includes(order.orderStatus)

  return (
    <div>
      <AdminPageHeader
        title={order.reference || `Order #${order.id}`}
        description={`Placed ${order.createdAt ? formatDate(order.createdAt, { month: 'long', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : '—'}`}
        actions={
          <>
            <StatusBadge status={order.orderStatus} />
            <StatusBadge status={order.paymentStatus} />
            <StatusBadge status={order.fulfillmentStatus} />
          </>
        }
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {/* Customer */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Customer</p>
            <dl className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-xs text-charcoal-600/60">Name</dt>
                <dd className="text-charcoal">{order.customerName || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-charcoal-600/60">Email</dt>
                <dd className="text-charcoal">{order.email}</dd>
              </div>
              <div>
                <dt className="text-xs text-charcoal-600/60">Phone</dt>
                <dd className="text-charcoal">{order.phone || '—'}</dd>
              </div>
              <div>
                <dt className="text-xs text-charcoal-600/60">Account</dt>
                <dd className="text-charcoal">{order.userId ? `User #${order.userId}` : 'Guest checkout'}</dd>
              </div>
            </dl>
            {(order.billingAddress || order.shippingAddress) && (
              <div className="mt-4 grid grid-cols-1 gap-4 border-t border-taupe-200 pt-4 sm:grid-cols-2">
                <AddressBlock title="Billing address" address={order.billingAddress} />
                <AddressBlock title="Shipping address" address={order.shippingAddress} />
              </div>
            )}
          </div>

          {/* Items — immutable snapshot, never editable here */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Items</p>
            <p className="mb-3 text-xs text-charcoal-600/60">
              Snapshotted at purchase time — fixed even if the product's current name, price, or status changes later.
            </p>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">
                  <tr>
                    <th className="py-2 pr-3">Product</th>
                    <th className="py-2 pr-3">SKU</th>
                    <th className="py-2 pr-3">Qty</th>
                    <th className="py-2 pr-3">Unit price</th>
                    <th className="py-2 pr-3">Line total</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-taupe-200">
                  {order.items.map((item) => (
                    <tr key={item.id}>
                      <td className="py-2 pr-3 text-charcoal">
                        {item.product ? (
                          <Link to={`/admin/products/${item.product.id}`} className="hover:text-burgundy-600">
                            {item.productName}
                          </Link>
                        ) : (
                          item.productName
                        )}
                      </td>
                      <td className="py-2 pr-3 text-charcoal-600">{item.productSku || '—'}</td>
                      <td className="py-2 pr-3 text-charcoal-600">{item.quantity}</td>
                      <td className="py-2 pr-3 text-charcoal-600">{formatProductPrice(item.unitPrice, item.currency)}</td>
                      <td className="py-2 pr-3 text-charcoal-600">{formatProductPrice(item.lineTotal, item.currency)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-4 ml-auto w-full max-w-xs space-y-1 text-sm">
              <div className="flex justify-between text-charcoal-600">
                <span>Subtotal</span>
                <span>{formatProductPrice(order.subtotalAmount, order.currency)}</span>
              </div>
              {order.discountAmount > 0 && (
                <div className="flex justify-between text-charcoal-600">
                  <span>Discount</span>
                  <span>-{formatProductPrice(order.discountAmount, order.currency)}</span>
                </div>
              )}
              {order.taxAmount > 0 && (
                <div className="flex justify-between text-charcoal-600">
                  <span>Tax</span>
                  <span>{formatProductPrice(order.taxAmount, order.currency)}</span>
                </div>
              )}
              {order.shippingAmount > 0 && (
                <div className="flex justify-between text-charcoal-600">
                  <span>Shipping</span>
                  <span>{formatProductPrice(order.shippingAmount, order.currency)}</span>
                </div>
              )}
              <div className="flex justify-between border-t border-taupe-200 pt-1 font-semibold text-charcoal">
                <span>Total</span>
                <span>{formatProductPrice(order.totalAmount, order.currency)}</span>
              </div>
            </div>
          </div>

          {/* Payment & refund */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Payment &amp; refund</p>
            <p className="mb-3 text-xs text-charcoal-600/60">
              Administrative records only — no payment gateway is connected; these fields are entered by staff.
            </p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Payment status">
                <select
                  value={paymentForm.paymentStatus}
                  onChange={(e) => setPaymentForm({ ...paymentForm, paymentStatus: e.target.value })}
                  className={selectClass}
                >
                  {PAYMENT_STATUSES.map((s) => (
                    <option key={s} value={s} disabled={paymentTerminal && ['unpaid', 'pending'].includes(s) && s !== order.paymentStatus}>
                      {s.replace(/_/g, ' ')}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Payment provider" hint="optional">
                <input
                  value={paymentForm.paymentProvider || ''}
                  onChange={(e) => setPaymentForm({ ...paymentForm, paymentProvider: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Payment reference" hint="optional">
                <input
                  value={paymentForm.paymentReference || ''}
                  onChange={(e) => setPaymentForm({ ...paymentForm, paymentReference: e.target.value })}
                  className={inputClass}
                />
              </Field>
              <Field label="Refund amount" hint="optional — whole currency units">
                <input
                  type="number"
                  min="0"
                  value={paymentForm.refundAmount}
                  onChange={(e) => setPaymentForm({ ...paymentForm, refundAmount: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>
            <div className="mt-4">
              <Field label="Refund reason" hint="optional">
                <textarea
                  rows={2}
                  value={paymentForm.refundReason || ''}
                  onChange={(e) => setPaymentForm({ ...paymentForm, refundReason: e.target.value })}
                  className={inputClass}
                />
              </Field>
            </div>
            {order.paidAt && <p className="mt-3 text-xs text-charcoal-600/60">Paid at {formatDate(order.paidAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}</p>}
            {order.refundedAt && <p className="mt-1 text-xs text-charcoal-600/60">Refunded at {formatDate(order.refundedAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })}</p>}
            <button type="button" onClick={handlePaymentSubmit} disabled={savingPayment} className="btn-secondary mt-4 !px-4 !py-2 text-xs disabled:opacity-60">
              {savingPayment ? 'Saving…' : 'Save payment details'}
            </button>
          </div>

          {/* Internal notes */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Internal notes</p>
            <p className="mb-3 text-xs text-charcoal-600/60">Staff-only — never visible to the customer.</p>
            <div className="flex gap-2">
              <textarea
                rows={2}
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                placeholder="e.g. Customer requested address change by email…"
                className={`${inputClass} flex-1`}
              />
              <button type="button" onClick={handleAddNote} disabled={savingNote || !noteBody.trim()} className="btn-secondary self-start !px-3 !py-2.5 text-xs disabled:opacity-60">
                <MessageSquarePlus size={14} /> {savingNote ? 'Adding…' : 'Add'}
              </button>
            </div>
            <div className="mt-4 space-y-3">
              {order.notes.length === 0 && <p className="text-sm text-charcoal-600/60">No internal notes yet.</p>}
              {order.notes.map((note) => (
                <div key={note.id} className="border-l-2 border-taupe-300 pl-3">
                  <p className="text-sm text-charcoal">{note.body}</p>
                  <p className="mt-1 text-xs text-charcoal-600/60">
                    {note.user?.name || 'Unknown'} &middot; {note.createdAt ? formatDate(note.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Activity / history */}
          <div className="border border-taupe-200 bg-white p-6">
            <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Activity</p>
            {history === null && <p className="text-sm text-charcoal-600/60">Loading…</p>}
            {history !== null && history.length === 0 && <p className="text-sm text-charcoal-600/60">No activity recorded yet.</p>}
            {history !== null && history.length > 0 && (
              <ul className="space-y-2 text-sm">
                {history.map((entry) => (
                  <li key={entry.id} className="text-charcoal-600">
                    <span className="font-medium text-charcoal">{entry.action.replace('order.', '').replace(/_/g, ' ')}</span>
                    {entry.user && <> by {entry.user}</>}
                    <span className="text-charcoal-600/60"> &middot; {entry.createdAt ? formatDate(entry.createdAt, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' }) : ''}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        <div className="space-y-4">
          {/* Order status */}
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Order status</p>
            <select value={orderStatusValue} onChange={(e) => setOrderStatusValue(e.target.value)} className={`${selectClass} mt-2`}>
              {ORDER_STATUSES.map((s) => (
                <option key={s} value={s} disabled={orderTerminal && ['pending', 'confirmed', 'processing'].includes(s) && s !== order.orderStatus}>
                  {s.replace(/_/g, ' ')}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleOrderStatusSubmit}
              disabled={savingOrderStatus || orderStatusValue === order.orderStatus}
              className="btn-secondary mt-2 w-full !py-2 text-xs disabled:opacity-60"
            >
              {savingOrderStatus ? 'Updating…' : 'Update order status'}
            </button>
          </div>

          {/* Fulfillment status */}
          <div className="border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Fulfillment status</p>
            {!order.requiresShipping && <p className="mt-1 text-xs text-charcoal-600/60">Digital-only order.</p>}
            <select value={fulfillmentValue} onChange={(e) => setFulfillmentValue(e.target.value)} className={`${selectClass} mt-2`}>
              {FULFILLMENT_STATUSES.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={handleFulfillmentSubmit}
              disabled={savingFulfillment || fulfillmentValue === order.fulfillmentStatus}
              className="btn-secondary mt-2 w-full !py-2 text-xs disabled:opacity-60"
            >
              {savingFulfillment ? 'Updating…' : 'Update fulfillment status'}
            </button>
          </div>

          {/* Actions */}
          <div className="space-y-2 border border-taupe-200 bg-white p-5">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Actions</p>
            <button
              type="button"
              onClick={() => setConfirmAction('cancel')}
              disabled={!canCancel || actionPending}
              className="btn-secondary w-full !py-2 text-xs disabled:opacity-40"
            >
              <Ban size={13} /> Cancel order
            </button>
            <button type="button" onClick={handleArchiveToggle} disabled={actionPending} className="btn-secondary w-full !py-2 text-xs disabled:opacity-60">
              {order.archived ? <ArchiveRestore size={13} /> : <Archive size={13} />} {order.archived ? 'Unarchive' : 'Archive'}
            </button>
            {canDelete && (
              <button
                type="button"
                onClick={() => setConfirmAction('delete')}
                disabled={actionPending}
                className="w-full !px-4 !py-2 text-xs font-semibold text-rose-600 hover:bg-rose-50 disabled:opacity-60"
              >
                <Trash2 size={13} /> Delete order
              </button>
            )}
          </div>

          <div className="border border-taupe-200 bg-white p-5">
            <dl className="space-y-2 text-xs text-charcoal-600">
              <div className="flex justify-between">
                <dt>Created</dt>
                <dd>{order.createdAt ? formatDate(order.createdAt) : '—'}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Last updated</dt>
                <dd>{order.updatedAt ? formatDate(order.updatedAt) : '—'}</dd>
              </div>
            </dl>
          </div>

          <Link to="/admin/orders" className="block text-center text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
            &larr; Back to all orders
          </Link>
        </div>
      </div>

      {confirmAction === 'cancel' && (
        <ConfirmDialog
          title="Cancel this order?"
          description="This moves the order to cancelled and is recorded in its activity history. Already-recorded payment/fulfillment history is preserved."
          confirmLabel="Cancel order"
          danger
          onConfirm={handleCancel}
          onCancel={() => setConfirmAction(null)}
        />
      )}
      {confirmAction === 'delete' && (
        <ConfirmDialog
          title="Delete this order?"
          description="This permanently removes the order record. Only possible because it has no payment or fulfillment history yet — archive instead to keep a record."
          confirmLabel="Delete order"
          danger
          onConfirm={handleDelete}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  )
}
