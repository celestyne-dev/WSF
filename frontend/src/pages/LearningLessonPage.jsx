import { useState } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
import { toast } from 'react-toastify'
import { ArrowLeft, ArrowRight, BookOpen, CheckCircle2, Circle, ExternalLink, FileText, ListTree } from 'lucide-react'
import useCourse from '../hooks/useCourse'
import useSeo from '../hooks/useSeo'
import { trackEvent } from '../utils/analytics'
import { LESSON_TYPE_LABEL, currentModuleIndex, formatMinutes, lessonNeighbors } from '../utils/learning'
import ArticleContent from '../components/article/ArticleContent'
import { LEARNING_RENDERERS } from '../components/learning/learningRenderers'
import CourseCurriculum from '../components/learning/CourseCurriculum'
import CourseProgress from '../components/learning/CourseProgress'
import Breadcrumb from '../components/ui/Breadcrumb'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import VideoEmbed from '../components/ui/VideoEmbed'
import NotFoundPage from './NotFoundPage'

function LinkedLesson({ lesson }) {
  // Lessons that point at existing WSF content keep it in one place: the
  // lesson introduces it and links to it, never a copy.
  if (lesson.article) {
    return (
      <Link to={`/${lesson.article.slug}`} className="mt-8 flex items-start gap-4 rounded-card border border-taupe-200 bg-white p-5 hover:border-burgundy-500">
        <FileText size={20} aria-hidden="true" className="mt-1 shrink-0 text-plum-600" />
        <span>
          <span className="block text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">Read the article</span>
          <span className="mt-1 block font-serif text-xl font-semibold text-charcoal">{lesson.article.title}</span>
        </span>
      </Link>
    )
  }
  if (lesson.lessonType === 'resource' && lesson.resource) {
    return (
      <Link to={`/resources/${lesson.resource.slug}`} className="mt-8 flex items-start gap-4 rounded-card border border-taupe-200 bg-cream p-5 hover:border-burgundy-500">
        <BookOpen size={20} aria-hidden="true" className="mt-1 shrink-0 text-plum-600" />
        <span>
          <span className="block text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">Open the resource</span>
          <span className="mt-1 block font-serif text-xl font-semibold text-charcoal">{lesson.resource.name}</span>
        </span>
      </Link>
    )
  }
  if (lesson.lessonType === 'external_link' && lesson.externalUrl) {
    return (
      <a href={lesson.externalUrl} target="_blank" rel="noopener noreferrer" className="mt-8 inline-flex items-center gap-2 font-semibold text-burgundy-600 hover:underline">
        Open the linked page <ExternalLink size={16} aria-hidden="true" />
      </a>
    )
  }
  return null
}

function LessonBody({ lesson }) {
  const video = lesson.lessonType === 'video' || lesson.lessonType === 'recording'
  return (
    <>
      {video && lesson.externalUrl && (
        <div className="mt-8">
          <VideoEmbed
            title={lesson.title}
            url={lesson.externalUrl}
            embedUrl={lesson.embedUrl}
            provider={lesson.videoProvider}
            transcript={lesson.transcript}
            captionsUrl={lesson.captionsUrl}
            thumbnail={lesson.thumbnail}
          />
        </div>
      )}
      {lesson.content?.length > 0 && (
        <div className="mt-6">
          <ArticleContent variant="article" blocks={lesson.content} extraRenderers={LEARNING_RENDERERS} rendererProps={{ lessonId: lesson.id }} />
        </div>
      )}
      <LinkedLesson lesson={lesson} />
      {video && lesson.resource && (
        <Link to={`/resources/${lesson.resource.slug}`} className="mt-6 inline-block font-semibold text-burgundy-600 hover:underline">
          Slides and handout: {lesson.resource.name}
        </Link>
      )}
    </>
  )
}

