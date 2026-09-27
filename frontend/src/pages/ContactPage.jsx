import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

export default function ContactPage() {
  const [page, setPage] = useState(undefined)

  useEffect(() => {
    let active = true
    fetchPublicPage('contact')
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
    canonical: 'https://womenshapingfutures.org/contact',
  })

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <PageHeader eyebrow="Contact" title={page.title} description={page.subtitle} />
      <div className="container-editorial max-w-reading py-14">
        <ArticleContent blocks={page.content} />
      </div>
    </div>
  )
}
