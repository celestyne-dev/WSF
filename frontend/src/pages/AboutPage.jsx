import { useEffect, useState } from 'react'
import { fetchAuthors } from '../api/taxonomies'
import { fetchAudienceStats } from '../api/site'
import { fetchPublicPage } from '../api/pages'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

export default function AboutPage() {
  const [page, setPage] = useState(undefined)
  const [authors, setAuthors] = useState([])
  const [stats, setStats] = useState(null)

  useEffect(() => {
    let active = true
    fetchPublicPage('about')
      .then((res) => active && setPage(res))
      .catch(() => active && setPage(null))
    fetchAuthors()
      .then((res) => active && setAuthors(res.items))
      .catch(() => {})
    fetchAudienceStats()
      .then((data) => active && setStats(data))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [])

  useSeo({
    title: page?.seo?.title || 'About Women Shaping Futures',
    description: page?.seo?.description || 'Women Shaping Futures is a global media, opportunity, and community platform for ambitious women.',
    canonical: 'https://womenshapingfutures.org/about',
  })

  if (page === undefined) return <PageLoader />
  if (page === null) return <EmptyState title="This page isn't available right now" description="Please check back shortly." />

  // The mission/hero description can incorporate live reach numbers once
  // they've loaded; the page's own CMS-authored subtitle is the fallback
  // shown immediately and whenever stats aren't available.
  const description = stats
    ? `Women Shaping Futures started in 2019 as a small LinkedIn page sharing stories of women in business. Today, we're a global editorial and opportunity platform reaching more than ${new Intl.NumberFormat('en-US').format(stats.linkedinFollowers)} people across ${stats.countriesReached} countries, with particularly strong readership in the United States.`
    : page.subtitle

  return (
    <div>
      <PageHeader eyebrow="About Us" title={page.title} description={description} />

      <div className="container-editorial max-w-reading py-14">
        <ArticleContent blocks={page.content} />
      </div>

      <div className="border-t border-taupe-200 bg-cream py-14">
        <div className="container-editorial">
          <h2 className="font-serif text-2xl font-semibold text-charcoal">Our team</h2>
          <div className="mt-8 grid grid-cols-2 gap-6 sm:grid-cols-3 lg:grid-cols-5">
            {authors.map((a) => (
              <div key={a.id} className="text-center">
                <MediaImage media={a.photoMedia} variant="thumbnail" mediaPath={a.photo} alt={a.name} width={200} height={200} aspect={1} className="mx-auto h-20 w-20 rounded-full object-cover" />
                <p className="mt-2 font-serif text-sm font-semibold text-charcoal">{a.name}</p>
                <p className="text-xs text-charcoal-600">{a.role}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
