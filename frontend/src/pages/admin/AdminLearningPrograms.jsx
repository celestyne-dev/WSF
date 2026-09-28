import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, ExternalLink, Search, Star } from 'lucide-react'
import { fetchAdminLearningPrograms } from '../../api/learning'
import { formatDate } from '../../utils/format'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import Pagination from '../../components/ui/Pagination'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'

const STATUSES = ['draft', 'review', 'published', 'archived']
const PROGRAM_TYPES = [
  { value: 'course', label: 'Course' },
  { value: 'masterclass', label: 'Masterclass' },
  { value: 'program', label: 'Program' },
  { value: 'learning_series', label: 'Learning Series' },
]
const DELIVERY_MODES = [
  { value: 'self_paced', label: 'Self-paced' },
  { value: 'live_online', label: 'Live online' },
  { value: 'in_person', label: 'In person' },
  { value: 'hybrid', label: 'Hybrid' },
]
const ACCESS_TYPES = [
  { value: 'free', label: 'Free' },
  { value: 'external', label: 'External' },
  { value: 'product', label: 'Product' },
]

export default function AdminLearningPrograms() {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [programType, setProgramType] = useState('')
  const [deliveryMode, setDeliveryMode] = useState('')
  const [accessType, setAccessType] = useState('')
  const [featured, setFeatured] = useState('')
  const [page, setPage] = useState(1)

  const [rows, setRows] = useState(undefined)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setError(null)
    fetchAdminLearningPrograms({
      query: query || undefined,
      status: status || undefined,
      programType: programType || undefined,
      deliveryMode: deliveryMode || undefined,
      accessType: accessType || undefined,
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
            ? "You don't have permission to view Learning programs."
            : 'Something went wrong loading learning programs. Please try again.',
        )
      })
    return () => {
      active = false
    }
  }, [query, status, programType, deliveryMode, accessType, featured, page])

  function withReset(setter) {
    return (value) => {
      setPage(1)
      setter(value)
    }
  }

  return (
    <div>
      <AdminPageHeader
        title="Learning"
        description="Courses, masterclasses, and learning programs — see app/models/learning.py for what this deliberately is not (a full LMS)."
        actions={
          <Link to="/admin/learning/new" className="btn-primary !px-4 !py-2 text-xs">
            <Plus size={14} /> New program
          </Link>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="text-charcoal-600" />
          <label htmlFor="learning-search" className="sr-only">Search learning programs</label>
          <input
            id="learning-search"
            value={query}
            onChange={(e) => withReset(setQuery)(e.target.value)}
            placeholder="Search programs…"
            className="w-56 text-sm focus:outline-none"
          />
        </div>
        <select value={status} onChange={(e) => withReset(setStatus)(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select value={programType} onChange={(e) => withReset(setProgramType)(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All types</option>
          {PROGRAM_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
        <select value={deliveryMode} onChange={(e) => withReset(setDeliveryMode)(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All delivery modes</option>
          {DELIVERY_MODES.map((d) => (
            <option key={d.value} value={d.value}>{d.label}</option>
          ))}
        </select>
        <select value={accessType} onChange={(e) => withReset(setAccessType)(e.target.value)} className="border border-taupe-300 bg-white px-3 py-2 text-sm">
          <option value="">All access types</option>
          {ACCESS_TYPES.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
        <label className="flex items-center gap-2 text-sm text-charcoal-600">
          <input type="checkbox" checked={featured === 'true'} onChange={(e) => withReset(setFeatured)(e.target.checked ? 'true' : '')} />
          Featured only
        </label>
      </div>

      {error && <EmptyState title="Couldn't load learning programs" description={error} />}
      {!error && rows === undefined && <PageLoader />}
      {!error && rows !== undefined && (
        rows.length ? (
          <div className="overflow-x-auto border border-taupe-200 bg-white">
            <table className="w-full min-w-[980px] text-left text-sm">
              <thead className="bg-taupe-100 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                <tr>
                  <th className="px-4 py-3">Title</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Instructor</th>
                  <th className="px-4 py-3">Delivery</th>
                  <th className="px-4 py-3">Access</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3">Updated</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {rows.map((row) => (
                  <tr key={row.id}>
                    <td className="max-w-xs truncate px-4 py-3 font-medium text-charcoal">
                      <Link to={`/admin/learning/${row.id}`} className="hover:text-burgundy-600">
                        {row.title}
                      </Link>
                      {row.featured && <Star size={12} className="ml-1.5 inline text-burgundy-600" fill="currentColor" aria-label="Featured" />}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{PROGRAM_TYPES.find((t) => t.value === row.programType)?.label || row.programType}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.primaryInstructor?.name || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{DELIVERY_MODES.find((d) => d.value === row.deliveryMode)?.label || row.deliveryMode}</td>
                    <td className="px-4 py-3 text-charcoal-600">{ACCESS_TYPES.find((a) => a.value === row.accessType)?.label || row.accessType}</td>
                    <td className="px-4 py-3"><StatusBadge status={row.status} /></td>
                    <td className="px-4 py-3 text-charcoal-600">{row.updatedAt ? formatDate(row.updatedAt, { month: 'short', day: 'numeric', year: 'numeric' }) : '—'}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-3">
                        {row.status === 'published' && (
                          <a href={`/learning/${row.slug}`} target="_blank" rel="noreferrer" aria-label="View live" className="text-charcoal-600 hover:text-burgundy-600">
                            <ExternalLink size={15} />
                          </a>
                        )}
                        <Link to={`/admin/learning/${row.id}`} className="text-charcoal-600 hover:text-burgundy-600">
                          Edit
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No learning programs match those filters" description="Create a new program or broaden your search." />
        )
      )}
      {pagination && <Pagination pagination={pagination} onPageChange={setPage} />}
    </div>
  )
}
