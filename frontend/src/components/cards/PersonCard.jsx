import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'

// `person` must be a normalized object from api/people.js — its `country`
// field is already resolved there (nested by the backend in real mode,
// attached via attachMockCountry in mock mode). No lookup here.
export default function PersonCard({ person }) {
  if (!person) return null
  return (
    <Link to={`/people/${person.slug}`} className="group block">
      <MediaImage
        mediaPath={person.photo}
        alt={person.name}
        width={600}
        height={750}
        aspect={0.8}
        className="aspect-[4/5] w-full object-cover transition-transform duration-500 group-hover:scale-105"
      />
      <div className="mt-3">
        <h3 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">
          {person.name}
        </h3>
        <p className="mt-0.5 text-sm text-charcoal-600">{person.title}</p>
        <p className="text-sm text-charcoal-600">
          {person.organization} &middot; {person.country?.name || person.countryCode}
        </p>
      </div>
    </Link>
  )
}
