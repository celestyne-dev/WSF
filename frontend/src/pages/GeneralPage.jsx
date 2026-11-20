import { useEffect, useState } from 'react'
import { consumeBootstrap } from '../utils/bootstrap'
import { fetchPublicPage } from '../api/pages'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import InstitutionalPageHero from '../components/pages/InstitutionalPageHero'
import InstitutionalPageShell from '../components/pages/InstitutionalPageShell'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'

// A published general (Studio-created) Page at /<slug>. Hard load:
// FlatSlugPage passes the server's bootstrap as `initialPage`, so the first
// commit is the final Page (matching the server prerender). Client-side
// navigation: ArticlePage falls back to this when no Article owns the slug,
// and it fetches the Page. Unknown or unpublished slugs show the 404 page.
export default function GeneralPage({ slug, initialPage = null }) {
  // Keyed by slug so a client-side move between Pages shows the loader
  // without a synchronous reset inside the effect.
  const [loaded, setLoaded] = useState(() => (initialPage ? { slug, page: initialPage } : { slug: null, page: undefined }))
  const page = loaded.slug === slug ? loaded.page : undefined

  useEffect(() => {
    // Hard load: the server's bootstrap already holds this Page (read by
    // FlatSlugPage); just clean the tag up, no request.
    if (initialPage && initialPage.slug === slug) {
      consumeBootstrap('page')
      return undefined
    }
    let active = true
    fetchPublicPage(slug)
      .then((res) => active && setLoaded({ slug, page: res?.pageType === 'general' ? res : null }))
      .catch(() => active && setLoaded({ slug, page: null }))
    return () => {
      active = false
    }
  }, [slug, initialPage])

  const canonical = page?.seo?.canonical || `https://womenshapingfutures.org/${slug}`
  useSeo(page ? { title: page.seo?.title || page.title, description: page.seo?.description || page.subtitle, canonical, robots: page.seo?.robots } : {})
  useBreadcrumbStructuredData(page ? [{ label: page.title }] : null, canonical)

  if (page === undefined) return <PageLoader />
  if (page === null) return <NotFoundPage />
  return (
    <div>
      <InstitutionalPageHero title={page.title} description={page.subtitle} />
      <InstitutionalPageShell heroMedia={page.heroMedia}>
        <ArticleContent blocks={page.content || []} />
      </InstitutionalPageShell>
    </div>
  )
}
