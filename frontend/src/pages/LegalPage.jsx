import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

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
    // No hardcoded literal fallback here — useSeo() itself falls back to
    // the global Site Settings SEO defaults when this page has none of its
    // own configured (see hooks/useSeo.js).
    title: page?.seo?.title,
    description: page?.seo?.description || page?.subtitle,
    canonical: `https://womenshapingfutures.org/${docKey}`,
  })

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <PageHeader title={page.title} description={page.subtitle} />
      <div className="container-editorial py-14">
        {page.heroMedia && (
          <div className="mb-14">
            <MediaImage media={page.heroMedia} variant="large" width={1200} height={600} aspect={2} priority className="w-full object-cover" />
          </div>
        )}
        <div className="mx-auto max-w-reading">
          {page.effectiveDate && (
            <p className="mb-8 text-sm text-charcoal-600">Last updated: {formatDate(page.effectiveDate)}</p>
          )}
          <ArticleContent blocks={page.content} />
        </div>
      </div>
    </div>
  )
}
