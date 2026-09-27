import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { resolveMediaImage } from '../../utils/media'

// The wordmark below is the structural fallback (spec: some immutable
// defaults are fine, but CMS data is authoritative when available) — an
// admin-uploaded logo (Site Settings → Site Identity → Branding) always
// wins when one is configured, read from the same site-wide settings
// PublicLayout already bootstraps once (state.site.settings).
export default function Logo({ light = false }) {
  const logo = useSelector((s) => s.site.settings?.branding?.logo)
  const siteName = useSelector((s) => s.site.settings?.site?.name) || 'Women Shaping Futures'

  if (logo) {
    const { src } = resolveMediaImage(logo, { variant: 'card', width: 240, height: 80 })
    return (
      <Link to="/" className="flex items-center">
        <img src={src} alt={siteName} className="h-8 w-auto sm:h-9" />
      </Link>
    )
  }

  return (
    <Link to="/" className="flex flex-col items-start leading-none">
      <span className={`whitespace-nowrap font-serif text-xl font-semibold tracking-tight sm:text-[1.5rem] ${light ? 'text-ivory' : 'text-charcoal'}`}>
        Women Shaping <span className="text-burgundy-500">Futures</span>
      </span>
      <span className={`mt-0.5 hidden whitespace-nowrap text-[10px] font-semibold uppercase tracking-widest2 sm:block ${light ? 'text-ivory/70' : 'text-charcoal-600'}`}>
        Stories &middot; Opportunity &middot; Growth
      </span>
    </Link>
  )
}
