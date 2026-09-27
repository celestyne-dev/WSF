import { useEffect } from 'react'
import { useSelector } from 'react-redux'
import { resolveMediaImage } from '../utils/media'

// One site-wide schema.org WebSite + Organization structured-data block,
// rendered once (see layouts/PublicLayout.jsx) from the global Site
// Settings data already bootstrapped there (state.site.settings) — kept
// entirely separate from the per-page structured data various detail pages
// already add for themselves (Article/Event/Resource/...). Built only from
// real, admin-configured values: no fabricated founding date, address,
// awards, or SearchAction — `sameAs` lists only the real, currently visible
// social profile URLs Footer CMS manages (see api/site.js's mapSiteSettings).
export default function useSiteStructuredData() {
  const settings = useSelector((s) => s.site.settings)

  useEffect(() => {
    if (!settings?.site?.name) return

    const siteUrl = settings.site.url
    const logo = settings.branding?.logo
    const sameAs = (settings.social || []).map((s) => s.url).filter(Boolean)

    const data = [
      {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        name: settings.site.name,
        ...(siteUrl ? { url: siteUrl } : {}),
      },
      {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: settings.site.name,
        ...(siteUrl ? { url: siteUrl } : {}),
        ...(logo ? { logo: resolveMediaImage(logo, { variant: 'card', width: 512, height: 512 }).src } : {}),
        ...(sameAs.length ? { sameAs } : {}),
      },
    ]

    let el = document.head.querySelector('script[data-site-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-site-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [settings])
}
