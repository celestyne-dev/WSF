import { useEffect, useState } from 'react'
import { Navigate, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { fetchMyLearningEnrollments, withdrawFromProgram, enrollInProgram } from '../api/learningEnrollments'
import useSeo from '../hooks/useSeo'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import LearningProgramCard from '../components/cards/LearningProgramCard'
import { formatDate } from '../utils/format'

const TABS = [
  { key: 'current', label: 'In Progress' },
  { key: 'completed', label: 'Completed' },
  { key: 'withdrawn', label: 'Withdrawn' },
]

const EMPTY_COPY = {
  current: "You don't have any programs in progress.",
  completed: "You haven't completed any programs yet.",
  withdrawn: 'No withdrawn enrollments.',
}

// An enrollment's own card is rendered as a sibling of this status/
// action footer, never a descendant — LearningProgramCard's root is a
// <Link>, so Continue/Withdraw/Resume controls live outside it entirely
// (see SaveButton's own docstring for the same reasoning on other
// content types' cards).
function EnrollmentRow({ item, onWithdraw, onResume, busy }) {
  const program = item.program
  if (!program) return null

  const unavailable = item.programAvailable === false

  return (
    <div>
      {unavailable ? (
        // Never a link to hidden curriculum — the public detail route
        // 404s an archived program, so this stays a plain, non-clickable
        // summary rather than reusing LearningProgramCard's own <Link>.
        <div className="border border-taupe-200 bg-white p-4">
          <p className="font-serif text-lg font-semibold text-charcoal">{program.title}</p>
        </div>
      ) : (
        <LearningProgramCard program={program} />
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border border-t-0 border-taupe-200 bg-cream px-4 py-3 text-xs text-charcoal-600">
        <div className="flex flex-wrap items-center gap-3">
          {unavailable ? (
            <span className="font-semibold text-rose-600">This learning program is no longer available.</span>
          ) : (
            <>
              {item.status === 'active' && item.completedAt && (
                <span className="font-semibold text-emerald-700">Completed {formatDate(item.completedAt)}</span>
              )}
              {item.status === 'active' && !item.completedAt && item.totalLessons > 0 && (
                <span>
                  {item.completedLessons} of {item.totalLessons} lessons complete · {item.progressPercent}%
                </span>
              )}
              {item.status === 'withdrawn' && <span>Withdrawn {item.withdrawnAt ? formatDate(item.withdrawnAt) : ''}</span>}
              {item.enrolledAt && <span>Enrolled {formatDate(item.enrolledAt)}</span>}
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {!unavailable && item.status === 'active' && (
            <Link to={`/learning/${program.slug}#curriculum`} className="font-semibold text-burgundy-600 hover:underline">
              Continue learning
            </Link>
          )}
          {!unavailable && item.status === 'active' && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onWithdraw(item.id)}
              className="font-semibold text-charcoal-600 hover:text-burgundy-600 disabled:opacity-60"
            >
              Withdraw
            </button>
          )}
          {!unavailable && item.status === 'withdrawn' && (
            <button
              type="button"
              disabled={busy}
              onClick={() => onResume(program.id)}
              className="font-semibold text-burgundy-600 hover:underline disabled:opacity-60"
            >
              Resume learning
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function AccountLearningPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const user = useSelector((s) => s.auth.user)

  const [activeTab, setActiveTab] = useState('current')
  const [page, setPage] = useState(1)
  const [retryCount, setRetryCount] = useState(0)
  const [items, setItems] = useState(null)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const [busyKey, setBusyKey] = useState(null)

  useSeo({ title: 'My Learning | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!accessToken) return undefined
    let cancelled = false
    fetchMyLearningEnrollments({ state: activeTab, page, perPage: 10 })
      .then((result) => {
        if (cancelled) return
        setItems(result.items)
        setPagination(result.pagination)
        setError(null)
      })
      .catch(() => {
        if (!cancelled) setError('We couldn’t load your learning programs. Please try again.')
      })
    return () => {
      cancelled = true
    }
  }, [accessToken, activeTab, page, retryCount])

  if (!accessToken) return <Navigate to="/login" replace />
  if (!user) return <PageLoader />
  if (user.mustChangePassword) return <Navigate to="/change-password" replace />

  function handleTabChange(tabKey) {
    setActiveTab(tabKey)
    setPage(1)
    setItems(null)
  }

  function handleRetry() {
    setItems(null)
    setError(null)
    setRetryCount((n) => n + 1)
  }

  async function handleWithdraw(enrollmentId) {
    setBusyKey(enrollmentId)
    try {
      await withdrawFromProgram(enrollmentId)
      toast.success('Withdrawn from this program.')
      setRetryCount((n) => n + 1)
    } catch {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setBusyKey(null)
    }
  }

  async function handleResume(programId) {
    setBusyKey(programId)
    try {
      await enrollInProgram(programId)
      toast.success("You're enrolled again!")
      setRetryCount((n) => n + 1)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setBusyKey(null)
    }
  }

  return (
    <div className="container-editorial max-w-4xl py-14">
      <p className="eyebrow">My WSF Account</p>
      <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal">My Learning</h1>
      <p className="mt-2 max-w-xl text-sm text-charcoal-600">Programs you're learning with Women Shaping Futures.</p>

      <div className="mt-8 flex flex-wrap gap-2 border-b border-taupe-200 pb-4">
        {TABS.map((tab) => {
          const active = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => handleTabChange(tab.key)}
              aria-pressed={active}
              className={`px-3 py-1.5 text-sm font-medium transition-colors ${
                active ? 'bg-burgundy-600 text-ivory' : 'border border-taupe-300 text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600'
              }`}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      <div className="mt-8">
        {error ? (
          <EmptyState
            title="Something went wrong"
            description={error}
            action={
              <button type="button" onClick={handleRetry} className="btn-secondary mt-4">
                Try again
              </button>
            }
          />
        ) : items === null ? (
          <div className="space-y-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-28 animate-pulse bg-taupe-100" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            title={EMPTY_COPY[activeTab]}
            description="Explore WSF Learning and start a free program."
            action={
              <Link to="/learning" className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
                Browse Learning
              </Link>
            }
          />
        ) : (
          <>
            <div className="space-y-6">
              {items.map((item) => (
                <EnrollmentRow
                  key={item.id}
                  item={item}
                  onWithdraw={handleWithdraw}
                  onResume={handleResume}
                  busy={busyKey === item.id || busyKey === item.program?.id}
                />
              ))}
            </div>

            {pagination && pagination.totalPages > 1 && (
              <div className="mt-10 flex items-center justify-center gap-4">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Previous
                </button>
                <span className="text-sm text-charcoal-600">
                  Page {pagination.page} of {pagination.totalPages}
                </span>
                <button
                  type="button"
                  disabled={page >= pagination.totalPages}
                  onClick={() => setPage((p) => Math.min(pagination.totalPages, p + 1))}
                  className="btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
