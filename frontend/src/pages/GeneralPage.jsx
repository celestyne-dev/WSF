import { useEffect, useState } from 'react'
import { fetchPublicPage } from '../api/pages'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import InstitutionalPageHero from '../components/pages/InstitutionalPageHero'
import InstitutionalPageShell from '../components/pages/InstitutionalPageShell'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'

// A published general (Studio-created) Page at /<slug>. ArticlePage owns
// the flat /:slug route and falls back to this when no Article has the
// slug; the server serves the same URL as a real 200
// (spa_shell._render_general_page_shell). Unknown slugs stay a 404 page.
export default function GeneralPage({ slug }) {
  // Keyed by slug so a client-side move between Pages shows the loader
  // without a synchronous reset inside the effect.
  const [loaded, setLoaded] = useState({ slug: null, page: undefined })
  const page = loaded.slug === slug ? loaded.page : undefined

  useEffect(() => {
    let active = true
    fetchPublicPage(slug)
      .then((res) => active && setLoaded({ slug, page: res?.pageType === 'general' ? res : null }))
      .catch(() => active && setLoaded({ slug, page: null }))
    return () => {
      active = false
    }
  }, [slug])

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
