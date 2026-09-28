import { useEffect, useState } from 'react'
import { Search } from 'lucide-react'
import { fetchLearningPrograms } from '../api/learning'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import FilterSelect from '../components/ui/FilterSelect'
import LearningProgramCard from '../components/cards/LearningProgramCard'
import NewsletterForm from '../components/ui/NewsletterForm'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'

const PROGRAM_TYPES = [
  { value: 'course', label: 'Course' },
  { value: 'masterclass', label: 'Masterclass' },
  { value: 'program', label: 'Program' },
  { value: 'learning_series', label: 'Learning Series' },
]

const DIFFICULTY_LEVELS = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'all_levels', label: 'All levels' },
]

const DELIVERY_MODES = [
  { value: 'self_paced', label: 'Self-paced' },
  { value: 'live_online', label: 'Live online' },
  { value: 'in_person', label: 'In person' },
  { value: 'hybrid', label: 'Hybrid' },
]

export default function LearningPage() {
  const [query, setQuery] = useState('')
  const [programType, setProgramType] = useState('')
  const [difficultyLevel, setDifficultyLevel] = useState('')
  const [deliveryMode, setDeliveryMode] = useState('')
  const [featured, setFeatured] = useState(null)
  const [latest, setLatest] = useState(null)
  const [results, setResults] = useState(null)
  const [error, setError] = useState(null)

  const isFiltering = !!(query || programType || difficultyLevel || deliveryMode)

  useSeo({
    title: 'Learning | Women Shaping Futures',
    description: 'Courses, masterclasses, and learning programs on leadership, entrepreneurship, and career growth.',
    canonical: 'https://womenshapingfutures.org/learning',
  })

  useEffect(() => {
    let active = true
    Promise.all([
      fetchLearningPrograms({ featured: 'true', pageSize: 4 }),
      fetchLearningPrograms({ pageSize: 8 }),
    ])
      .then(([featuredRes, latestRes]) => {
        if (!active) return
        setFeatured(featuredRes.items)
        setLatest(latestRes.items)
      })
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useEffect(() => {
    if (!isFiltering) {
      setResults(null)
      return
    }
    let active = true
    setError(null)
    fetchLearningPrograms({ programType, difficultyLevel, deliveryMode, q: query, pageSize: 100 })
      .then((res) => active && setResults(res.items))
      .catch(() => active && setError('Something went wrong loading learning programs. Please try again.'))
    return () => {
      active = false
    }
  }, [programType, difficultyLevel, deliveryMode, query, isFiltering])

  return (
    <div>
      <PageHeader
        eyebrow="WSF Learning"
        title="Courses, Masterclasses & Learning Programs"
        description="Structured learning on leadership, entrepreneurship, and career growth — self-paced courses, live masterclasses, and guided programs."
      />
      <div className="container-editorial py-10">
        <div className="flex flex-wrap items-center gap-3 border-b border-taupe-200 pb-8">
          <div className="flex items-center gap-2 border border-taupe-300 bg-white px-3 py-2.5">
            <Search size={16} className="text-charcoal-600" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search learning programs…"
              className="w-full min-w-0 text-sm focus:outline-none sm:w-56"
            />
          </div>
          <FilterSelect label="Type" value={programType} onChange={setProgramType} options={PROGRAM_TYPES} />
          <FilterSelect label="Level" value={difficultyLevel} onChange={setDifficultyLevel} options={DIFFICULTY_LEVELS} />
          <FilterSelect label="Delivery" value={deliveryMode} onChange={setDeliveryMode} options={DELIVERY_MODES} />
        </div>

        {isFiltering ? (
          <div className="mt-8">
            {error && <EmptyState title="Couldn't load learning programs" description={error} />}
            {!error && results === null && <PageLoader />}
            {!error && results !== null && (
              results.length ? (
                <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
                  {results.map((p) => (
                    <LearningProgramCard key={p.id} program={p} />
                  ))}
                </div>
              ) : (
                <EmptyState title="No learning programs match these filters." description="Try a different search term or clear your filters." />
              )
            )}
          </div>
        ) : (
          <>
            {featured === null ? (
              <div className="mt-8">
                <PageLoader />
              </div>
            ) : (
              <>
                {featured.length > 0 && (
                  <section className="mt-12">
                    <h2 className="font-serif text-2xl font-semibold text-charcoal">Featured</h2>
                    <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
                      {featured.map((p) => (
                        <LearningProgramCard key={p.id} program={p} />
                      ))}
                    </div>
                  </section>
                )}

                {latest?.length > 0 && (
                  <section className="mt-14 border-t border-taupe-200 pt-12">
                    <h2 className="font-serif text-2xl font-semibold text-charcoal">Browse all</h2>
                    <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
                      {latest.map((p) => (
                        <LearningProgramCard key={p.id} program={p} />
                      ))}
                    </div>
                  </section>
                )}

                {featured.length === 0 && !latest?.length && (
                  <div className="mt-8">
                    <EmptyState title="No learning programs match these filters." description="Check back soon." />
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>

      <section className="border-t border-taupe-200 bg-charcoal py-16 text-ivory sm:py-20">
        <div className="container-editorial flex flex-col items-center text-center">
          <p className="eyebrow !text-blush-200">Never miss a new program</p>
          <h2 className="mt-3 max-w-xl font-serif text-3xl font-semibold sm:text-4xl">Get new courses and masterclasses in your inbox</h2>
          <div className="mt-7">
            <NewsletterForm variant="dark" source="learning_page" />
          </div>
        </div>
      </section>
    </div>
  )
}
