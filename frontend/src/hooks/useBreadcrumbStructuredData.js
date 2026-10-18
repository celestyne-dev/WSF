import { useEffect } from 'react'

// Shared BreadcrumbList JSON-LD emitter — WSF SEO Phase 2A. Mirrors the
// server's own breadcrumb builder (backend/app/services/spa_shell.py's
// _build_breadcrumb_json_ld) so the initial, crawler-visible trail and
// whatever the client renders after an SPA navigation are always the
// same shape, under the same data-breadcrumb-structured-data attribute
// the server already uses — so this always finds and reuses the
// server-rendered tag on first mount rather than appending a duplicate,
// same pattern as every other structured-data hook in this app.
//
// `items` is the SAME {label, to}[] shape every detail page's own
// visible <Breadcrumb> component already consumes — Home is added
// automatically as position 1, never passed in. An entry with a `to`
// links to that relative path; the one entry without a `to` (normally
// the last, current-page crumb) uses `canonicalUrl` instead, so the
// trail always ends on the exact address this page itself
// canonicalizes to — never a path invented here.
//
// Without this, a client-side navigation between two pages that don't
// both manage this exact tag (e.g. two different Job postings) would
// leave a previous page's breadcrumb trail sitting in document.head
// forever, since nothing else ever touches this attribute — unlike
// useSeo.js's own tags, this one has no "always mounted" owner.
export default function useBreadcrumbStructuredData(items, canonicalUrl) {
  useEffect(() => {
    if (!items?.length || !canonicalUrl) return
    let origin
    try {
      origin = new URL(canonicalUrl).origin
    } catch {
      return
    }
    const data = {
      '@context': 'https://schema.org',
      '@type': 'BreadcrumbList',
      itemListElement: [
        { '@type': 'ListItem', position: 1, name: 'Home', item: `${origin}/` },
        ...items.map((entry, i) => ({
          '@type': 'ListItem',
          position: i + 2,
          name: entry.label,
          item: entry.to ? `${origin}${entry.to}` : canonicalUrl,
        })),
      ],
    }
    let el = document.head.querySelector('script[data-breadcrumb-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-breadcrumb-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [items, canonicalUrl])
}
