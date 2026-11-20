import { Link } from 'react-router-dom'
import { Route } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { formatMinutes } from '../../utils/learning'

// A Learning Path summary: course count and duration are derived by the
// server from the path's published courses; progress is the signed-in
// learner's own (only on the detail page).
export default function LearningPathCard({ path }) {
  if (!path) return null
  const facts = [`${path.courseCount} course${path.courseCount === 1 ? '' : 's'}`, path.totalMinutes ? `Approx. ${formatMinutes(path.totalMinutes)}` : null].filter(Boolean)
  return (
    <Link to={`/learning/paths/${path.slug}`} className="group flex h-full flex-col overflow-hidden rounded-card border border-taupe-200 bg-white transition-shadow hover:shadow-card">
      {path.heroMedia ? (
        <MediaImage media={path.heroMedia} variant="card" alt="" width={800} height={450} aspect={16 / 9} className="aspect-[16/9] w-full object-cover" />
      ) : (
        <div className="flex aspect-[16/9] items-center justify-center bg-gradient-to-br from-plum-600 to-burgundy-600 text-ivory" aria-hidden="true">
          <Route size={36} />
        </div>
      )}
      <div className="flex flex-1 flex-col p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy-600">{path.careerGoal?.label || 'Learning Path'}</p>
        <h3 className="mt-1.5 font-serif text-xl font-semibold leading-snug text-charcoal group-hover:text-burgundy-600">{path.title}</h3>
        {(path.shortDescription || path.subtitle) && <p className="mt-2 line-clamp-2 text-sm text-charcoal-600">{path.shortDescription || path.subtitle}</p>}
        {path.courseTitles?.length > 0 && (
          <ol className="mt-3 space-y-1 text-sm text-charcoal">
            {path.courseTitles.slice(0, 4).map((title, i) => (
              <li key={i} className="flex gap-2">
                <span className="w-4 shrink-0 text-right font-semibold text-charcoal-600">{i + 1}.</span>
                <span className="line-clamp-1">{title}</span>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-auto pt-4 text-xs font-semibold text-charcoal-600">
          {facts.join(' · ')}
          {path.lifetimeIncluded && <span className="ml-2 text-plum-600">· All included with WSF Lifetime</span>}
        </p>
      </div>
    </Link>
  )
}
