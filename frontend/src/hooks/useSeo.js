import { useEffect } from 'react'
import { useSelector } from 'react-redux'
import { resolveMediaImage } from '../utils/media'

// Only ever clears/writes tags this hook itself owns (selectors below are
// scoped to one specific meta[name]/meta[property]/link[rel=canonical]) —
// never touches any other <head> tag a layout or analytics snippet manages.
function setMeta(attr, key, content) {
  const el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!content) {
    el?.remove()
    return
  }
  if (el) {
    el.setAttribute('content', content)
    return
  }
  const created = document.createElement('meta')
  created.setAttribute(attr, key)
  created.setAttribute('content', content)
  document.head.appendChild(created)
}

function setCanonical(url) {
  const el = document.head.querySelector('link[rel="canonical"]')
  if (!url) {
    el?.remove()
    return
  }
  if (el) {
    el.setAttribute('href', url)
    return
  }
  const created = document.createElement('link')
  created.setAttribute('rel', 'canonical')
  created.setAttribute('href', url)
  document.head.appendChild(created)
}

/**
 * Applies per-page SEO metadata (title, description, canonical, OpenGraph,
 * Twitter card, robots). In production this metadata is CMS-editable per
 * content item; here it mirrors the `seo` field modeled on every content type.
 *
 * `type`/`ogType` sets og:type explicitly — defaults to "website". Only
 * pass "article" (or another real og:type value) from a page whose content
 * actually is one; most WSF pages (jobs, events, resources, listings) stay
 * "website" unless their own semantics say otherwise.
 *
 * `imageAlt` sets og:image:alt/twitter:image:alt — only ever rendered when
 * a real alt text is supplied; never fabricated here.
 *
 * When a page passes no title/description/image of its own, falls back to
 * the global Site Settings SEO defaults (Admin → Site Settings → Site
 * Identity → SEO defaults, via state.site.settings.seo) instead of leaving
 * the tag unset — page-specific SEO always overrides this, never the
 * reverse.
 *
 * Every managed tag is cleared (not left stale) when its value is absent on
 * a later render — e.g. navigating from a page with an image to one
 * without must not leave the previous page's og:image in document.head.
 */
export default function useSeo({ title, description, canonical, image, imageAlt, robots = 'index, follow', type, ogType } = {}) {
  const seoDefaults = useSelector((s) => s.site.settings?.seo)
  const resolvedTitle = title || seoDefaults?.defaultTitle
  const resolvedDescription = description || seoDefaults?.defaultDescription
  const resolvedImage = image || (seoDefaults?.defaultOgImage ? resolveMediaImage(seoDefaults.defaultOgImage, { variant: 'large' }).src : undefined)
  const resolvedType = ogType || type || 'website'

  useEffect(() => {
    if (resolvedTitle) document.title = resolvedTitle
    setMeta('name', 'description', resolvedDescription)
    setMeta('name', 'robots', robots)
    setCanonical(canonical)
    setMeta('property', 'og:title', resolvedTitle)
    setMeta('property', 'og:description', resolvedDescription)
    setMeta('property', 'og:url', canonical)
    setMeta('property', 'og:type', resolvedType)
    setMeta('property', 'og:image', resolvedImage)
    setMeta('property', 'og:image:alt', resolvedImage ? imageAlt : undefined)
    setMeta('name', 'twitter:card', 'summary_large_image')
    setMeta('name', 'twitter:title', resolvedTitle)
    setMeta('name', 'twitter:description', resolvedDescription)
    setMeta('name', 'twitter:image', resolvedImage)
    setMeta('name', 'twitter:image:alt', resolvedImage ? imageAlt : undefined)
  }, [resolvedTitle, resolvedDescription, canonical, resolvedImage, imageAlt, robots, resolvedType])
}
