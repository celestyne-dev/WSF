import { useParams, useNavigate, useLocation, Link } from 'react-router-dom'
import { toast } from 'react-toastify'
import { Award, BookOpen, Check, Clock, ExternalLink, FileText, Gauge, Layers, ListChecks, Route } from 'lucide-react'
import useCourse from '../hooks/useCourse'
import { resolveImage } from '../utils/media'
import { formatDate } from '../utils/format'
import { trackEvent } from '../utils/analytics'
import { LEVEL_LABEL, PROGRAM_TYPE_LABEL, currentModuleIndex, formatMinutes, nextIncompleteLesson, programMetaLines } from '../utils/learning'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import SaveButton from '../components/account/SaveButton'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'
import CourseCurriculum from '../components/learning/CourseCurriculum'
import CourseProgress from '../components/learning/CourseProgress'
import CourseCompletion from '../components/learning/CourseCompletion'
import FinalAssessment from '../components/learning/FinalAssessment'
import LifetimeValueNote from '../components/learning/LifetimeValueNote'
import useLifetimeOffer from '../hooks/useLifetimeOffer'
import { premiumCourseState, programAccessLabel } from '../utils/learningAccess'
import CollectionNotice from '../components/legal/CollectionNotice'

// The primary call to action, from the backend's own access answers.
function CourseCta({ course, program, onSignIn }) {
  const { enrollment, enroll, busy, modules, canReadLessons, accessDenied, signedIn } = course
  const navigate = useNavigate()
  const { available: lifetimeOnSale } = useLifetimeOffer(program.accessType === 'product' && program.lifetimeIncluded && program.viewerCanAccess !== true)
  const firstLesson = nextIncompleteLesson(modules, [])?.lesson || null
  const nextLessonId = enrollment?.nextLessonId || firstLesson?.id

  async function start() {
    try {
      const created = await enroll()
      trackEvent('learning_enrollment_started', { programSlug: program.slug })
      if (program.accessType === 'product') trackEvent('lifetime_course_enrollment', { programSlug: program.slug })
      const target = created?.nextLessonId || firstLesson?.id
      if (target) navigate(`/learning/${program.slug}/lessons/${target}`)
      else toast.success(`You're enrolled in ${program.title}.`)
    } catch (err) {
      toast.error(err?.response?.data?.error?.message || 'Something went wrong. Please try again.')
    }
  }

  if (program.accessType === 'external') {
    return program.externalUrl ? (
      <a href={program.externalUrl} target="_blank" rel="noopener noreferrer" className="btn-primary">
        Enroll with the provider <ExternalLink size={16} aria-hidden="true" />
      </a>
    ) : null
  }

  // Premium (product) course without access: WSF Lifetime is the only way
  // in for this launch. Never a "Buy" link to the linked Product: a Product
  // purchase does not unlock Learning (see utils/learningAccess.js).
  const premium = premiumCourseState(program, { lifetimeOnSale })
  if (premium === 'lifetime') {
    return (
      <Link to="/lifetime" className="btn-primary">
        Get WSF Lifetime
      </Link>
    )
  }
  if (premium === 'info') return <p className="text-sm font-semibold text-plum-600">Available with WSF Lifetime</p>
  if (premium === 'unavailable') return <p className="text-sm text-charcoal-600">This premium course isn&rsquo;t open for enrollment yet.</p>

  if (program.accessType === 'circle_only' && (!program.viewerCanAccess || accessDenied)) {
    return signedIn ? (
      <Link to="/circle" className="btn-primary">Explore WSF Circle</Link>
    ) : (
      <button type="button" onClick={onSignIn} className="btn-primary">Sign in to start</button>
    )
  }

  // free, circle_only with access, or an eligible course for a Lifetime member.
  if (enrollment === undefined && signedIn) return <span className="text-sm text-charcoal-600">Checking your progress…</span>
  if (enrollment && enrollment.status === 'active') {
    if (enrollment.completedAt) {
      return firstLesson ? (
        <Link to={`/learning/${program.slug}/lessons/${firstLesson.id}`} className="btn-secondary">Review the course</Link>
      ) : null
    }
    return canReadLessons && nextLessonId ? (
      <Link to={`/learning/${program.slug}/lessons/${nextLessonId}`} className="btn-primary">
        {enrollment.completedLessons > 0 ? 'Continue learning' : 'Start course'} <span aria-hidden="true">→</span>
      </Link>
    ) : (
      <span className="text-sm text-charcoal-600">Loading your lessons…</span>
    )
  }
  if (!signedIn) {
    // Free courses can be read without an account; signing in adds progress.
    return (
      <div className="flex flex-wrap items-center gap-3">
        {program.accessType === 'free' && firstLesson && (
          <Link to={`/learning/${program.slug}/lessons/${firstLesson.id}`} className="btn-primary">Start reading</Link>
        )}
        <button type="button" onClick={onSignIn} className={program.accessType === 'free' ? 'btn-secondary' : 'btn-primary'}>
          Sign in to track progress
        </button>
      </div>
    )
  }
  return (
    <div>
      <button type="button" onClick={start} disabled={busy} className="btn-primary disabled:opacity-60">
        {busy ? 'Please wait…' : enrollment?.status === 'withdrawn' ? 'Resume course' : 'Start course'}
      </button>
      <CollectionNotice kind="learningEnrolment" className="mt-2 max-w-md" />
    </div>
  )
}

