import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import { resolveAltText } from '../../utils/media'

export default function SeriesCard({ item }) {
  if (!item) return null
  return (
    <Link to={`/series/${item.slug}`} className="group relative block overflow-hidden">
      <MediaImage
        media={item.coverMedia}
        variant="card"
        mediaPath={item.coverImage}
        alt={resolveAltText(item.coverMedia, item.name)}
        width={900}
        height={1125}
        aspect={0.8}
        tone="plum"
        sizes="(min-width: 1024px) 25vw, (min-width: 640px) 50vw, 100vw"
        className="aspect-[4/5] w-full object-cover transition-transform duration-700 group-hover:scale-105"
      />
      <div className="absolute inset-0 bg-gradient-to-t from-charcoal-800/85 via-charcoal-800/10 to-transparent" />
      <div className="absolute inset-x-0 bottom-0 p-5">
        <p className="eyebrow !text-blush-100">Series</p>
        <h3 className="mt-1 font-serif text-xl font-semibold text-ivory">{item.name}</h3>
        <p className="mt-1 text-xs text-ivory/80">{item.articleCount} stories</p>
      </div>
    </Link>
  )
}
