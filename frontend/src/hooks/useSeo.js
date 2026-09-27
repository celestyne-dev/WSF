import { useEffect } from 'react'
import { useSelector } from 'react-redux'
import { resolveMediaImage } from '../utils/media'

function setMeta(attr, key, content) {
  if (!content) return
  let el = document.head.querySelector(`meta[${attr}="${key}"]`)
  if (!el) {
    el = document.createElement('meta')
    el.setAttribute(attr, key)
    document.head.appendChild(el)
  }
  el.setAttribute('content', content)
}

function setCanonical(url) {
  if (!url) return
  let el = document.head.querySelector('link[rel="canonical"]')
  if (!el) {
    el = document.createElement('link')
    el.setAttribute('rel', 'canonical')
    document.head.appendChild(el)
  }
  el.setAttribute('href', url)
}

/**
 * Applies per-page SEO metadata (title, description, canonical, OpenGraph,
 * Twitter card, robots). In production this metadata is CMS-editable per
 * content item; here it mirrors the `seo` field modeled on every content type.
 *
 * When a page passes no title/description/image of its own, falls back to
 * the global Site Settings SEO defaults (Admin → Site Settings → Site
 * Identity → SEO defaults, via state.site.settings.seo) instead of leaving
 * the tag unset — page-specific SEO always overrides this, never the
 * reverse.
 */
export default function useSeo({ title, description, canonical, image, robots = 'index, follow' } = {}) {
  const seoDefaults = useSelector((s) => s.site.settings?.seo)
  const resolvedTitle = title || seoDefaults?.defaultTitle
  const resolvedDescription = description || seoDefaults?.defaultDescription
  const resolvedImage = image || (seoDefaults?.defaultOgImage ? resolveMediaImage(seoDefaults.defaultOgImage, { variant: 'large' }).src : undefined)

  useEffect(() => {
    if (resolvedTitle) document.title = resolvedTitle
    setMeta('name', 'description', resolvedDescription)
    setMeta('name', 'robots', robots)
    setCanonical(canonical)
    setMeta('property', 'og:title', resolvedTitle)
    setMeta('property', 'og:description', resolvedDescription)
    setMeta('property', 'og:url', canonical)
    setMeta('property', 'og:type', 'article')
    if (resolvedImage) setMeta('property', 'og:image', resolvedImage)
    setMeta('name', 'twitter:card', 'summary_large_image')
    setMeta('name', 'twitter:title', resolvedTitle)
    setMeta('name', 'twitter:description', resolvedDescription)
  }, [resolvedTitle, resolvedDescription, canonical, resolvedImage, robots])
}