function Fact({ icon: Icon, label, value }) {
  if (!value) return null
  return (
    <li className="flex items-start gap-3 py-2.5">
      <Icon size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-plum-600" />
      <span className="min-w-0">
        <span className="block text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</span>
        <span className="block text-[15px] text-charcoal">{value}</span>
      </span>
    </li>
  )
}

export default function LearningProgramDetailPage() {
  const { slug } = useParams()
  const navigate = useNavigate()
  const location = useLocation()
  const course = useCourse(slug)
  const { program, error, enrollment, modules, canReadLessons } = course

  const canonicalUrl = program ? `https://womenshapingfutures.org/learning/${program.slug}` : ''
  useSeo(
    program
      ? {
          title: program.seo?.title || `${program.title} | Women Shaping Futures Learning`,
          description: program.seo?.description || program.shortDescription || program.subtitle || program.title,
          canonical: program.seo?.canonical || canonicalUrl,
          image: program.heroMedia?.mediaPath ? resolveImage(program.heroMedia.mediaPath, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )
  useBreadcrumbStructuredData(program ? [{ label: 'Learning', to: '/learning' }, { label: program.title }] : null, program?.seo?.canonical || canonicalUrl)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this course" description={error} /></div>
  if (program === undefined) return <PageLoader />
  if (program === null) return <NotFoundPage />

  const [metaFirst, metaSecond] = programMetaLines(program)
  const completedIds = enrollment?.status === 'active' ? enrollment.completedLessonIds : []
  const openModule = currentModuleIndex(modules, completedIds)
  const stats = program.stats || {}
  const instructors = [program.primaryInstructor, ...(program.coInstructors || [])].filter(Boolean)
  const upcomingEvent = program.events?.[0] || null
  const onSignIn = () => navigate('/login', { state: { from: location.pathname } })
  const lifetimeViewer = program.viewerMembershipLabel && /lifetime/i.test(program.viewerMembershipLabel)

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Learning', to: '/learning' }, { label: program.title }]} />
      </div>

      <header className="container-editorial pb-10 pt-8">
        <div className={`grid grid-cols-1 gap-10 ${program.heroMedia ? 'lg:grid-cols-[minmax(0,1fr)_420px]' : ''}`}>
          <div className="min-w-0 max-w-3xl">
            <div className="flex items-start justify-between gap-4">
              <p className="eyebrow">{PROGRAM_TYPE_LABEL[program.programType] || 'Course'}</p>
              <SaveButton contentType="learning_program" contentId={program.id} />
            </div>
            <h1 className="mt-3 font-serif text-[2.25rem] font-semibold leading-[1.1] text-charcoal sm:text-5xl">{program.title}</h1>
            {program.subtitle && <p className="mt-4 text-lg leading-relaxed text-charcoal-600 sm:text-xl">{program.subtitle}</p>}

            {metaFirst.length > 0 && <p className="mt-5 text-sm font-semibold text-charcoal">{metaFirst.join(' · ')}</p>}
            {metaSecond.length > 0 && <p className="mt-1 text-sm text-charcoal-600">{metaSecond.join(' · ')}</p>}

            {instructors.length > 0 && (
              <p className="mt-4 text-sm text-charcoal-600">
                Taught by{' '}
                {instructors.map((person, i) => (
                  <span key={person.slug || person.name}>
                    {i > 0 && (i === instructors.length - 1 ? ' and ' : ', ')}
                    {person.slug ? (
                      <Link to={`/authors/${person.slug}`} className="font-semibold text-charcoal hover:text-burgundy-600">{person.name}</Link>
                    ) : (
                      person.name
                    )}
                  </span>
                ))}
                {program.providerOrganization && <> · Provided by {program.providerOrganization.name}</>}
              </p>
            )}

            <div className="mt-6 flex flex-wrap items-center gap-x-4 gap-y-2">
              {!lifetimeViewer && programAccessLabel(program) && <p className="text-lg font-semibold text-charcoal">{programAccessLabel(program)}</p>}
              <LifetimeValueNote included={program.lifetimeIncluded && program.accessType !== 'free'} viewerLabel={program.viewerMembershipLabel} />
            </div>
            {program.circleInclusion?.included && program.accessType === 'circle_only' && !program.viewerMembershipLabel && program.circleInclusion.label && (
              <p className="mt-1 text-sm text-charcoal-600">{program.circleInclusion.label}</p>
            )}

            <div className="mt-6">
              <CourseCta course={course} program={program} onSignIn={onSignIn} />
            </div>

            {enrollment?.status === 'active' && !enrollment.completedAt && (
              <div className="mt-6 max-w-md">
                <CourseProgress enrollment={enrollment} />
              </div>
            )}

            {upcomingEvent && (
              <p className="mt-6 text-sm text-charcoal-600">
                Next live session: <span className="font-semibold text-charcoal">{formatDate(upcomingEvent.date)}</span> ·{' '}
                <Link to={`/events/${upcomingEvent.slug}`} className="font-semibold text-burgundy-600 hover:underline">Event details</Link>
              </p>
            )}
            <div className="mt-6">
              <ShareBar title={program.title} url={canonicalUrl} trackEventName="learning_share_click" trackPayload={{ programSlug: program.slug }} />
            </div>
          </div>
          {program.heroMedia && (
            <div className="order-first lg:order-none">
              <MediaImage media={program.heroMedia} variant="medium" alt="" width={840} height={630} aspect={4 / 3} priority className="w-full rounded-media object-cover" />
            </div>
          )}
        </div>
      </header>

      <div className="container-editorial grid grid-cols-1 gap-12 pb-16 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 max-w-[760px] space-y-12">
          {enrollment?.completedAt && <CourseCompletion program={program} enrollment={enrollment} />}

          {program.learningOutcomes?.length > 0 && (
            <section aria-labelledby="outcomes-title" className="rounded-card border border-taupe-200 bg-white p-6 sm:p-7">
              <h2 id="outcomes-title" className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">What you&apos;ll learn</h2>
              <ul className="mt-4 grid gap-3 sm:grid-cols-2">
                {program.learningOutcomes.map((outcome, i) => (
                  <li key={i} className="flex items-start gap-2.5 text-[15px] leading-snug text-charcoal">
                    <Check size={18} aria-hidden="true" className="mt-0.5 shrink-0 text-plum-600" />
                    {outcome}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {program.skills?.length > 0 && (
            <section aria-labelledby="skills-title">
              <h2 id="skills-title" className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">Skills you&apos;ll build</h2>
              <ul className="mt-3 flex flex-wrap gap-2">
                {program.skills.map((skill) => (
                  <li key={skill} className="rounded-full border border-taupe-300 bg-white px-3 py-1 text-sm text-charcoal">{skill}</li>
                ))}
              </ul>
            </section>
          )}

          {program.overview?.length > 0 && (
            <section aria-labelledby="about-title">
              <h2 id="about-title" className="font-serif text-2xl font-semibold text-charcoal">About this course</h2>
              <ArticleContent blocks={program.overview} />
            </section>
          )}

          {modules.length > 0 && (
            <section id="curriculum" aria-labelledby="curriculum-title" className="scroll-mt-28">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <h2 id="curriculum-title" className="font-serif text-2xl font-semibold text-charcoal">Course content</h2>
                <p className="text-sm text-charcoal-600">
                  {[stats.moduleCount && `${stats.moduleCount} modules`, stats.lessonCount && `${stats.lessonCount} lessons`, stats.totalMinutes && formatMinutes(stats.totalMinutes)].filter(Boolean).join(' · ')}
                </p>
              </div>
              {!canReadLessons && program.accessType !== 'external' && (
                <p className="mt-2 text-sm text-charcoal-600">
                  {program.accessType === 'circle_only' ? 'Lessons open once you start the course as a WSF Circle member.' : 'Lessons open once you have access to this course.'}
                </p>
              )}
              <div className="mt-4">
                <CourseCurriculum programSlug={program.slug} modules={modules} completedIds={completedIds} canReadLessons={canReadLessons} openModuleIndex={openModule} />
              </div>
            </section>
          )}

          {canReadLessons && enrollment?.finalAssessment && <FinalAssessment enrollment={enrollment} onEnrollmentChange={course.setEnrollment} />}

          {program.prerequisites?.length > 0 && (
            <section aria-labelledby="prereq-title">
              <h2 id="prereq-title" className="font-serif text-xl font-semibold text-charcoal">Before you start</h2>
              <ul className="mt-3 list-disc space-y-1.5 pl-5 text-[15px] text-charcoal-600">
                {program.prerequisites.map((p, i) => (
                  <li key={i}>{p}</li>
                ))}
              </ul>
            </section>
          )}

          {(program.relatedArticles?.length > 0 || program.relatedResources?.length > 0) && (
            <section aria-labelledby="related-title" className="border-t border-taupe-200 pt-8">
              <h2 id="related-title" className="font-serif text-xl font-semibold text-charcoal">Related reading and tools</h2>
              <ul className="mt-3 space-y-2">
                {program.relatedArticles.map((a) => (
                  <li key={`a-${a.id}`}><Link to={`/${a.slug}`} className="font-medium text-burgundy-600 hover:underline">{a.title}</Link></li>
                ))}
                {program.relatedResources.map((r) => (
                  <li key={`r-${r.id}`}><Link to={`/resources/${r.slug}`} className="font-medium text-burgundy-600 hover:underline">{r.name}</Link></li>
                ))}
              </ul>
            </section>
          )}
        </div>

        <aside className="space-y-6 lg:sticky lg:top-24 lg:self-start" aria-label="Course details">
          <div className="rounded-card border border-taupe-200 bg-white p-5">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">This course includes</p>
            <ul className="mt-2 divide-y divide-taupe-100">
              <Fact icon={FileText} label="Format" value={[program.deliveryMode === 'self_paced' ? 'Self-paced' : null, stats.formatLabel].filter(Boolean).join(' · ')} />
              <Fact icon={Layers} label="Content" value={[stats.moduleCount && `${stats.moduleCount} modules`, stats.lessonCount && `${stats.lessonCount} lessons`].filter(Boolean).join(' · ')} />
              <Fact icon={Clock} label="Estimated time" value={stats.totalMinutes ? `Approx. ${formatMinutes(stats.totalMinutes)}` : program.durationValue ? `${program.durationValue} ${program.durationUnit || ''}` : null} />
              <Fact icon={Gauge} label="Level" value={LEVEL_LABEL[program.difficultyLevel]} />
              <Fact icon={ListChecks} label="Final assessment" value={program.assessment ? `${program.assessment.questionCount} questions · pass mark ${program.assessment.passingScore}%` : null} />
              <Fact icon={Award} label="Certificate" value={program.certificateAvailable ? 'Certificate of Completion' : null} />
              <Fact icon={BookOpen} label="Access" value={programAccessLabel(program)} />
            </ul>
          </div>
          {program.learningPaths?.length > 0 && (
            <div className="rounded-card border border-taupe-200 bg-cream p-5">
              <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">
                <Route size={14} aria-hidden="true" /> Part of a learning path
              </p>
              <ul className="mt-2 space-y-1.5">
                {program.learningPaths.map((path) => (
                  <li key={path.slug}><Link to={`/learning/paths/${path.slug}`} className="font-serif text-lg font-semibold text-charcoal hover:text-burgundy-600">{path.title}</Link></li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  )
}
