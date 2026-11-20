import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { ArrowRight, BookOpen, Clock, Infinity as InfinityIcon, Search, Smartphone } from 'lucide-react'
import { fetchLearningFacets, fetchLearningPrograms } from '../api/learning'
import { fetchLearningPaths, fetchRecommendedLearningPaths } from '../api/learningPaths'
import { fetchMyLearningEnrollments } from '../api/learningEnrollments'
import { CAREER_GOAL_OPTIONS } from '../constants/careerMetadata'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import useLifetimeOffer from '../hooks/useLifetimeOffer'
import FilterSelect from '../components/ui/FilterSelect'
import LearningProgramCard from '../components/cards/LearningProgramCard'
import LearningPathCard from '../components/cards/LearningPathCard'
import NewsletterForm from '../components/ui/NewsletterForm'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import { LEVEL_LABEL } from '../utils/learning'

const GOAL_LABEL = Object.fromEntries(CAREER_GOAL_OPTIONS.map((o) => [o.value, o.label]))
const FORMAT_LABEL = { text: 'Text-based', mixed: 'Mixed format', video_led: 'Video-led' }
const ACCESS_OPTIONS = [
  { value: 'free', label: 'Free' },
  { value: 'circle_only', label: 'WSF Circle' },
  { value: 'product', label: 'Premium' },
]
const LEVEL_OPTIONS = Object.entries(LEVEL_LABEL).map(([value, label]) => ({ value, label }))

const LEARNING_INDEX_COPY = {
  eyebrow: 'WSF Learning',
  title: 'Build the skills to move your career forward.',
  lead: 'Self-paced, text-first courses and guided learning paths — practical, mobile-friendly, and easy to finish in short sessions.',
}

function Section({ id, title, action, children }) {
  return (
    <section id={id} aria-labelledby={`${id}-title`} className="scroll-mt-24 border-t border-taupe-200 py-12">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h2 id={`${id}-title`} className="font-serif text-2xl font-semibold text-charcoal sm:text-3xl">{title}</h2>
        {action}
      </div>
      <div className="mt-6">{children}</div>
    </section>
  )
}

function ContinueCard({ enrollment }) {
  const program = enrollment.program
  const target = enrollment.nextLessonId ? `/learning/${program.slug}/lessons/${enrollment.nextLessonId}` : `/learning/${program.slug}`
  const percent = Math.round(enrollment.progressPercent || 0)
  return (
    <Link to={target} className="group flex h-full flex-col rounded-card border border-taupe-200 bg-white p-5 hover:border-burgundy-500">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-charcoal-600">Continue learning</p>
      <p className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal group-hover:text-burgundy-600">{program.title}</p>
      <div className="mt-auto pt-4">
        <div className="h-1.5 overflow-hidden rounded-full bg-taupe-100" aria-hidden="true">
          <div className="h-full rounded-full bg-plum-600" style={{ width: `${percent}%` }} />
        </div>
        <p className="mt-2 flex items-center justify-between text-sm text-charcoal-600">
          <span>{enrollment.completedLessons} of {enrollment.totalLessons} lessons · {percent}%</span>
          <span className="inline-flex items-center gap-1 font-semibold text-burgundy-600">Continue <ArrowRight size={14} aria-hidden="true" /></span>
        </p>
      </div>
    </Link>
  )
}

