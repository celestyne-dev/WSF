import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

// A true Pages CMS page — title, subtitle, hero media, content, and SEO
// all come from the "about" Page record (/admin/pages) and nothing else.
// No audience stats, no authors grid, no hard-coded copy: an editor's
// save in AdminPageEditor is exactly what renders here.
export default function AboutPage() {
  const [page, setPage] = useState(undefined)

  useEffect(() => {
    let active = true
    fetchPublicPage('about')
      .then((res) => active && setPage(res))
      .catch(() => active && setPage(null))
    return () => {
      active = false
    }
  }, [])

  useSeo({
    // No hardcoded literal fallback here — useSeo() itself falls back to
    // the global Site Settings SEO defaults when this page has none of its
    // own configured (see hooks/useSeo.js).
    title: page?.seo?.title,
    description: page?.seo?.description,
    canonical: 'https://womenshapingfutures.org/about',
  })

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <PageHeader eyebrow="About Us" title={page.title} description={page.subtitle} />

      <div className="container-editorial py-14">
        {page.heroMedia && (
          <div className="mb-14">
            <MediaImage media={page.heroMedia} variant="large" width={1200} height={600} aspect={2} priority className="w-full object-cover" />
          </div>
        )}
        <div className="mx-auto max-w-reading">
          <ArticleContent blocks={page.content} />
        </div>
      </div>
    </div>
  )
}
