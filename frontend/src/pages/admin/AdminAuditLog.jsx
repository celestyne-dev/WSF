import { useEffect, useState } from 'react'
import { Search, X } from 'lucide-react'
import { fetchAuditLog } from '../../api/audit'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const CATEGORIES = [
  { key: '', label: 'All categories' },
  { key: 'content', label: 'Content' },
  { key: 'access', label: 'Access' },
  { key: 'site', label: 'Site' },
  { key: 'commercial', label: 'Commercial' },
  { key: 'community', label: 'Community' },
  { key: 'newsletter', label: 'Newsletter' },
  { key: 'system', label: 'System' },
]

const CATEGORY_LABELS = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label]))

const QUICK_RANGES = [
  { key: 'today', label: 'Today', days: 0 },
  { key: '7', label: 'Last 7 days', days: 6 },
  { key: '30', label: 'Last 30 days', days: 29 },
]

function isoDate(d) {
  return d.toISOString().slice(0, 10)
}

function quickRangeDates(days) {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - days)
  return { dateFrom: isoDate(start), dateTo: isoDate(end) }
}

function timestampLabel(iso) {
  return formatDate(iso, { month: 'short', day: 'numeric', year: 'numeric', hour: 'numeric', minute: '2-digit' })
}

function DetailDrawer({ entry, onClose }) {
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  const metadataEntries = entry.metadata && typeof entry.metadata === 'object' ? Object.entries(entry.metadata) : []

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-charcoal/50" role="dialog" aria-modal="true" aria-label="Audit event detail">
      <div className="h-full w-full max-w-md overflow-y-auto bg-ivory p-6 shadow-card">
        <div className="flex items-center justify-between">
          <h3 className="font-serif text-lg font-semibold text-charcoal">Event detail</h3>
          <button type="button" onClick={onClose} aria-label="Close" className="text-charcoal-600 hover:text-burgundy-600">
            <X size={18} />
          </button>
        </div>

        <dl className="mt-5 space-y-4 text-sm">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Timestamp</dt>
            <dd className="mt-1 text-charcoal">{timestampLabel(entry.createdAt)}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Actor</dt>
            <dd className="mt-1 text-charcoal">
              {entry.actor?.name || 'System'}
              {entry.actor?.email && <span className="text-charcoal-600"> — {entry.actor.email}</span>}
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Action</dt>
            <dd className="mt-1 text-charcoal">
              {entry.actionLabel}
              <span className="ml-2 text-xs text-charcoal-600/60">({entry.action})</span>
            </dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Category</dt>
            <dd className="mt-1 text-charcoal">{CATEGORY_LABELS[entry.category] || entry.category}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Entity</dt>
            <dd className="mt-1 text-charcoal">
              {entry.entity.label}
              <div className="text-xs text-charcoal-600/70">
                {entry.entity.type}
                {entry.entity.id ? ` #${entry.entity.id}` : ''}
              </div>
            </dd>
          </div>
          {metadataEntries.length > 0 && (
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Details</dt>
              <dd className="mt-1 space-y-1">
                {metadataEntries.map(([key, value]) => (
                  <div key={key} className="flex gap-2 text-charcoal">
                    <span className="text-charcoal-600/70">{key.replace(/_/g, ' ')}:</span>
                    <span>{typeof value === 'object' ? JSON.stringify(value) : String(value)}</span>
                  </div>
                ))}
              </dd>
            </div>
          )}
        </dl>
      </div>
    </div>
  )
}

