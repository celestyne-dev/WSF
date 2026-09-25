import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import { formatDate } from '../utils/format'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

// Backs /privacy, /terms, /cookies, /editorial-policy — each a fixed
// system Page identified by `docKey` (== its stable backend `key`, see
// backend/app/models/page.py SYSTEM_PAGE_KEYS). Content, effective date,
// and SEO are entirely CMS-managed; this component only lays it out.
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
    title: page?.seo?.title || `${page?.title || 'Legal'} | Women Shaping Futures`,
    description: page?.seo?.description || page?.subtitle,
    canonical: `https://womenshapingfutures.org/${docKey}`,
  })

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <PageHeader eyebrow="Legal" title={page.title} description={page.subtitle} />
      <div className="container-editorial max-w-reading py-14">
        {page.effectiveDate && (
          <p className="mb-8 text-sm text-charcoal-600">Last updated: {formatDate(page.effectiveDate)}</p>
        )}
        <ArticleContent blocks={page.content} />
      </div>
    </div>
  )
}
