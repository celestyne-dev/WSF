import { Link } from 'react-router-dom'
import {
  ArrowUpRight, Award, BookOpen, Briefcase, Calendar, Compass, Globe, GraduationCap, HeartHandshake, Lightbulb,
  Megaphone, Rocket, Sparkles, Target, Users,
} from 'lucide-react'
import SectionHeading from '../ui/SectionHeading'
import SectionCtaLink from './SectionCtaLink'
import { externalRel } from '../../utils/navigation'
import { pathwayCardLink } from '../../utils/homepageCollections'

// Controlled icon keys (backend PATHWAY_ICONS) -> lucide icons.
const ICONS = {
  briefcase: Briefcase, 'graduation-cap': GraduationCap, users: Users, 'book-open': BookOpen, lightbulb: Lightbulb,
  compass: Compass, calendar: Calendar, sparkles: Sparkles, 'heart-handshake': HeartHandshake, rocket: Rocket,
  target: Target, megaphone: Megaphone, globe: Globe, award: Award,
}

// Desktop columns by card count: 3–4 tiles per row without a lonely orphan.
const DESKTOP_COLUMNS = {
  1: 'lg:grid-cols-2', 2: 'lg:grid-cols-2', 3: 'lg:grid-cols-3', 4: 'lg:grid-cols-4',
  5: 'lg:grid-cols-3', 6: 'lg:grid-cols-3', 7: 'lg:grid-cols-4', 8: 'lg:grid-cols-4',
}

function PathwayTile({ card }) {
  const link = pathwayCardLink(card)
  if (!link || link.kind === 'group') return null
  const Icon = card.icon ? ICONS[card.icon] : null
  const body = (
    <>
      {card.image ? (
        <img
          src={card.image.url}
          alt=""
          width={card.image.width || undefined}
          height={card.image.height || undefined}
          loading="lazy"
          className="mb-4 aspect-[16/9] w-full object-cover"
        />
      ) : (
        Icon && (
          <span className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-full bg-taupe-100 text-burgundy-600 transition-colors group-hover:bg-burgundy-600 group-hover:text-white">
            <Icon size={20} aria-hidden="true" />
          </span>
        )
      )}
      {card.eyebrow && <p className="eyebrow mb-1.5">{card.eyebrow}</p>}
      <h3 className="break-words font-serif text-xl font-semibold leading-snug text-charcoal group-hover:text-burgundy-700">{card.title}</h3>
      {card.description && <p className="mt-2 break-words text-sm leading-relaxed text-charcoal-600">{card.description}</p>}
      <span className="mt-auto flex justify-end pt-4 text-burgundy-600" aria-hidden="true">
        <ArrowUpRight size={18} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
      </span>
    </>
  )
  const className =
    'group flex h-full min-w-0 flex-col border border-taupe-200 border-t-4 border-t-burgundy-600 bg-white p-5 transition-shadow hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy-600 sm:p-6'
  const aria = card.ariaLabel || undefined
  return (
    <li className="min-w-0">
      {link.kind === 'external' ? (
        <a href={link.href} target={link.newTab ? '_blank' : undefined} rel={externalRel(link.newTab)} aria-label={aria} className={className}>
          {body}
        </a>
      ) : (
        <Link to={link.to} aria-label={aria} className={className}>
          {body}
        </Link>
      )}
    </li>
  )
}

/**
 * Career Pathways / Start Here — editor-written "where do I start?" tiles.
 * Cards arrive resolved from the server (unpublished/invalid destinations
 * already dropped); the section hides itself when none remain.
 */
export default function CareerPathwaysModule({ module }) {
  const cards = (module.resolved?.cards || []).filter((c) => pathwayCardLink(c))
  if (cards.length === 0) return null
  const columns = DESKTOP_COLUMNS[cards.length] || 'lg:grid-cols-4'
  return (
    <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
      <div className="container-editorial">
        <SectionHeading eyebrow={module.eyebrow} heading={module.heading} subheading={module.subheading} />
        <ul className={`mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 ${columns}`}>
          {cards.map((card, index) => (
            <PathwayTile key={`${card.href}-${index}`} card={card} />
          ))}
        </ul>
        <SectionCtaLink label={module.ctaLabel} url={module.ctaUrl} />
      </div>
    </section>
  )
}
