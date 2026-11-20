import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { fetchLearningPaths } from '../api/learningPaths'
import { CAREER_GOAL_OPTIONS } from '../constants/careerMetadata'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import Breadcrumb from '../components/ui/Breadcrumb'
import LearningPathCard from '../components/cards/LearningPathCard'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

const GOAL_LABEL = Object.fromEntries(CAREER_GOAL_OPTIONS.map((o) => [o.value, o.label]))

export default function LearningPathsPage() {
  const [params, setParams] = useSearchParams()
  const goal = (params.get('goal') || '').replace(/-/g, '_')
  const [all, setAll] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Learning Paths | WSF Learning',
    description: 'Guided career journeys: a few focused WSF courses, in order, for one career goal.',
    canonical: 'https://womenshapingfutures.org/learning/paths',
  })
  useBreadcrumbStructuredData([{ label: 'Learning', to: '/learning' }, { label: 'Learning Paths' }], 'https://womenshapingfutures.org/learning/paths')

  useEffect(() => {
    let active = true
    fetchLearningPaths()
      .then((items) => active && setAll(items))
      .catch(() => active && setError('Something went wrong loading learning paths. Please try again.'))
    return () => {
      active = false
    }
  }, [])

  // Goal chips only for goals that actually have a path.
  const goals = [...new Set((all || []).map((p) => p.careerGoal?.key).filter(Boolean))]
  const shown = (all || []).filter((p) => !goal || p.careerGoal?.key === goal)

  return (
    <div>
      <div className="container-editorial pt-6">
        <Breadcrumb items={[{ label: 'Learning', to: '/learning' }, { label: 'Learning Paths' }]} />
      </div>
      <header className="container-editorial pb-8 pt-8">
        <p className="eyebrow">WSF Learning</p>
        <h1 className="mt-3 font-serif text-4xl font-semibold text-charcoal sm:text-5xl">Learning Paths</h1>
        <p className="mt-4 max-w-2xl text-lg text-charcoal-600">Guided career journeys: a few focused WSF courses, in order, for one career goal.</p>
      </header>
      <div className="container-editorial pb-20">
        {goals.length > 1 && (
          <div className="mb-8 flex flex-wrap gap-2" role="group" aria-label="Filter by career goal">
            <button type="button" aria-pressed={!goal} onClick={() => setParams({})} className={`rounded-full border px-4 py-2 text-sm font-medium ${!goal ? 'border-plum-600 bg-plum-600 text-ivory' : 'border-taupe-300 bg-white text-charcoal'}`}>All goals</button>
            {goals.map((g) => (
              <button key={g} type="button" aria-pressed={goal === g} onClick={() => setParams({ goal: g.replace(/_/g, '-') })} className={`rounded-full border px-4 py-2 text-sm font-medium ${goal === g ? 'border-plum-600 bg-plum-600 text-ivory' : 'border-taupe-300 bg-white text-charcoal'}`}>
                {GOAL_LABEL[g] || g}
              </button>
            ))}
          </div>
        )}
        {error && <EmptyState title="Couldn't load learning paths" description={error} />}
        {!error && all === null && <PageLoader />}
        {!error && all !== null && (shown.length ? (
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {shown.map((p) => <LearningPathCard key={p.id} path={p} />)}
          </div>
        ) : (
          <EmptyState title="Learning Paths are coming soon." description="Browse WSF courses in the meantime." />
        ))}
      </div>
    </div>
  )
}
