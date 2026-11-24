import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { fetchMyLearningEnrollments, withdrawFromProgram, enrollInProgram } from '../api/learningEnrollments'
import useSeo from '../hooks/useSeo'
import EmptyState from '../components/ui/EmptyState'
import LearningProgramCard from '../components/cards/LearningProgramCard'
import { formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import { downloadCertificatePdf, fetchCertificateNameMode, fetchMyCertificates, saveCertificateNameMode } from '../api/certificates'
import { CERTIFICATE_NAME_OPTIONS, CERTIFICATE_TERM, enrollmentCertificateState } from '../utils/certificates'

const TABS = [
  { key: 'current', label: 'In Progress' },
  { key: 'completed', label: 'Completed' },
  { key: 'withdrawn', label: 'Withdrawn' },
  { key: 'certificates', label: 'My Certificates' },
]

const EMPTY_COPY = {
  current: "You don't have any programs in progress.",
  completed: "You haven't completed any programs yet.",
  withdrawn: 'No withdrawn enrollments.',
}

// Download (authenticated blob), Verify (public link) and Add to LinkedIn
// (LinkedIn's documented add-to-profile URL pattern; no API integration).
function CertificateActions({ certificate }) {
  const [busy, setBusy] = useState(false)

  async function handleDownload() {
    setBusy(true)
    try {
      await downloadCertificatePdf(certificate)
      trackEvent('certificate_downloaded', { certificateNumber: certificate.certificateNumber })
    } catch {
      toast.error('We couldn’t download your certificate. Please try again.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <button type="button" disabled={busy} onClick={handleDownload} className="font-semibold text-burgundy-600 hover:underline disabled:opacity-60">
        Download PDF
      </button>
      <Link to={`/certificates/verify/${certificate.publicId}`} className="font-semibold text-burgundy-600 hover:underline">
        Verify credential
      </Link>
      {certificate.linkedinUrl && (
        <a
          href={certificate.linkedinUrl}
          target="_blank"
          rel="noopener noreferrer"
          onClick={() => trackEvent('certificate_linkedin_clicked', { certificateNumber: certificate.certificateNumber })}
          className="font-semibold text-burgundy-600 hover:underline"
        >
          Add to LinkedIn
        </a>
      )}
    </div>
  )
}

// Step 20: full name or initials on public verification, for every
// certificate (issued and future). The PDF keeps the full issued name.
function CertificateNamePreference({ sampleName, onChange }) {
  const [mode, setMode] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchCertificateNameMode()
      .then((m) => !cancelled && setMode(m))
      .catch(() => !cancelled && setMode('full'))
    return () => {
      cancelled = true
    }
  }, [])

  async function choose(next) {
    if (next === mode || saving) return
    setSaving(true)
    try {
      setMode(await saveCertificateNameMode(next))
      onChange?.()
      toast.success('Saved. Verification links now show your choice.')
    } catch {
      toast.error('We couldn’t save that. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  if (mode === null) return null
  return (
    <fieldset className="mb-6 border border-taupe-200 bg-white p-4">
      <legend className="px-1 text-sm font-semibold text-charcoal">Your name on public verification</legend>
      <p className="text-xs text-charcoal-600">
        Anyone with a certificate’s verification link (or its QR code) sees this. It never shows your email. Your downloaded
        certificate always carries your full name.
      </p>
      <div className="mt-3 flex flex-wrap gap-4 text-sm">
        {CERTIFICATE_NAME_OPTIONS.map((o) => (
          <label key={o.value} className="flex items-center gap-2">
            <input type="radio" name="certificate-name-display" value={o.value} checked={mode === o.value} disabled={saving} onChange={() => choose(o.value)} />
            {o.label}
            {sampleName && <span className="text-charcoal-600">({o.example(sampleName)})</span>}
          </label>
        ))}
      </div>
    </fieldset>
  )
}

function CertificatesList() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  const [reload, setReload] = useState(0)
  const user = useSelector((st) => st.auth.user)
  const sampleName = [user?.firstName, user?.lastName].filter(Boolean).join(' ')

  useEffect(() => {
    let cancelled = false
    fetchMyCertificates()
      .then((rows) => !cancelled && setItems(rows))
      .catch(() => !cancelled && setError('We couldn’t load your certificates. Please try again.'))
    return () => {
      cancelled = true
    }
  }, [reload])

  const preference = <CertificateNamePreference sampleName={sampleName} onChange={() => setReload((n) => n + 1)} />
  if (error) return <EmptyState title="Something went wrong" description={error} />
  if (items === null) return <div className="h-28 animate-pulse bg-taupe-100" />
  if (items.length === 0) {
    return (
      <>
      {preference}
      <EmptyState
        title="No certificates yet"
        description={`Complete a WSF program that offers a ${CERTIFICATE_TERM} and it will appear here.`}
        action={
          <Link to="/learning" className="mt-4 inline-block text-sm font-semibold text-burgundy-600 hover:underline">
            Browse Learning
          </Link>
        }
      />
      </>
    )
  }
  return (
    <>
    {preference}
    <ul className="space-y-4">
      {items.map((c) => (
        <li key={c.publicId} className="border border-taupe-200 bg-white p-4">
          <p className="eyebrow">{c.certificateTitle}</p>
          <p className="mt-1 font-serif text-lg font-semibold text-charcoal">{c.programTitle}</p>
          <p className="mt-1 text-xs text-charcoal-600">
            {c.certificateNumber}
            {c.completedAt && <> · Completed {formatDate(c.completedAt)}</>}
            {c.status === 'revoked' && <span className="font-semibold text-rose-600"> · Revoked</span>}
          </p>
          {c.publicRecipientName && (
            <p className="mt-1 text-xs text-charcoal-600">Shown publicly as: {c.publicRecipientName}</p>
          )}
          {c.status === 'active' && (
            <div className="mt-3 text-xs">
              <CertificateActions certificate={c} />
            </div>
          )}
        </li>
      ))}
    </ul>
    </>
  )
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
  // Circle entitlement lapsed (spec section Q) — the enrollment row and
  // its progress stay exactly as-is; only the "Continue learning" action
  // is replaced, and only while the program is otherwise available. The
  // learner's own Withdraw action is unaffected and never automatic.
  const circleAccessLapsed = !unavailable && item.status === 'active' && item.canAccessCurriculum === false && item.accessReason === 'circle_required'
  const certificateState = enrollmentCertificateState(item)

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
              {circleAccessLapsed && (
                <span className="font-semibold text-rose-600">Your WSF Circle access is currently inactive.</span>
              )}
              {item.status === 'active' && item.completedAt && (
                <span className="font-semibold text-emerald-700">Completed {formatDate(item.completedAt)}</span>
              )}
              {certificateState === 'available' && <span className="font-semibold text-plum-600">Certificate available</span>}
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
          {!unavailable && item.status === 'active' && circleAccessLapsed && (
            <Link to="/circle" className="font-semibold text-burgundy-600 hover:underline">
              Explore WSF Circle
            </Link>
          )}
          {!unavailable && item.status === 'active' && !circleAccessLapsed && (
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
      {certificateState === 'available' && (
        <div className="border border-t-0 border-taupe-200 bg-white px-4 py-3 text-xs">
          <CertificateActions certificate={item.certificate} />
        </div>
      )}
    </div>
  )
}

// Routed only as a child of AccountLayout, which already guards on
// accessToken/user/mustChangePassword before rendering any child route.
export default function AccountLearningPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)

  const [activeTab, setActiveTab] = useState('current')
  const [page, setPage] = useState(1)
  const [retryCount, setRetryCount] = useState(0)
  const [items, setItems] = useState(null)
  const [pagination, setPagination] = useState(null)
  const [error, setError] = useState(null)
  const [busyKey, setBusyKey] = useState(null)

  useSeo({ title: 'My Learning | Women Shaping Futures', robots: 'noindex, nofollow' })

  useEffect(() => {
    if (!accessToken || activeTab === 'certificates') return undefined
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
    <div className="max-w-[880px]">
      <h2 className="font-serif text-2xl font-semibold text-charcoal">My Learning</h2>
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
        {activeTab === 'certificates' ? (
          <CertificatesList />
        ) : error ? (
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
