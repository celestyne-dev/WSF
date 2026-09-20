import { Link } from 'react-router-dom'
import { topics } from '../mock/topics'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'

export default function TopicsIndexPage() {
  useSeo({
    title: 'Stories by Topic | Women Shaping Futures',
    description: 'Explore Women Shaping Futures stories by topic — leadership, careers, entrepreneurship, money, technology, and more.',
    canonical: 'https://womenshapingfutures.org/topics',
  })

  return (
    <div>
      <PageHeader eyebrow="Stories" title="Browse by Topic" description="Every story we publish, organized around the themes that matter most to the women who read us." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {topics.map((topic) => (
            <Link
              key={topic.id}
              to={`/topics/${topic.slug}`}
              className="group border border-taupe-200 bg-white p-6 transition-colors hover:border-burgundy-500/40"
            >
              <h2 className="font-serif text-xl font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{topic.name}</h2>
              <p className="mt-2 text-sm text-charcoal-600">{topic.description}</p>
              <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-charcoal-600/70">{topic.articleCount} stories</p>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
