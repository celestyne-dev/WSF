import { useEffect, useState } from 'react'
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { toast } from 'react-toastify'
import { ExternalLink, FileText, PlayCircle, BookOpen, ClipboardList, CheckCircle2, Circle } from 'lucide-react'
import { fetchLearningProgramBySlug } from '../api/learning'
import {
  enrollInProgram,
  checkLearningEnrollment,
  fetchProtectedCurriculum,
  markLessonComplete,
  markLessonIncomplete,
} from '../api/learningEnrollments'
import { resolveImage } from '../utils/media'
import { formatCurrency, formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import NewsletterForm from '../components/ui/NewsletterForm'
import SaveButton from '../components/account/SaveButton'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

const PROGRAM_TYPE_LABEL = {
  course: 'Course',
  masterclass: 'Masterclass',
  program: 'Program',
  learning_series: 'Learning Series',
}

const LESSON_ICON = {
  article: FileText,
  resource: BookOpen,
  video: PlayCircle,
  external_link: ExternalLink,
  activity: ClipboardList,
  text: FileText,
}

function LessonRow({ lesson, enrollment, onToggleComplete, toggleBusy }) {
  const Icon = LESSON_ICON[lesson.lessonType] || FileText
  const label = lesson.article?.title || lesson.resource?.name || lesson.title
  const linkClass = 'text-sm font-medium text-charcoal hover:text-burgundy-600'

  let content
  if (lesson.article) {
    content = <Link to={`/${lesson.article.slug}`} className={linkClass}>{label}</Link>
  } else if (lesson.resource) {
    content = <Link to={`/resources/${lesson.resource.slug}`} className={linkClass}>{label}</Link>
  } else if (lesson.externalUrl) {
    content = (
      <a href={lesson.externalUrl} target="_blank" rel="noopener noreferrer" className={linkClass}>
        {label}
      </a>
    )
  } else {
    content = <span className="text-sm font-medium text-charcoal">{label}</span>
  }

  // Native text/activity content was already stored on the lesson but
  // never rendered anywhere — minimally surfaced here rather than built
  // into a new lesson-player route (spec: keep progress interaction
  // within this existing curriculum view).
  const showInlineContent = (lesson.lessonType === 'text' || lesson.lessonType === 'activity') && lesson.content?.length > 0
  const canToggle = !!enrollment && enrollment.status === 'active'
  const isComplete = canToggle && enrollment.completedLessonIds?.includes(lesson.id)

  return (
    <li className="py-2.5">
      <div className="flex items-start gap-3">
        <Icon size={16} className="mt-0.5 shrink-0 text-charcoal-600" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          {content}
          {lesson.summary && <p className="mt-0.5 text-xs text-charcoal-600/80">{lesson.summary}</p>}
          {showInlineContent && (
            <div className="mt-2 text-sm text-charcoal-700">
              <ArticleContent blocks={lesson.content} />
            </div>
          )}
        </div>
        {lesson.durationMinutes ? <span className="shrink-0 text-xs text-charcoal-600/70">{lesson.durationMinutes} min</span> : null}
      </div>
      {canToggle && (
        <div className="mt-1.5 pl-7">
          <button
            type="button"
            disabled={toggleBusy}
            onClick={() => onToggleComplete(lesson, isComplete)}
            aria-pressed={isComplete}
            className={`inline-flex items-center gap-1.5 text-xs font-semibold disabled:opacity-60 ${
              isComplete ? 'text-emerald-700' : 'text-charcoal-600 hover:text-burgundy-600'
            }`}
          >
            {isComplete ? <CheckCircle2 size={14} /> : <Circle size={14} />}
            {isComplete ? 'Completed' : 'Mark complete'}
          </button>
        </div>
      )}
    </li>
  )
}

function ModuleAccordion({ module, index, enrollment, onToggleComplete, toggleBusyLessonId }) {
  return (
    <details className="border border-taupe-200 bg-white" open={index === 0}>
      <summary className="cursor-pointer list-none px-5 py-4 font-serif text-lg font-semibold text-charcoal marker:content-none">
        {module.title}
      </summary>
      <div className="border-t border-taupe-200 px-5 pb-4">
        {module.description && <p className="mt-3 text-sm text-charcoal-600">{module.description}</p>}
        {module.lessons.length > 0 ? (
          <ul className="mt-2 divide-y divide-taupe-100">
            {module.lessons.map((lesson) => (
              <LessonRow
                key={lesson.id}
                lesson={lesson}
                enrollment={enrollment}
                onToggleComplete={onToggleComplete}
                toggleBusy={toggleBusyLessonId === lesson.id}
              />
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm text-charcoal-600/70">No lessons added yet.</p>
        )}
      </div>
    </details>
  )
}

function durationLabel(program) {
  if (!program.durationValue) return null
  return `${program.durationValue} ${program.durationUnit || ''}`.trim()
}

function CtaButton({ program }) {
  if (program.accessType === 'product' && program.product) {
    const price = program.product.salePrice ?? program.product.price
    return (
      <a href={`/shop/${program.product.slug}`} className="btn-primary inline-flex">
        Enroll — {price ? formatCurrency(price, program.product.currency) : 'View pricing'}
      </a>
    )
  }
  if (program.accessType === 'external' && program.externalUrl) {
    return (
      <a href={program.externalUrl} target="_blank" rel="noopener noreferrer" className="btn-primary inline-flex items-center gap-2">
        Enroll externally <ExternalLink size={16} />
      </a>
    )
  }
  return null
}

// Shared by both free and circle_only CTAs once access to enroll/continue
// is already established — only the gate above it differs per access type.
function EnrollmentStateCta({ enrollment, pending, onEnroll }) {
  if (enrollment === undefined) return null // still checking — avoid a CTA flash
  if (enrollment && enrollment.completedAt) {
    return (
      <div className="inline-flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-2 border border-emerald-200 bg-emerald-50 px-4 py-2.5 text-sm font-semibold text-emerald-700">
          <CheckCircle2 size={16} /> Completed
        </span>
        <Link to="/account/learning" className="text-sm font-semibold text-burgundy-600 hover:underline">
          View in My Learning
        </Link>
      </div>
    )
  }
  if (enrollment && enrollment.status === 'active') {
    return (
      <div className="flex flex-wrap items-center gap-3">
        <a href="#curriculum" className="btn-primary inline-flex">
          Continue learning
        </a>
        {enrollment.totalLessons > 0 && (
          <span className="text-sm text-charcoal-600">
            {enrollment.completedLessons} of {enrollment.totalLessons} lessons complete
          </span>
        )}
      </div>
    )
  }
  const label = enrollment && enrollment.status === 'withdrawn' ? 'Resume learning' : 'Start learning'
  return (
    <button type="button" onClick={onEnroll} disabled={pending} className="btn-primary inline-flex disabled:opacity-60">
      {pending ? 'Please wait…' : label}
    </button>
  )
}

// Free-access programs only (spec's core product decision — external/
// product programs never get a WSF enrollment row, see CtaButton above
// and backend app/services/learning_enrollments.py's own docstring).
function LearningEnrollmentCta({ enrollment, accessToken, pending, onEnroll, onSignIn }) {
  if (!accessToken) {
    return (
      <button type="button" onClick={onSignIn} className="btn-primary inline-flex">
        Sign in to track progress
      </button>
    )
  }
  return <EnrollmentStateCta enrollment={enrollment} pending={pending} onEnroll={onEnroll} />
}

// circle_only programs — the "Circle active?" gate (spec section L) sits
// in front of the same enroll/continue states free programs use. Backend
// remains authoritative either way: viewerCanAccess/circleAccessDenied
// are UI guidance, not the enrollment/curriculum/progress endpoints'
// own checks.
function CircleLearningCta({ enrollment, accessToken, viewerCanAccess, circleAccessDenied, pending, onEnroll, onSignIn }) {
  if (!accessToken) {
    return (
      <div className="inline-flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-charcoal">Included with WSF Circle</span>
        <button type="button" onClick={onSignIn} className="btn-primary inline-flex">
          Sign in
        </button>
      </div>
    )
  }
  if (!viewerCanAccess || circleAccessDenied) {
    return (
      <div className="inline-flex flex-wrap items-center gap-3">
        <span className="text-sm font-semibold text-charcoal">WSF Circle access required</span>
        <Link to="/circle" className="btn-primary inline-flex">
          Explore WSF Circle
        </Link>
      </div>
    )
  }
  return <EnrollmentStateCta enrollment={enrollment} pending={pending} onEnroll={onEnroll} />
}

export default function LearningProgramDetailPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [program, setProgram] = useState(undefined)
  const [error, setError] = useState(null)
  const [enrollment, setEnrollment] = useState(undefined)
  const [enrolling, setEnrolling] = useState(false)
  const [toggleBusyLessonId, setToggleBusyLessonId] = useState(null)
  // Full protected curriculum for circle_only (spec section H/L) — null
  // until a successful fetch; never populated from stale state once
  // access is lost (see the effect below's circle_required handling).
  const [protectedModules, setProtectedModules] = useState(null)
  const [circleAccessDenied, setCircleAccessDenied] = useState(false)

  useEffect(() => {
    let active = true
    setProgram(undefined)
    setError(null)
    fetchLearningProgramBySlug(slug)
      .then((data) => active && setProgram(data))
      .catch(() => active && setError('Something went wrong loading this program. Please try again.'))
    return () => {
      active = false
    }
  }, [slug])

  useEffect(() => {
    const eligible = program && (program.accessType === 'free' || program.accessType === 'circle_only')
    if (!eligible || !accessToken) return undefined
    let active = true
    checkLearningEnrollment(program.id).then((result) => {
      if (active) setEnrollment(result.enrollment)
    })
    return () => {
      active = false
    }
  }, [program, accessToken])

  // Protected curriculum fetch for circle_only (spec sections H/L/M) — the
  // public detail payload only ever carries the safe outline for this
  // access type, so full lesson content is fetched separately once an
  // active enrollment exists. Any circle_required failure here clears
  // protectedModules rather than leaving stale content on screen.
  useEffect(() => {
    let active = true
    async function run() {
      setProtectedModules(null)
      setCircleAccessDenied(false)
      if (!program || program.accessType !== 'circle_only' || !accessToken) return
      if (!enrollment || enrollment.status !== 'active') return
      try {
        const modules = await fetchProtectedCurriculum(enrollment.id)
        if (active) setProtectedModules(modules)
      } catch (err) {
        if (!active) return
        if (err?.response?.data?.error?.code === 'circle_required') setCircleAccessDenied(true)
      }
    }
    run()
    return () => {
      active = false
    }
  }, [program, accessToken, enrollment])

  const canonicalUrl = program ? `https://womenshapingfutures.org/learning/${program.slug}` : ''

  useSeo(
    program
      ? {
          title: program.seo?.title || `${program.title} | Women Shaping Futures Learning`,
          description: program.seo?.description || program.shortDescription || program.subtitle || program.title,
          canonical: program.seo?.canonical || canonicalUrl,
          image: resolveImage(program.heroMedia?.mediaPath, { width: 1200, height: 630 }),
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this program" description={error} /></div>
  if (program === undefined) return <PageLoader />
  if (program === null) return <NotFoundPage />

  async function handleEnroll() {
    setEnrolling(true)
    try {
      const result = await enrollInProgram(program.id)
      setEnrollment(result.enrollment)
      toast.success(`You're enrolled in ${program.title}.`)
      trackEvent('learning_enrollment_started', { programSlug: program.slug })
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    } finally {
      setEnrolling(false)
    }
  }

  async function handleToggleLesson(lesson, isComplete) {
    setToggleBusyLessonId(lesson.id)
    try {
      const updated = isComplete
        ? await markLessonIncomplete(enrollment.id, lesson.id)
        : await markLessonComplete(enrollment.id, lesson.id)
      setEnrollment(updated)
      if (!isComplete) {
        trackEvent('learning_lesson_completed', { programSlug: program.slug, lessonId: lesson.id })
        if (updated.completedAt) {
          trackEvent('learning_program_completed', { programSlug: program.slug })
        }
      }
    } catch {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setToggleBusyLessonId(null)
    }
  }

  const upcomingEvent = program.events?.[0] || null

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Learning', to: '/learning' }, { label: program.title }]} />
      </div>
      <div className="container-editorial grid grid-cols-1 gap-10 py-10 sm:grid-cols-[360px_1fr]">
        <div>
          <MediaImage media={program.heroMedia} variant="medium" alt={program.title} width={800} height={600} aspect={4 / 3} className="w-full object-cover" />
        </div>
        <div>
          <div className="flex items-start justify-between gap-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="eyebrow">{PROGRAM_TYPE_LABEL[program.programType] || program.programType}</span>
              {program.difficultyLevel && <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">· {program.difficultyLevel.replace('_', ' ')}</span>}
              {program.featured && <span className="bg-burgundy-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>}
            </div>
            <SaveButton contentType="learning_program" contentId={program.id} />
          </div>
          <h1 className="mt-2 font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{program.title}</h1>
          {program.subtitle && <p className="mt-2 max-w-xl text-lg text-charcoal-600">{program.subtitle}</p>}

          {program.primaryInstructor && (
            <p className="mt-3 text-sm text-charcoal-600">
              Taught by{' '}
              <Link to={`/authors/${program.primaryInstructor.slug}`} className="font-medium text-charcoal hover:text-burgundy-600">
                {program.primaryInstructor.name}
              </Link>
              {program.coInstructors?.length > 0 && ` and ${program.coInstructors.map((i) => i.name).join(', ')}`}
            </p>
          )}

          <div className="mt-5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-charcoal-600/70">
            {durationLabel(program) && <span>{durationLabel(program)}</span>}
            <span>{program.deliveryMode?.replace('_', ' ')}</span>
            {program.providerOrganization && <span>Provided by {program.providerOrganization.name}</span>}
          </div>

          {upcomingEvent && (
            <div className="mt-5 border border-taupe-200 bg-blush-50 px-4 py-3 text-sm text-charcoal-700">
              <p className="font-semibold text-charcoal">Next live session: {formatDate(upcomingEvent.date)}</p>
              {upcomingEvent.location && <p className="mt-0.5 text-charcoal-600">{upcomingEvent.location}</p>}
              <Link to={`/events/${upcomingEvent.slug}`} className="mt-1 inline-block text-burgundy-600 hover:underline">View event details</Link>
            </div>
          )}

          <div className="mt-6">
            {program.accessType === 'free' ? (
              <LearningEnrollmentCta
                enrollment={enrollment}
                accessToken={accessToken}
                pending={enrolling}
                onEnroll={handleEnroll}
                onSignIn={() => navigate('/login', { state: { from: location.pathname } })}
              />
            ) : program.accessType === 'circle_only' ? (
              <CircleLearningCta
                enrollment={enrollment}
                accessToken={accessToken}
                viewerCanAccess={program.viewerCanAccess}
                circleAccessDenied={circleAccessDenied}
                pending={enrolling}
                onEnroll={handleEnroll}
                onSignIn={() => navigate('/login', { state: { from: location.pathname } })}
              />
            ) : (
              <CtaButton program={program} />
            )}
          </div>

          <div className="mt-6">
            <ShareBar title={program.title} url={canonicalUrl} trackEventName="learning_share_click" trackPayload={{ programSlug: program.slug }} />
          </div>
        </div>
      </div>

      {program.overview?.length > 0 && (
        <div className="container-editorial max-w-reading pb-4">
          <ArticleContent blocks={program.overview} />
        </div>
      )}

      {program.learningOutcomes?.length > 0 && (
        <div className="container-editorial max-w-reading py-8">
          <h2 className="font-serif text-xl font-semibold text-charcoal">What you'll learn</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-charcoal-700">
            {program.learningOutcomes.map((outcome, i) => (
              <li key={i}>{outcome}</li>
            ))}
          </ul>
        </div>
      )}

      {program.prerequisites?.length > 0 && (
        <div className="container-editorial max-w-reading pb-8">
          <h2 className="font-serif text-xl font-semibold text-charcoal">Prerequisites</h2>
          <ul className="mt-3 list-disc space-y-1.5 pl-5 text-sm text-charcoal-700">
            {program.prerequisites.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        </div>
      )}

      {(() => {
        // free: public detail already carries the full curriculum. circle_only
        // with an active enrollment + confirmed access: swap in the protected
        // curriculum fetched above. Everything else (circle_only without full
        // access yet, external, product) renders the safe public outline the
        // backend returned instead — never lesson content/links/toggles.
        const circleFullAccess = program.accessType === 'circle_only' && protectedModules !== null
        const curriculumModules = circleFullAccess ? protectedModules : program.modules
        const curriculumEnrollment = program.accessType === 'free' || circleFullAccess ? enrollment : null
        if (!curriculumModules?.length) return null
        return (
          <div id="curriculum" className="container-editorial max-w-reading pb-10">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="font-serif text-xl font-semibold text-charcoal">Curriculum</h2>
              {curriculumEnrollment && curriculumEnrollment.status === 'active' && curriculumEnrollment.totalLessons > 0 && (
                <p className="text-sm text-charcoal-600">
                  {curriculumEnrollment.completedLessons} of {curriculumEnrollment.totalLessons} lessons complete ·{' '}
                  {curriculumEnrollment.progressPercent}%
                </p>
              )}
            </div>
            {program.accessType === 'circle_only' && !circleFullAccess && (
              <p className="mt-1 text-sm text-charcoal-600">Full lessons are available to WSF Circle members.</p>
            )}
            <div className="mt-4 space-y-3">
              {curriculumModules.map((module, i) => (
                <ModuleAccordion
                  key={module.id}
                  module={module}
                  index={i}
                  enrollment={curriculumEnrollment}
                  onToggleComplete={handleToggleLesson}
                  toggleBusyLessonId={toggleBusyLessonId}
                />
              ))}
            </div>
          </div>
        )
      })()}

      {(program.relatedArticles?.length > 0 || program.relatedResources?.length > 0) && (
        <div className="container-editorial max-w-reading border-t border-taupe-200 py-10">
          <h2 className="font-serif text-xl font-semibold text-charcoal">Related reading</h2>
          <ul className="mt-3 space-y-2">
            {program.relatedArticles.map((a) => (
              <li key={`article-${a.id}`}>
                <Link to={`/${a.slug}`} className="text-sm font-medium text-burgundy-600 hover:underline">{a.title}</Link>
              </li>
            ))}
            {program.relatedResources.map((r) => (
              <li key={`resource-${r.id}`}>
                <Link to={`/resources/${r.slug}`} className="text-sm font-medium text-burgundy-600 hover:underline">{r.name}</Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <section className="border-t border-taupe-200 bg-charcoal py-14 text-ivory">
        <div className="container-editorial flex flex-col items-center text-center">
          <p className="eyebrow !text-blush-200">Never miss a new program</p>
          <h2 className="mt-3 max-w-xl font-serif text-2xl font-semibold sm:text-3xl">Get new courses and masterclasses in your inbox</h2>
          <div className="mt-6">
            <NewsletterForm variant="dark" source="learning_detail" />
          </div>
        </div>
      </section>
    </div>
  )
}
