import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import { formatCurrency } from '../../utils/format'

const PROGRAM_TYPE_LABEL = {
  course: 'Course',
  masterclass: 'Masterclass',
  program: 'Program',
  learning_series: 'Learning Series',
}

function accessLabel(program) {
  if (program.accessType === 'circle_only') return 'WSF Circle'
  if (program.accessType === 'product') {
    if (program.product) {
      return program.product.price ? formatCurrency(program.product.price, program.product.currency) : 'Premium'
    }
    return 'Premium'
  }
  if (program.accessType === 'external') return 'External'
  return 'Free'
}

export default function LearningProgramCard({ program }) {
  if (!program) return null
  return (
    <Link to={`/learning/${program.slug}`} className="group block">
      <div className="relative overflow-hidden bg-taupe-100">
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
        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm font-medium text-charcoal-600">
          {program.primaryInstructor?.name && <span>{program.primaryInstructor.name}</span>}
          {program.primaryInstructor?.name && <span className="text-charcoal-600/40">·</span>}
          <span>{accessLabel(program)}</span>
        </div>
      </div>
    </Link>
  )
}
