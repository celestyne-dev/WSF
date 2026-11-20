import { Link } from 'react-router-dom'
import { CheckCircle2, Clock, Sparkles } from 'lucide-react'
import MediaImage from '../ui/MediaImage'
import { cardAccessLine, cardCircleLine, cardEyebrow, cardMetaLine, cardPriceLine, cardViewerLine } from '../../utils/careerHub'

/**
 * One WSF Career Hub result — a Resource or a Learning program in the same
 * shape. Everything shown is what the server computed for an anonymous
 * visitor; opening the item goes to its own page, which enforces access.
 */
export default function CareerHubCard({ card, onOpen }) {
  if (!card) return null
  const eyebrow = cardEyebrow(card)
  const meta = cardMetaLine(card)
  const price = cardPriceLine(card)
  const circle = cardCircleLine(card)
  const access = cardAccessLine(card)
  // A signed-in member whose own membership covers this item sees that
  // first; the original price stays visible but secondary (no buy cue).
  const viewer = cardViewerLine(card)
  return (
    <Link
      to={card.url}
      onClick={() => onOpen?.(card)}
      className="group flex overflow-hidden rounded-card h-full min-w-0 flex-col border border-taupe-200 bg-white transition-shadow hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-600"
    >
      <div className="relative overflow-hidden bg-taupe-100">
        <MediaImage
          media={card.image}
          variant="card"
          alt={card.imageAlt || card.title}
          width={800}
          height={500}
          aspect={16 / 10}
          sizes="(min-width: 1024px) 33vw, (min-width: 640px) 50vw, 100vw"
          className="aspect-[16/10] w-full object-cover transition-transform duration-500 group-hover:scale-105"
        />
        <span className="absolute left-3 top-3 bg-charcoal/85 px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-ivory">
          {card.sourceType === 'learning' ? 'Learning' : 'Resource'}
        </span>
      </div>
      <div className="flex flex-1 flex-col p-5">
        {eyebrow && <p className="eyebrow break-words">{eyebrow}</p>}
        {meta && (
          <p className="mt-1 flex items-center gap-1.5 text-xs font-medium text-charcoal-600">
            {card.estimatedTime && <Clock size={12} aria-hidden="true" />}
            {meta}
          </p>
        )}
        <h3 className="mt-2 break-words font-serif text-lg font-semibold leading-snug text-charcoal group-hover:text-burgundy-700">{card.title}</h3>
        {card.summary && <p className="mt-2 line-clamp-3 text-sm text-charcoal-600">{card.summary}</p>}
        <div className="mt-auto space-y-1 pt-4 text-sm">
          {viewer && (
            <p className="flex items-center gap-1.5 font-semibold text-plum-600">
              <CheckCircle2 size={14} aria-hidden="true" /> {viewer}
            </p>
          )}
          {price && <p className={viewer ? 'text-xs text-charcoal-600/70' : 'font-semibold text-charcoal'}>{price}</p>}
          {access && !viewer && <p className="font-medium text-charcoal-600">{access}</p>}
          {circle && !viewer && (
            <p className="flex items-center gap-1.5 font-medium text-plum-600">
              <Sparkles size={13} aria-hidden="true" /> {circle}
            </p>
          )}
        </div>
      </div>
    </Link>
  )
}
