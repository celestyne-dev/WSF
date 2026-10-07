import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import { resolveMediaImage } from '../utils/media'
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
    // CMS SEO fields win; the Page's own title/subtitle are the next
    // fallback (both are editor-controlled), and only below that does
    // useSeo() reach for the global Site Settings SEO defaults.
    title: page?.seo?.title || page?.title,
    description: page?.seo?.description || page?.subtitle,
    canonical: 'https://womenshapingfutures.org/about',
    image: page?.heroMedia ? resolveMediaImage(page.heroMedia, { variant: 'large' }).src : undefined,
  })

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  return (
    <div>
      <PageHeader eyebrow="About Us" title={page.title} description={page.subtitle} />

      <div className="container-editorial py-14">
        {page.heroMedia && (
          <div className="mb-14 flex justify-center bg-cream">
            <MediaImage
              media={page.heroMedia}
              variant="large"
              width={1200}
              height={800}
              priority
              className="h-auto max-h-[480px] w-full object-contain"
            />
          </div>
        )}
        <div className="mx-auto max-w-reading lg:max-w-3xl xl:max-w-4xl">
          <ArticleContent blocks={page.content} />
        </div>
      </div>
    </div>
  )
}
