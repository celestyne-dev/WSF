import { Link } from 'react-router-dom'
import MediaImage from '../ui/MediaImage'
import { resolveAltText } from '../../utils/media'

// AI Search / GEO Phase 4C — a bounded list of lightweight profile previews
// on a Topic ("Contributors covering this topic": active Authors explicitly
// classified under the Topic) or a Series ("People in this series":
// published People explicitly in the Series). Never inferred, never
// labelled "experts"; credentials/sources stay on the profile pages
// themselves. The same items, order and links are in the server-rendered
// first paint (prerender.py's _editorial_depth).
export default function ProfilePreviewList({ id, heading, items, basePath, metaKey }) {
  const profiles = (items || []).filter((p) => p?.slug && p?.name)
  if (!profiles.length) return null
  return (
    <section aria-labelledby={id} className="mt-12">
      <h2 id={id} className="font-serif text-2xl font-semibold text-charcoal">
        {heading}
      </h2>
      <ul className="mt-6 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {profiles.map((p) => (
          <li key={p.slug} className="flex items-start gap-4">
            <MediaImage media={p.photoMedia} variant="card" mediaPath={p.photo} alt={resolveAltText(p.photoMedia, p.name)} width={128} height={128} aspect={1} sizes="64px" className="h-16 w-16 shrink-0 rounded-full object-cover" />
            <div className="min-w-0">
              <Link to={`${basePath}/${p.slug}`} className="font-serif text-lg font-semibold text-charcoal hover:text-burgundy-600">
                {p.name}
              </Link>
              {p[metaKey] && <p className="mt-0.5 text-sm text-charcoal-600">{p[metaKey]}</p>}
              {p.shortBio && <p className="mt-1 line-clamp-3 text-sm text-charcoal-600/80">{p.shortBio}</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}