export default function LearningPage() {
  const accessToken = useSelector((s) => s.auth.accessToken)
  const [catalog, setCatalog] = useState(null)
  const [paths, setPaths] = useState([])
  const [facets, setFacets] = useState({ careerGoals: [], formats: [] })
  const [recommended, setRecommended] = useState(null)
  const [current, setCurrent] = useState([])
  const [filters, setFilters] = useState({ q: '', goal: '', difficultyLevel: '', format: '', accessType: '', topic: '' })
  const [results, setResults] = useState({ key: '', items: null, error: null })
  const lifetime = useLifetimeOffer()

  useSeo({
    title: 'WSF Learning | Women Shaping Futures',
    description: 'Self-paced, text-first courses and guided learning paths to build the skills that move your career forward.',
    canonical: 'https://womenshapingfutures.org/learning',
  })
  useBreadcrumbStructuredData([{ label: 'Learning' }], 'https://womenshapingfutures.org/learning')

  useEffect(() => {
    let active = true
    fetchLearningPrograms({ pageSize: 100 })
      .then((res) => active && setCatalog(res.items))
      .catch(() => active && setCatalog([]))
    fetchLearningPaths().then((items) => active && setPaths(items)).catch(() => {})
    fetchLearningFacets().then((f) => active && setFacets(f)).catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!accessToken) return undefined
    let active = true
    fetchMyLearningEnrollments({ state: 'current', perPage: 6 })
      .then((res) => active && setCurrent(res.items.filter((e) => e.program && e.programAvailable && e.canAccessCurriculum)))
      .catch(() => {})
    fetchRecommendedLearningPaths()
      .then((res) => active && setRecommended(res))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [accessToken])

  const filterKey = JSON.stringify(filters)
  const isFiltering = Object.values(filters).some(Boolean)
  useEffect(() => {
    if (!isFiltering) return undefined
    let active = true
    fetchLearningPrograms({ ...filters, pageSize: 100 })
      .then((res) => active && setResults({ key: filterKey, items: res.items, error: null }))
      .catch(() => active && setResults({ key: filterKey, items: null, error: 'Something went wrong loading courses. Please try again.' }))
    return () => {
      active = false
    }
  }, [filterKey, isFiltering, filters])

  const topics = useMemo(() => {
    const map = new Map()
    ;(catalog || []).forEach((p) => p.topics.forEach((t) => map.set(t.slug, t.name)))
    return [...map.entries()].map(([value, label]) => ({ value, label })).sort((a, b) => a.label.localeCompare(b.label))
  }, [catalog])
  const popular = (catalog || []).filter((p) => p.featured).slice(0, 4)
  const recent = [...(catalog || [])].sort((a, b) => String(b.publishedAt || b.createdAt || '').localeCompare(String(a.publishedAt || a.createdAt || ''))).slice(0, 4)
  const set = (key) => (value) => setFilters((f) => ({ ...f, [key]: value }))
  const shownResults = results.key === filterKey ? results : { items: null, error: null }

  return (
    <div>
      <section className="border-b border-taupe-200 bg-cream">
        <div className="container-editorial grid gap-10 py-14 sm:py-16 lg:grid-cols-[minmax(0,1fr)_340px] lg:items-end">
          <div className="max-w-2xl">
            <p className="eyebrow">{LEARNING_INDEX_COPY.eyebrow}</p>
            <h1 className="mt-3 font-serif text-4xl font-semibold leading-[1.08] text-charcoal sm:text-5xl">{LEARNING_INDEX_COPY.title}</h1>
            <p className="mt-4 text-lg leading-relaxed text-charcoal-600">{LEARNING_INDEX_COPY.lead}</p>
            <div className="mt-7 flex flex-wrap gap-3">
              {paths.length > 0 && <a href="#paths" className="btn-primary">Explore Learning Paths</a>}
              <a href="#courses" className={paths.length > 0 ? 'btn-secondary' : 'btn-primary'}>Browse courses</a>
            </div>
          </div>
          <ul className="grid gap-3 text-sm text-charcoal">
            <li className="flex items-start gap-3"><BookOpen size={18} aria-hidden="true" className="mt-0.5 text-plum-600" /> Read at your own pace — no video required</li>
            <li className="flex items-start gap-3"><Clock size={18} aria-hidden="true" className="mt-0.5 text-plum-600" /> Short lessons that fit a break or a commute</li>
            <li className="flex items-start gap-3"><Smartphone size={18} aria-hidden="true" className="mt-0.5 text-plum-600" /> Designed for your phone as much as your laptop</li>
          </ul>
        </div>
      </section>

      <div className="container-editorial">
        {current.length > 0 && (
          <Section id="continue" title="Continue learning" action={<Link to="/account/learning" className="text-sm font-semibold text-burgundy-600 hover:underline">My Learning</Link>}>
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
              {current.slice(0, 3).map((e) => <ContinueCard key={e.id} enrollment={e} />)}
            </div>
          </Section>
        )}

        {recommended?.items?.length > 0 && (
          <Section id="for-you" title="Recommended for your goals">
            <p className="-mt-3 mb-5 text-sm text-charcoal-600">Based on the career goals you chose: {recommended.goals.map((g) => g.label).join(', ')}.</p>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {recommended.items.map((p) => <LearningPathCard key={p.id} path={p} />)}
            </div>
          </Section>
        )}

        {paths.length > 0 && (
          <Section id="paths" title="Learning Paths" action={paths.length > 3 ? <Link to="/learning/paths" className="text-sm font-semibold text-burgundy-600 hover:underline">All learning paths</Link> : null}>
            <p className="-mt-3 mb-5 max-w-2xl text-sm text-charcoal-600">Guided career journeys: a few focused courses, in order, for one goal.</p>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {paths.slice(0, 3).map((p) => <LearningPathCard key={p.id} path={p} />)}
            </div>
          </Section>
        )}

        {!isFiltering && facets.careerGoals.length > 0 && (
          <Section id="goals" title="Learn by career goal">
            <ul className="flex flex-wrap gap-2">
              {facets.careerGoals.map((goal) => (
                <li key={goal}>
                  <button type="button" onClick={() => { set('goal')(goal); document.getElementById('courses')?.scrollIntoView({ behavior: 'smooth' }) }} className="rounded-full border border-taupe-300 bg-white px-4 py-2 text-sm font-medium text-charcoal hover:border-burgundy-500 hover:text-burgundy-600">
                    {GOAL_LABEL[goal] || goal}
                  </button>
                </li>
              ))}
            </ul>
          </Section>
        )}

        {!isFiltering && popular.length > 0 && (
          <Section id="popular" title="Popular courses">
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {popular.map((p) => <LearningProgramCard key={p.id} program={p} />)}
            </div>
          </Section>
        )}

        {!isFiltering && recent.length > 0 && (catalog || []).length > popular.length && (
          <Section id="new" title="New and recently added">
            <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
              {recent.map((p) => <LearningProgramCard key={p.id} program={p} />)}
            </div>
          </Section>
        )}

        <Section id="courses" title={isFiltering ? 'Matching courses' : 'All courses'}>
          <div className="flex flex-wrap items-center gap-3 pb-6">
            <label className="flex items-center gap-2 rounded-control border border-taupe-300 bg-white px-3 py-2.5">
              <Search size={16} aria-hidden="true" className="text-charcoal-600" />
              <span className="sr-only">Search courses</span>
              <input value={filters.q} onChange={(e) => set('q')(e.target.value)} placeholder="Search courses…" className="w-full min-w-0 text-sm focus:outline-none sm:w-56" />
            </label>
            {facets.careerGoals.length > 0 && (
              <FilterSelect label="Career goal" value={filters.goal} onChange={set('goal')} options={facets.careerGoals.map((g) => ({ value: g, label: GOAL_LABEL[g] || g }))} />
            )}
            {topics.length > 0 && <FilterSelect label="Topic" value={filters.topic} onChange={set('topic')} options={topics} />}
            <FilterSelect label="Level" value={filters.difficultyLevel} onChange={set('difficultyLevel')} options={LEVEL_OPTIONS} />
            {facets.formats.length > 0 && (
              <FilterSelect label="Format" value={filters.format} onChange={set('format')} options={facets.formats.map((f) => ({ value: f, label: FORMAT_LABEL[f] || f }))} />
            )}
            <FilterSelect label="Access" value={filters.accessType} onChange={set('accessType')} options={ACCESS_OPTIONS} />
            {isFiltering && (
              <button type="button" onClick={() => setFilters({ q: '', goal: '', difficultyLevel: '', format: '', accessType: '', topic: '' })} className="text-sm font-semibold text-burgundy-600 hover:underline">
                Clear filters
              </button>
            )}
          </div>
          {(() => {
            const items = isFiltering ? shownResults.items : catalog
            if (isFiltering && shownResults.error) return <EmptyState title="Couldn't load courses" description={shownResults.error} />
            if (items === null) return <PageLoader />
            if (!items.length) {
              return <EmptyState title={isFiltering ? 'No courses match these filters.' : 'New courses are on the way.'} description={isFiltering ? 'Try a different search or clear your filters.' : 'Check back soon.'} />
            }
            return (
              <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
                {items.map((p) => <LearningProgramCard key={p.id} program={p} />)}
              </div>
            )
          })()}
        </Section>

        {lifetime.available && (
          <section aria-labelledby="lifetime-banner-title" className="mb-14 rounded-card bg-plum-700 px-6 py-10 text-ivory sm:px-10">
            <p className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-ivory/80"><InfinityIcon size={16} aria-hidden="true" /> WSF Lifetime</p>
            <h2 id="lifetime-banner-title" className="mt-2 max-w-2xl font-serif text-2xl font-semibold sm:text-3xl">One payment. Every eligible WSF course and learning path, for life.</h2>
            <p className="mt-2 max-w-2xl text-sm text-ivory/85">Plus premium career resources and WSF Circle membership — with no renewal.</p>
            <Link to="/lifetime" className="btn-light mt-6">Discover WSF Lifetime</Link>
          </section>
        )}
      </div>

      <section className="border-t border-taupe-200 bg-charcoal py-16 text-ivory">
        <div className="container-editorial flex flex-col items-center text-center">
          <p className="eyebrow !text-blush-200">Never miss a new course</p>
          <h2 className="mt-3 max-w-xl font-serif text-3xl font-semibold">Get new courses and learning paths in your inbox</h2>
          <div className="mt-7">
            <NewsletterForm variant="dark" source="learning_page" />
          </div>
        </div>
      </section>
    </div>
  )
}
