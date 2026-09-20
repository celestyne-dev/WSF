import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

const TRACKS = [
  { title: 'Personal Branding', level: 'Beginner', format: 'Self-paced' },
  { title: 'Leadership Fundamentals', level: 'Intermediate', format: 'Cohort-based' },
  { title: 'Entrepreneurship 101', level: 'Beginner', format: 'Self-paced' },
  { title: 'Digital Marketing for Founders', level: 'Intermediate', format: 'Self-paced' },
  { title: 'Financial Literacy & Investing', level: 'Beginner', format: 'Live workshop' },
  { title: 'Job Searching & Interviewing', level: 'Beginner', format: 'Self-paced' },
]

export default function LearningPage() {
  useSeo({
    title: 'Learning & Academy | Women Shaping Futures',
    description: 'Courses, workshops, and masterclasses on leadership, entrepreneurship, and career growth.',
    canonical: 'https://womenshapingfutures.org/learning',
  })

  return (
    <div>
      <PageHeader eyebrow="WSF Academy" title="Learning" description="Courses and masterclasses on leadership, entrepreneurship, and career growth — launching soon." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {TRACKS.map((t) => (
            <div key={t.title} className="border border-taupe-200 bg-white p-6">
              <span className="eyebrow">{t.level}</span>
              <h3 className="mt-2 font-serif text-lg font-semibold text-charcoal">{t.title}</h3>
              <p className="mt-1 text-sm text-charcoal-600">{t.format}</p>
              <span className="mt-4 inline-block bg-taupe-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">Coming soon</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
