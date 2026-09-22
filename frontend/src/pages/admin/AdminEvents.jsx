import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, ExternalLink, Search } from 'lucide-react'
import { fetchEvents } from '../../api/events'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const TYPES = [
  'Conference',
  'Summit',
  'Workshop',
  'Webinar',
  'Networking Event',
  'Panel',
  'Masterclass',
  'Training',
  'Community Event',
  'Career Event',
  'Founder Event',
  'Mentorship Event',
  'Awards Event',
  'Other',
]

export default function AdminEvents() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [type, setType] = useState('')
  const [format, setFormat] = useState('')
  const [rows, setRows] = useState(undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchEvents({ status, query, type, format, pageSize: 100 })
      .then((res) => active && setRows(res.items))
      .catch(() => active && setError('Something went wrong loading events. Please try again.'))
    return () => {
      active = false
    }
  }, [status, query, type, format])

  return (
    <div>
      <AdminPageHeader
        title="Events"
        description="Conferences, workshops, and networking events hosted by Women Shaping Futures and partners."
        actions={
          <Link to="/admin/events/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New event
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search events…" className="w-56 text-sm focus:outline-none" />
        </div>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {['draft', 'published', 'cancelled', 'archived'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={type} onChange={(e) => setType(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select value={format} onChange={(e) => setFormat(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All formats</option>
          {['in-person', 'virtual', 'hybrid'].map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load events" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Host</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Start date</th>
                  <th className="px-4 py-3">Location / format</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Registration</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      {row.title}
                      {row.featured && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-burgundy-600">Featured</span>}
                      {row.sponsored && <span className="ml-1 text-[10px] font-semibold uppercase tracking-wide text-charcoal-600/60">Sponsored</span>}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.organizer || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.type || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.date ? formatDate(row.date, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.format === 'virtual' ? 'Virtual' : [row.location, row.format].filter(Boolean).join(' · ') || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={row.isCancelled ? 'cancelled' : row.isPast && row.status === 'published' ? 'past' : row.status} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.soldOut ? 'Sold out' : row.registrationRequired ? 'Required' : 'Not required'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/events/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/events/${row.slug}`} aria-label="Edit" className="text-charcoal-600 hover:text-burgundy-600">
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
          <EmptyState title="No events match those filters yet" description="Create a new event or broaden your search." />
        )
      )}
    </div>
  )
}