export default function AdminAuditLog() {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [activeQuickRange, setActiveQuickRange] = useState(null)
  const [page, setPage] = useState(1)
  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchAuditLog({ query, category, dateFrom, dateTo, page, pageSize: 50 })
      .then((res) => {
        if (!active) return
        setRows(res.items)
        setPagination(res.pagination)
      })
      .catch((err) => {
        if (!active) return
        setError(
          err?.response?.status === 403
            ? "You don't have permission to view the audit log."
            : 'Something went wrong loading the audit log. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [query, category, dateFrom, dateTo, page])

  function applyQuickRange(r) {
    setActiveQuickRange(r.key)
    setPage(1)
    const { dateFrom: from, dateTo: to } = quickRangeDates(r.days)
    setDateFrom(from)
    setDateTo(to)
  }

  function clearDateRange() {
    setActiveQuickRange(null)
    setPage(1)
    setDateFrom('')
    setDateTo('')
  }

  function applyCustomDate(field, value) {
    setActiveQuickRange(null)
    setPage(1)
    if (field === 'from') setDateFrom(value)
    else setDateTo(value)
  }

  return (
    <div>
      <AdminPageHeader
        title="Audit Log"
        description="Review important administrative actions across Women Shaping Futures — who did what, and when. Read-only historical evidence; nothing here can be edited or deleted."
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <label htmlFor="audit-search" className="sr-only">
            Search audit log
          </label>
          <input
            id="audit-search"
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search action, actor, or target…"
            className="w-64 text-sm focus:outline-none"
          />
        </div>

        <div>
          <label htmlFor="audit-category" className="sr-only">
            Category
          </label>
          <select
            id="audit-category"
            value={category}
            onChange={(e) => {
              setPage(1)
              setCategory(e.target.value)
            }}
            className="border border-taupe-300 bg-white px-3 py-2 text-sm"
          >
            {CATEGORIES.map((c) => (
              <option key={c.key} value={c.key}>
                {c.label}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5" role="group" aria-label="Quick date range">
          {QUICK_RANGES.map((r) => (
            <button
              key={r.key}
              type="button"
              onClick={() => applyQuickRange(r)}
              aria-pressed={activeQuickRange === r.key}
              className={`px-3 py-2 text-xs font-semibold ${
                activeQuickRange === r.key ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600 hover:bg-taupe-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-2">
          <label htmlFor="audit-date-from" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            From
          </label>
          <input
            id="audit-date-from"
            type="date"
            value={dateFrom}
            max={dateTo || undefined}
            onChange={(e) => applyCustomDate('from', e.target.value)}
            className="border border-taupe-300 bg-white px-2 py-1.5 text-sm"
          />
          <label htmlFor="audit-date-to" className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">
            To
          </label>
          <input
            id="audit-date-to"
            type="date"
            value={dateTo}
            min={dateFrom || undefined}
            onChange={(e) => applyCustomDate('to', e.target.value)}
            className="border border-taupe-300 bg-white px-2 py-1.5 text-sm"
          />
          {(dateFrom || dateTo) && (
            <button type="button" onClick={clearDateRange} className="text-xs font-semibold text-charcoal-600 hover:text-burgundy-600">
              Clear
            </button>
          )}
        </div>
      </div>

      {error && <EmptyState title="Couldn't load the audit log" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[860px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Timestamp</th>
                  <th className="px-4 py-3">Actor</th>
                  <th className="px-4 py-3">Action</th>
                  <th className="px-4 py-3">Target</th>
                  <th className="px-4 py-3">Category</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((entry) => (
                  <tr key={entry.id}>
                    <td className="px-4 py-3 text-charcoal-600">
                      <button type="button" onClick={() => setSelected(entry)} className="text-left hover:text-burgundy-600">
                        <time dateTime={entry.createdAt}>{timestampLabel(entry.createdAt)}</time>
                      </button>
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{entry.actor?.name || 'System'}</td>
                    <td className="px-4 py-3 font-medium text-charcoal">{entry.actionLabel}</td>
                    <td className="px-4 py-3 text-charcoal-600">{entry.entity.label}</td>
                    <td className="px-4 py-3">
                      <span className="bg-taupe-100 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600">
                        {CATEGORY_LABELS[entry.category] || entry.category}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No audit activity matches these filters" description="Try a different search term or clear your filters." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}

      {selected && <DetailDrawer entry={selected} onClose={() => setSelected(null)} />}
    </div>
  )
}
