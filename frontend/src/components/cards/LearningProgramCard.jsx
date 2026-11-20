import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import { programCardAccessLabel } from '../../utils/learningAccess'
import { formatMinutes } from '../../utils/learning'

const PROGRAM_TYPE_LABEL = {
  course: 'Course',
  masterclass: 'Masterclass',
  program: 'Program',
  learning_series: 'Learning Series',
  challenge: 'Challenge',
}

export default function LearningProgramCard({ program }) {
  if (!program) return null
  return (
    <Link to={`/learning/${program.slug}`} className="group block">
      <div className="relative overflow-hidden rounded-media bg-taupe-100">
        <MediaImage
          media={program.heroMedia}
          variant="card"
          alt={program.title}
          width={800}
          height={600}
          aspect={4 / 3}
          className="aspect-[4/3] w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        {program.featured && (
          <span className="absolute left-3 top-3 bg-burgundy-600 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-ivory">Featured</span>
        )}
      </div>
      <div className="mt-3">
        <span className="eyebrow">{PROGRAM_TYPE_LABEL[program.programType] || program.programType}</span>
        <h3 className="mt-1 font-serif text-lg font-semibold leading-snug text-charcoal transition-colors group-hover:text-burgundy-600">
          {program.title}
        </h3>
        {program.shortDescription && <p className="mt-1 line-clamp-2 text-sm text-charcoal-600/80">{program.shortDescription}</p>}
        {/* Derived, real facts only: "Text-based · 12 lessons · 1 hr 40 min". */}
        {program.stats?.lessonCount > 0 && (
          <p className="mt-1.5 text-xs text-charcoal-600">
            {[program.stats.formatLabel, `${program.stats.lessonCount} lesson${program.stats.lessonCount === 1 ? '' : 's'}`, formatMinutes(program.stats.totalMinutes)].filter(Boolean).join(' · ')}
          </p>
        )}
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm font-medium text-charcoal-600">
          {program.primaryInstructor?.name && <span>{program.primaryInstructor.name}</span>}
          {program.primaryInstructor?.name && <span className="text-charcoal-600/40">·</span>}
          <span>{programCardAccessLabel(program)}</span>
        </div>
        {program.lifetimeIncluded && program.accessType === 'product' && (
          <p className="mt-1 text-xs font-semibold text-plum-600">Included with WSF Lifetime</p>
        )}
      </div>
    </Link>
  )
}
