import { useEffect, useMemo, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import InstitutionalPageHero from '../components/pages/InstitutionalPageHero'
import InstitutionalPageShell from '../components/pages/InstitutionalPageShell'
import LegalPageLayout from '../components/pages/LegalPageLayout'
import { buildHeadingToc } from '../utils/headingToc'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

// "On this page" anchor ids: see utils/headingToc.js (shared with ArticlePage).

// Backs /privacy, /terms, /cookies, /editorial-policy — each a fixed
// system Page identified by `docKey` (== its stable backend `key`, see
// backend/app/models/page.py SYSTEM_PAGE_KEYS). Title, subtitle, content,
// hero media, effective date, and SEO are entirely CMS-managed; this
// component only lays it out — no policy wording lives here. No eyebrow
// is rendered: a generic "Legal" label adds no CMS-editable information,
// and a policy-specific one would be exactly the kind of copy an editor
// should control through AdminPageEditor instead.
export default function LegalPage({ docKey }) {
  const [page, setPage] = useState(undefined)

  useEffect(() => {
    let active = true
    setPage(undefined)
    fetchPublicPage(docKey)
      .then((res) => active && setPage(res))
      .catch(() => active && setPage(null))
    return () => {
      active = false
    }
  }, [docKey])

  useSeo({
    // CMS SEO fields win; the Page's own title/subtitle are the next
    // fallback (both are editor-controlled), and only below that does
    // useSeo() reach for the global Site Settings SEO defaults.
    title: page?.seo?.title || page?.title,
    description: page?.seo?.description || page?.subtitle,
    canonical: `https://womenshapingfutures.org/${docKey}`,
  })
  // Home > (the real public CMS page display title, page.title — same
  // string shown as this page's own H1 via InstitutionalPageHero below)
  // — matches the server's own breadcrumb for this docKey
  // (spa_shell.py's _render_system_page_shell, same page.title, never
  // the resolved SEO/meta title), computed against the current
  // docKey's own canonical so switching between /privacy, /terms,
  // /cookies, and /editorial-policy never leaves a stale previous-page
  // breadcrumb.
  useBreadcrumbStructuredData(
    page ? [{ label: page?.title }] : null,
    `https://womenshapingfutures.org/${docKey}`,
  )

  const headings = useMemo(() => buildHeadingToc(page?.content), [page?.content])

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <InstitutionalPageHero title={page.title} description={page.subtitle} />
      <InstitutionalPageShell heroMedia={page.heroMedia} maxWidthClassName="">
        <LegalPageLayout headings={headings} effectiveDate={page.effectiveDate} content={page.content} />
      </InstitutionalPageShell>
    </div>
  )
}
