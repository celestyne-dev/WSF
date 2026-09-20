import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'

export default function SectionHeading({ eyebrow, heading, subheading, viewAllHref, viewAllLabel = 'See all', align = 'left' }) {
  return (
    <div className={`flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between ${align === 'center' ? 'text-center sm:text-left' : ''}`}>
      <div>
        {eyebrow && <p className="eyebrow mb-2">{eyebrow}</p>}
        {heading && <h2 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{heading}</h2>}
        {subheading && <p className="mt-2 max-w-2xl text-base text-charcoal-600">{subheading}</p>}
      </div>
      {viewAllHref && (
        <Link
          to={viewAllHref}
          className="group inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-burgundy-600 transition-colors hover:text-burgundy-700"
        >
          {viewAllLabel}
          <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
        </Link>
      )}
    </div>
  )
}
