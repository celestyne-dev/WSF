import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Search, Download } from 'lucide-react'
import { toast } from 'react-toastify'
import { fetchEventBySlug } from '../../api/events'
import { fetchAdminEventRegistrations, updateAdminEventRegistration, exportEventRegistrations } from '../../api/eventRegistrations'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const STATUS_FILTERS = ['', 'registered', 'attended', 'cancelled']

export default function AdminEventRegistrations() {
  // The route param is the event's slug (matching AdminEventEditor's own
  // :id param, which is really a slug) — fetched once to resolve the
  // numeric event id the registrations API is actually scoped to.
  const { id: slug } = useParams()

  const [event, setEvent] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [busyId, setBusyId] = useState(null)

  useEffect(() => {
    let active = true
    fetchEventBySlug(slug)
      .then((e) => {
        if (active) setEvent(e || null)
        if (active && !e) setNotFound(true)
      })
      .catch(() => active && setNotFound(true))
    return () => {
      active = false
    }
  }, [slug])

  useEffect(() => {
    if (!event?.id) return undefined
    let active = true
    fetchAdminEventRegistrations(event.id, { status, q: query, page, perPage: 25 })
      .then((res) => {
        if (active) {
          setResult(res)
          setError(null)
        }
      })
      .catch(() => active && setError('Something went wrong loading registrations. Please try again.'))
    return () => {
      active = false
    }
  }, [event?.id, status, query, page])

  async function handleStatusChange(registrationId, newStatus) {
    setBusyId(registrationId)
    try {
      await updateAdminEventRegistration(event.id, registrationId, { status: newStatus })
      toast.success('Registration updated.')
      setResult((prev) =>
        prev
          ? { ...prev, items: prev.items.map((r) => (r.id === registrationId ? { ...r, status: newStatus } : r)) }
          : prev
      )
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong updating this registration.')
    } finally {
      setBusyId(null)
    }
  }

  async function handleExport() {
    setExporting(true)
    try {
      await exportEventRegistrations(event.id, event.slug)
    } catch {
      toast.error("You don't have permission to export registrations, or something went wrong.")
    } finally {
      setExporting(false)
    }
  }

  if (notFound) return <EmptyState title="Event not found" description="This event may have been deleted or the URL is incorrect." />
  if (event === undefined) return <PageLoader />

  const counts = result?.counts || {}

  return (
    <div>
      <AdminPageHeader
        title={`Registrations: ${event.title}`}
        description={`Public URL: womenshapingfutures.org/events/${event.slug}`}
        actions={
          <>
            <Link to={`/admin/events/${event.slug}`} className="btn-secondary !px-4 !py-2 text-xs">
              &larr; Back to event
            </Link>
            <button type="button" onClick={handleExport} disabled={exporting} className="btn-secondary !px-4 !py-2 text-xs disabled:opacity-60">
              <Download size={14} /> {exporting ? 'Exporting…' : 'Export CSV'}
            </button>
          </>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Active</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{result?.activeCount ?? '—'}</p>
        </div>
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Capacity</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{result?.capacity ?? 'Unlimited'}</p>
        </div>
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Available</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{result?.available ?? '—'}</p>
        </div>
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Attended</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{counts.attended ?? 0}</p>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input
            value={query}
            onChange={(e) => {
              setPage(1)
              setQuery(e.target.value)
            }}
            placeholder="Search name or email…"
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
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s ? s.charAt(0).toUpperCase() + s.slice(1) : 'All statuses'}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load registrations" description={error} />}
      {!error && result === null && <PageLoader />}
      {!error && result !== null && (
        result.items.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[840px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Name</th>
                  <th className="px-4 py-3">Email</th>
                  <th className="px-4 py-3">Country</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Registered</th>
                  <th className="px-4 py-3">Attended</th>
                  <th className="px-4 py-3">Cancelled</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {result.items.map((row) => {
                  const busy = busyId === row.id
                  return (
                    <tr key={row.id}>
                      <td className="px-4 py-3 font-medium text-charcoal">{row.attendeeName || '—'}</td>
                      <td className="px-4 py-3 text-charcoal-600">{row.attendeeEmail || '—'}</td>
                      <td className="px-4 py-3 text-charcoal-600">{row.attendeeCountry || '—'}</td>
                      <td className="px-4 py-3">
                        <StatusBadge status={row.status} />
                      </td>
                      <td className="px-4 py-3 text-charcoal-600">{row.registeredAt ? formatDate(row.registeredAt) : '—'}</td>
                      <td className="px-4 py-3 text-charcoal-600">{row.attendedAt ? formatDate(row.attendedAt) : '—'}</td>
                      <td className="px-4 py-3 text-charcoal-600">{row.cancelledAt ? formatDate(row.cancelledAt) : '—'}</td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap gap-2 text-xs font-semibold">
                          {row.status !== 'attended' && (
                            <button type="button" disabled={busy} onClick={() => handleStatusChange(row.id, 'attended')} className="text-emerald-700 hover:underline disabled:opacity-50">
                              Mark attended
                            </button>
                          )}
                          {row.status === 'cancelled' && (
                            <button type="button" disabled={busy} onClick={() => handleStatusChange(row.id, 'registered')} className="text-burgundy-600 hover:underline disabled:opacity-50">
                              Restore
                            </button>
                          )}
                          {row.status !== 'cancelled' && (
                            <button type="button" disabled={busy} onClick={() => handleStatusChange(row.id, 'cancelled')} className="text-charcoal-600 hover:text-rose-600 disabled:opacity-50">
                              Cancel
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No registrations match those filters" description="Try a different search term or clear your filters." />
        )
      )}

      {result?.pagination && result.pagination.totalPages > 1 && (
        <div className="mt-6 flex items-center justify-center gap-4">
          <button type="button" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60">
            Previous
          </button>
          <span className="text-sm text-charcoal-600">
            Page {result.pagination.page} of {result.pagination.totalPages}
          </span>
          <button
            type="button"
            disabled={page >= result.pagination.totalPages}
            onClick={() => setPage((p) => Math.min(result.pagination.totalPages, p + 1))}
            className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