export default function LearningLessonPage() {
  const { slug, lessonId } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const course = useCourse(slug)
  const { program, error, enrollment, modules, canReadLessons, signedIn } = course
  const [saving, setSaving] = useState(false)
  const neighbors = lessonNeighbors(modules, lessonId)
  const lesson = neighbors.current?.lesson || null

  useSeo(
    program
      ? {
          title: `${lesson?.title ? `${lesson.title} · ` : ''}${program.title} | WSF Learning`,
          canonical: `https://womenshapingfutures.org/learning/${program.slug}`,
          robots: 'noindex, follow',
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this lesson" description={error} /></div>
  if (program === undefined) return <PageLoader />
  if (program === null) return <NotFoundPage />
  if (!neighbors.current) return <NotFoundPage />

  const completedIds = enrollment?.status === 'active' ? enrollment.completedLessonIds : []
  const isComplete = completedIds.includes(lesson.id)
  const tracking = enrollment?.status === 'active'
  const lessonUrl = (id) => `/learning/${program.slug}/lessons/${id}`
  const moduleLabel = `Module ${neighbors.current.moduleIndex + 1}`

  async function toggleComplete() {
    setSaving(true)
    try {
      const updated = await course.setLessonComplete(lesson.id, !isComplete)
      if (!isComplete) {
        trackEvent('learning_lesson_completed', { programSlug: program.slug, lessonId: lesson.id })
        if (updated?.completedAt && !enrollment.completedAt) {
          trackEvent('learning_program_completed', { programSlug: program.slug })
          toast.success('Course complete. Well done!')
          navigate(`/learning/${program.slug}`)
        }
      }
    } catch {
      toast.error('Something went wrong. Please try again.')
    } finally {
      setSaving(false)
    }
  }

  async function startTracking() {
    try {
      await course.enroll()
      trackEvent('learning_enrollment_started', { programSlug: program.slug })
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    }
  }

  const curriculum = (onNavigate) => (
    <CourseCurriculum
      variant="sidebar"
      programSlug={program.slug}
      modules={modules}
      completedIds={completedIds}
      currentLessonId={lesson.id}
      canReadLessons={canReadLessons}
      openModuleIndex={neighbors.current.moduleIndex ?? currentModuleIndex(modules, completedIds)}
      onNavigate={onNavigate}
    />
  )

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Learning', to: '/learning' }, { label: program.title, to: `/learning/${program.slug}` }, { label: lesson.title }]} />
      </div>

      <div className="container-editorial grid grid-cols-1 gap-10 pb-20 pt-6 lg:grid-cols-[minmax(0,1fr)_320px] xl:gap-14">
        <article className="min-w-0 max-w-[720px]">
          {/* Mobile/tablet: compact progress + collapsible course outline. */}
          <div className="mb-6 space-y-3 lg:hidden">
            {tracking && <CourseProgress enrollment={enrollment} compact />}
            <details className="group rounded-card border border-taupe-200 bg-white">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-charcoal [&::-webkit-details-marker]:hidden">
                <span className="inline-flex items-center gap-2"><ListTree size={16} aria-hidden="true" /> Course content</span>
                <span className="text-xs font-normal text-charcoal-600">Lesson {neighbors.position} of {neighbors.total}</span>
              </summary>
              <div className="border-t border-taupe-200 px-3 py-2">
                {curriculum((e) => e.currentTarget.closest('details')?.removeAttribute('open'))}
              </div>
            </details>
          </div>

          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">
            {moduleLabel} · {neighbors.current.module.title}
          </p>
          <h1 className="mt-3 font-serif text-3xl font-semibold leading-tight text-charcoal sm:text-[2.5rem]">{lesson.title}</h1>
          <p className="mt-3 text-sm text-charcoal-600">
            {[`Lesson ${neighbors.position} of ${neighbors.total}`, LESSON_TYPE_LABEL[lesson.lessonType], formatMinutes(lesson.durationMinutes)].filter(Boolean).join(' · ')}
          </p>
          {lesson.summary && <p className="mt-5 text-xl leading-relaxed text-charcoal-600">{lesson.summary}</p>}

          {canReadLessons ? (
            <LessonBody lesson={lesson} />
          ) : (
            <div className="mt-8 rounded-card border border-taupe-200 bg-cream p-6">
              <p className="font-serif text-xl font-semibold text-charcoal">This lesson opens once you start the course.</p>
              <p className="mt-2 text-sm text-charcoal-600">See what&apos;s included and how to get access on the course page.</p>
              <Link to={`/learning/${program.slug}`} className="btn-primary mt-4">Go to the course</Link>
            </div>
          )}

          {canReadLessons && (
            <div className="mt-12 rounded-card border border-taupe-200 bg-white p-5">
              {tracking ? (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-charcoal-600">{isComplete ? 'You’ve completed this lesson.' : 'Finished reading? Mark it complete to track your progress.'}</p>
                  <button
                    type="button"
                    onClick={toggleComplete}
                    disabled={saving}
                    aria-pressed={isComplete}
                    className={`${isComplete ? 'btn-secondary' : 'btn-primary'} !py-2.5 disabled:opacity-60`}
                  >
                    {isComplete ? <CheckCircle2 size={16} aria-hidden="true" /> : <Circle size={16} aria-hidden="true" />}
                    {isComplete ? 'Completed — undo' : 'Mark complete'}
                  </button>
                </div>
              ) : signedIn ? (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-charcoal-600">Start the course to save your progress and earn any certificate.</p>
                  <button type="button" onClick={startTracking} disabled={course.busy} className="btn-primary !py-2.5 disabled:opacity-60">Start tracking</button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-sm text-charcoal-600">Sign in to save your progress.</p>
                  <button type="button" onClick={() => navigate('/login', { state: { from: location.pathname } })} className="btn-secondary !py-2.5">Sign in</button>
                </div>
              )}
            </div>
          )}

          <nav aria-label="Lesson navigation" className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-2">
            {neighbors.prev ? (
              <Link to={lessonUrl(neighbors.prev.lesson.id)} className="group rounded-card border border-taupe-200 bg-white p-4 hover:border-burgundy-500">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600"><ArrowLeft size={14} aria-hidden="true" /> Previous lesson</span>
                <span className="mt-1 block font-medium text-charcoal group-hover:text-burgundy-600">{neighbors.prev.lesson.title}</span>
              </Link>
            ) : (
              <Link to={`/learning/${program.slug}`} className="group rounded-card border border-taupe-200 bg-white p-4 hover:border-burgundy-500">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-charcoal-600"><ArrowLeft size={14} aria-hidden="true" /> Course overview</span>
                <span className="mt-1 block font-medium text-charcoal group-hover:text-burgundy-600">{program.title}</span>
              </Link>
            )}
            {neighbors.next ? (
              <Link to={lessonUrl(neighbors.next.lesson.id)} className="group rounded-card border border-plum-600 bg-plum-600 p-4 text-right text-ivory hover:bg-plum-700 sm:col-start-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ivory/80">Next lesson <ArrowRight size={14} aria-hidden="true" /></span>
                <span className="mt-1 block font-medium">{neighbors.next.lesson.title}</span>
              </Link>
            ) : (
              <Link to={`/learning/${program.slug}`} className="group rounded-card border border-plum-600 bg-plum-600 p-4 text-right text-ivory hover:bg-plum-700 sm:col-start-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-ivory/80">End of course <ArrowRight size={14} aria-hidden="true" /></span>
                <span className="mt-1 block font-medium">{program.assessment ? 'Final assessment and course summary' : 'Back to the course page'}</span>
              </Link>
            )}
          </nav>
        </article>

        <aside className="hidden lg:block" aria-label="Course progress and content">
          <div className="sticky top-24 max-h-[calc(100vh-7rem)] space-y-5 overflow-y-auto pb-4 pr-1">
            <Link to={`/learning/${program.slug}`} className="block font-serif text-lg font-semibold leading-snug text-charcoal hover:text-burgundy-600">{program.title}</Link>
            {tracking && <CourseProgress enrollment={enrollment} />}
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">Course content</p>
              {curriculum()}
            </div>
          </div>
        </aside>
      </div>
    </div>
  )
}
