import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CheckCircle2, Circle, CircleDot } from 'lucide-react'
import { fetchLearningPathBySlug } from '../api/learningPaths'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import { resolveImage } from '../utils/media'
import { LEVEL_LABEL, formatMinutes, programMetaLines } from '../utils/learning'
import Breadcrumb from '../components/ui/Breadcrumb'
import ArticleContent from '../components/article/ArticleContent'
import MediaImage from '../components/ui/MediaImage'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import LifetimeValueNote from '../components/learning/LifetimeValueNote'
import NotFoundPage from './NotFoundPage'

const STATE = {
  completed: { label: 'Completed', icon: CheckCircle2, className: 'text-emerald-700' },
  in_progress: { label: 'In progress', icon: CircleDot, className: 'text-burgundy-600' },
  not_started: { label: 'Not started', icon: Circle, className: 'text-charcoal-600/60' },
}

export default function LearningPathDetailPage() {
  const { slug } = useParams()
  const [loaded, setLoaded] = useState({ slug: null, path: undefined, error: null })

  useEffect(() => {
    let active = true
    fetchLearningPathBySlug(slug)
      .then((path) => active && setLoaded({ slug, path, error: null }))
      .catch(() => active && setLoaded({ slug, path: undefined, error: 'Something went wrong loading this learning path. Please try again.' }))
    return () => {
      active = false
    }
  }, [slug])

  const path = loaded.slug === slug ? loaded.path : undefined
  const error = loaded.slug === slug ? loaded.error : null
  const canonical = `https://womenshapingfutures.org/learning/paths/${slug}`
  useSeo(
    path
      ? {
          title: path.seo?.title || `${path.title} | WSF Learning Paths`,
          description: path.seo?.description || path.shortDescription || path.subtitle || path.title,
          canonical,
          image: path.heroMedia?.mediaPath ? resolveImage(path.heroMedia.mediaPath, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )
  useBreadcrumbStructuredData(path ? [{ label: 'Learning', to: '/learning' }, { label: 'Learning Paths', to: '/learning/paths' }, { label: path.title }] : null, canonical)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this learning path" description={error} /></div>
  if (path === undefined) return <PageLoader />
  if (path === null) return <NotFoundPage />

  const progress = path.viewerProgress
  const stateFor = Object.fromEntries((progress?.courses || []).map((c) => [c.slug, c]))
  const nextSlug = progress?.nextProgramSlug
  const facts = [`${path.courseCount} course${path.courseCount === 1 ? '' : 's'}`, path.totalMinutes ? `Approx. ${formatMinutes(path.totalMinutes)}` : null, LEVEL_LABEL[path.difficultyLevel]].filter(Boolean)

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Learning', to: '/learning' }, { label: 'Learning Paths', to: '/learning/paths' }, { label: path.title }]} />
      </div>
      <header className="container-editorial pb-10 pt-8">
        <div className={`grid gap-10 ${path.heroMedia ? 'lg:grid-cols-[minmax(0,1fr)_420px]' : ''}`}>
          <div className="max-w-3xl">
            <p className="eyebrow">Learning Path{path.careerGoal ? ` · ${path.careerGoal.label}` : ''}</p>
            <h1 className="mt-3 font-serif text-[2.25rem] font-semibold leading-[1.1] text-charcoal sm:text-5xl">{path.title}</h1>
            {path.subtitle && <p className="mt-4 text-lg text-charcoal-600 sm:text-xl">{path.subtitle}</p>}
            <p className="mt-5 text-sm font-semibold text-charcoal">{facts.join(' · ')}</p>
            <div className="mt-4">
              <LifetimeValueNote
                included={path.lifetimeIncluded}
                viewerLabel={path.viewerIsLifetime ? 'All courses included in your Lifetime membership' : null}
              />
            </div>
            {progress && (
              <div className="mt-6 max-w-md rounded-card border border-taupe-200 bg-white p-4">
                <div className="flex items-baseline justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">Your path progress</p>
                  <p className="font-serif text-2xl font-semibold text-charcoal">{progress.progressPercent}%</p>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-taupe-100" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress.progressPercent} aria-label={`Path progress: ${progress.progressPercent}%`}>
                  <div className="h-full rounded-full bg-plum-600" style={{ width: `${progress.progressPercent}%` }} />
                </div>
                <p className="mt-2 text-sm text-charcoal-600">{progress.completedCourses} of {progress.totalCourses} courses complete</p>
              </div>
            )}
            {nextSlug ? (
              <Link to={`/learning/${nextSlug}`} className="btn-primary mt-6">
                {progress?.completedCourses || progress?.inProgressCourses ? 'Continue path' : 'Start path'} <span aria-hidden="true">→</span>
              </Link>
            ) : progress ? (
              <p className="mt-6 inline-flex items-center gap-2 font-semibold text-emerald-700"><CheckCircle2 size={18} aria-hidden="true" /> Path complete</p>
            ) : (
              path.courses[0] && <Link to={`/learning/${path.courses[0].slug}`} className="btn-primary mt-6">Start with course 1 <span aria-hidden="true">→</span></Link>
            )}
          </div>
          {path.heroMedia && <MediaImage media={path.heroMedia} variant="medium" alt="" width={840} height={472} aspect={16 / 9} priority className="w-full rounded-media object-cover" />}
        </div>
      </header>

      <div className="container-editorial max-w-[860px] pb-20">
        {path.shortDescription && <p className="text-lg leading-relaxed text-charcoal">{path.shortDescription}</p>}
        {path.description?.length > 0 && <ArticleContent blocks={path.description} />}

        <section aria-labelledby="path-courses-title" className="mt-10">
          <h2 id="path-courses-title" className="font-serif text-2xl font-semibold text-charcoal">Courses in this path</h2>
          <ol className="mt-5 space-y-4">
            {path.courses.map((course, i) => {
              const state = stateFor[course.slug]
              const meta = STATE[state?.state] || null
              const Icon = meta?.icon
              const [first, second] = programMetaLines(course)
              return (
                <li key={course.id} className={`rounded-card border bg-white p-5 sm:p-6 ${course.slug === nextSlug ? 'border-plum-600' : 'border-taupe-200'}`}>
                  <div className="flex items-start gap-4">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-cream font-serif text-lg font-semibold text-charcoal" aria-hidden="true">{i + 1}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">
                        <span className="sr-only">Course {i + 1}: </span>
                        {[...first, ...second].join(' · ')}
                      </p>
                      <Link to={`/learning/${course.slug}`} className="mt-1 block font-serif text-xl font-semibold text-charcoal hover:text-burgundy-600">{course.title}</Link>
                      {course.shortDescription && <p className="mt-1 text-sm text-charcoal-600">{course.shortDescription}</p>}
                      {meta && (
                        <p className={`mt-2 inline-flex items-center gap-1.5 text-sm font-semibold ${meta.className}`}>
                          <Icon size={16} aria-hidden="true" /> {meta.label}
                          {state.state === 'in_progress' && ` · ${state.progressPercent}%`}
                          {course.slug === nextSlug && <span className="ml-1 text-burgundy-600">· Up next</span>}
                        </p>
                      )}
                    </div>
                  </div>
                </li>
              )
            })}
          </ol>
          <p className="mt-4 text-sm text-charcoal-600">Each course awards its own Certificate of Completion where available.</p>
        </section>
      </div>
    </div>
  )
}
