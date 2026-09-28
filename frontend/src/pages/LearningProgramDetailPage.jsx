import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { ExternalLink, FileText, PlayCircle, BookOpen, ClipboardList } from 'lucide-react'
import { fetchLearningProgramBySlug } from '../api/learning'
import { resolveImage } from '../utils/media'
import { formatCurrency, formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ShareBar from '../components/ui/ShareBar'
import NewsletterForm from '../components/ui/NewsletterForm'
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

function LessonRow({ lesson }) {
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

  return (
    <li className="flex items-start gap-3 py-2.5">
      <Icon size={16} className="mt-0.5 shrink-0 text-charcoal-600" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        {content}
        {lesson.summary && <p className="mt-0.5 text-xs text-charcoal-600/80">{lesson.summary}</p>}
      </div>
      {lesson.durationMinutes ? <span className="shrink-0 text-xs text-charcoal-600/70">{lesson.durationMinutes} min</span> : null}
    </li>
  )
}

function ModuleAccordion({ module, index }) {
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
              <LessonRow key={lesson.id} lesson={lesson} />
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
  // Free access with no external URL and no linked Product: there is
  // nothing to gate — the curriculum itself is the offering, so no fake
  // "Start course" button is shown pointing nowhere (spec: "no fake
  // gating" — this app has no learner accounts/lesson-access system).
  return null
}

export default function LearningProgramDetailPage() {
  const { slug } = useParams()
  const [program, setProgram] = useState(undefined)
  const [error, setError] = useState(null)

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
          <div className="flex flex-wrap items-center gap-2">
            <span className="eyebrow">{PROGRAM_TYPE_LABEL[program.programType] || program.programType}</span>
            {program.difficultyLevel && <span className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">· {program.difficultyLevel.replace('_', ' ')}</span>}
            {program.featured && <span className="bg-burgundy-600 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>}
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
            <CtaButton program={program} />
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

      {program.modules?.length > 0 && (
        <div className="container-editorial max-w-reading pb-10">
          <h2 className="font-serif text-xl font-semibold text-charcoal">Curriculum</h2>
          <div className="mt-4 space-y-3">
            {program.modules.map((module, i) => (
              <ModuleAccordion key={module.id} module={module} index={i} />
            ))}
          </div>
        </div>
      )}

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
