import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchAdminLearningProgram } from '../../api/learning'
import { fetchAdminLearningEnrollments } from '../../api/learningEnrollments'
import AdminPageHeader from '../../components/cms/AdminPageHeader'
import StatusBadge from '../../components/cms/StatusBadge'
import PageLoader from '../../components/ui/PageLoader'
import EmptyState from '../../components/ui/EmptyState'
import { formatDate } from '../../utils/format'

const STATE_FILTERS = ['', 'current', 'completed', 'withdrawn']
const STATE_LABEL = { current: 'In progress', completed: 'Completed', withdrawn: 'Withdrawn' }

function rowStatus(row) {
  if (row.status === 'withdrawn') return 'withdrawn'
  return row.completedAt ? 'completed' : 'current'
}

// Read-only operational view (spec: "primarily operational/read-only" —
// no staff action ever marks a lesson complete or fabricates completion;
// learner lifecycle stays entirely self-service). See
// backend app/api/v1/learning.py's LearningEnrollmentAdminListResource
// for the same decision on the API side.
export default function AdminLearningEnrollments() {
  const { id: programId } = useParams()

  const [program, setProgram] = useState(undefined)
  const [notFound, setNotFound] = useState(false)
  const [query, setQuery] = useState('')
  const [state, setState] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    fetchAdminLearningProgram(programId)
      .then((p) => {
        if (active) setProgram(p || null)
        if (active && !p) setNotFound(true)
      })
      .catch(() => active && setNotFound(true))
    return () => {
      active = false
    }
  }, [programId])

  useEffect(() => {
    if (!program) return undefined
    let active = true
    fetchAdminLearningEnrollments(programId, { state, q: query, page, perPage: 25 })
      .then((res) => {
        if (active) {
          setResult(res)
          setError(null)
        }
      })
      .catch(() => active && setError('Something went wrong loading enrollments. Please try again.'))
    return () => {
      active = false
    }
  }, [program, programId, state, query, page])

  if (notFound) return <EmptyState title="Learning program not found" description="This program may have been deleted or the URL is incorrect." />
  if (program === undefined) return <PageLoader />

  const counts = result?.counts || {}

  return (
    <div>
      <AdminPageHeader
        title={`Enrollments: ${program.title}`}
        description={`Public URL: womenshapingfutures.org/learning/${program.slug}`}
        actions={
          <Link to={`/admin/learning/${programId}`} className="btn-secondary !px-4 !py-2 text-xs">
            &larr; Back to program
          </Link>
        }
      />

      <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">In progress</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{counts.current ?? '—'}</p>
        </div>
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Completed</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{counts.completed ?? '—'}</p>
        </div>
        <div className="border border-taupe-200 bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">Withdrawn</p>
          <p className="mt-1 text-2xl font-semibold text-charcoal">{counts.withdrawn ?? '—'}</p>
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
          value={state}
          onChange={(e) => {
            setPage(1)
            setState(e.target.value)
          }}
          className="border border-taupe-300 bg-white px-3 py-2 text-sm"
        >
          {STATE_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s ? STATE_LABEL[s] : 'All states'}
            </option>
          ))}
        </select>
      </div>

      {error && <EmptyState title="Couldn't load enrollments" description={error} />}
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
                  <th className="px-4 py-3">Progress</th>
                  <th className="px-4 py-3">Enrolled</th>
                  <th className="px-4 py-3">Completed</th>
                  <th className="px-4 py-3">Withdrawn</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-taupe-200">
                {result.items.map((row) => (
                  <tr key={row.id}>
                    <td className="px-4 py-3 font-medium text-charcoal">{row.learnerName || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.learnerEmail || '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.learnerCountry || '—'}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={rowStatus(row)} />
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">
                      {row.totalLessons > 0 ? `${row.completedLessons}/${row.totalLessons} (${row.progressPercent}%)` : '—'}
                    </td>
                    <td className="px-4 py-3 text-charcoal-600">{row.enrolledAt ? formatDate(row.enrolledAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.completedAt ? formatDate(row.completedAt) : '—'}</td>
                    <td className="px-4 py-3 text-charcoal-600">{row.withdrawnAt ? formatDate(row.withdrawnAt) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No enrollments match those filters" description="Try a different search term or clear your filters." />
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
