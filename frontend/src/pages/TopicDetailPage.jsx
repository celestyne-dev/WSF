import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { fetchTopicBySlug, fetchTopicHub, mapTopicDetail, mapTopicHub } from '../api/taxonomies'
import { readBootstrap, consumeBootstrap } from '../utils/bootstrap'
import useSeo from '../hooks/useSeo'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import { resolveImage } from '../utils/media'
import Breadcrumb from '../components/ui/Breadcrumb'
import SectionHeading from '../components/ui/SectionHeading'
import ArticleCard from '../components/cards/ArticleCard'
import LearningProgramCard from '../components/cards/LearningProgramCard'
import ResourceCard from '../components/cards/ResourceCard'
import OpportunityCard from '../components/cards/OpportunityCard'
import ArticleContent from '../components/article/ArticleContent'
import SourceReferences from '../components/article/SourceReferences'
import ProfilePreviewList from '../components/article/ProfilePreviewList'
import NewsletterForm from '../components/ui/NewsletterForm'
import EmptyState from '../components/ui/EmptyState'
import PageLoader from '../components/ui/PageLoader'
import NotFoundPage from './NotFoundPage'

// A Topic as a destination page. Every section comes from ONE server
// selection (backend services/topic_hub.py): Start here -> Latest ->
// Editor's picks never repeat an Article, and React never re-selects. The
// server first paint (services/first_paint.py render_topic_hub) mirrors this.
function readTopicBootstrap(slug) {
  const bootstrap = readBootstrap('topic', slug)
  return bootstrap?.data ? { topic: mapTopicDetail(bootstrap.data.topic), hub: mapTopicHub(bootstrap.data.hub) } : null
}

export default function TopicDetailPage() {
  const { slug } = useParams()
  const [state, setState] = useState(() => readTopicBootstrap(slug) || undefined)
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    const boot = readTopicBootstrap(slug)
    if (boot) {
      consumeBootstrap('topic')
      setState(boot)
      return undefined
    }
    setState(undefined)
    setError(null)
    fetchTopicBySlug(slug)
      .then((topic) => {
        if (!active) return
        if (!topic) {
          setState(null)
          return
        }
        fetchTopicHub(slug)
          .then((hub) => active && setState({ topic, hub }))
          .catch(() => active && setState({ topic, hub: mapTopicHub({}) }))
      })
      .catch(() => active && setError('Something went wrong loading this topic. Please try again.'))
    return () => {
      active = false
    }
  }, [slug])

  const topic = state?.topic
  const canonical = topic ? topic.seo?.canonical || `https://womenshapingfutures.org/topics/${topic.slug}` : null
  useSeo(
    topic
      ? {
          title: topic.seo?.title || `${topic.name} | Women Shaping Futures`,
          description: topic.seo?.description || topic.description,
          canonical,
          robots: topic.seo?.robots,
          image: topic.heroMedia ? resolveImage(topic.heroMedia, { width: 1200, height: 630 }) : undefined,
        }
      : {},
  )
  useBreadcrumbStructuredData(topic ? [{ label: 'Topics', to: '/topics' }, { label: topic.name }] : null, canonical)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this topic" description={error} /></div>
  if (state === undefined) return <PageLoader />
  if (state === null) return <NotFoundPage />

  const { hub } = state
  const hasArticles = hub.startHere.length + hub.latest.length + hub.editorsPicks.length > 0

  return (
    <div>
      <section className="border-b border-taupe-200 bg-cream">
        <div className="container-editorial py-14 sm:py-16">
          <Breadcrumb items={[{ label: 'Topics', to: '/topics' }, { label: topic.name }]} />
          <p className="eyebrow mt-6">Topic</p>
          <h1 className="mt-3 max-w-3xl font-serif text-4xl font-semibold leading-tight text-charcoal sm:text-5xl">{topic.name}</h1>
          {topic.description && <p className="mt-4 max-w-2xl text-lg text-charcoal-600">{topic.description}</p>}
          {hub.relatedTopics.length > 0 && (
            <nav aria-label="Related topics" className="mt-8">
              <p className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">Browse related topics</p>
              <ul className="mt-3 flex flex-wrap gap-2">
                {hub.relatedTopics.map((t) => (
                  <li key={t.slug}>
                    <Link to={`/topics/${t.slug}`} className="inline-flex border border-taupe-300 bg-white px-3 py-1.5 text-sm font-medium text-charcoal transition-colors hover:border-burgundy-500 hover:text-burgundy-600">
                      {t.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </nav>
          )}
        </div>
      </section>

      {topic.content?.length > 0 && (
        <div className="container-editorial pt-12">
          <div className="max-w-reading">
            <ArticleContent blocks={topic.content} />
          </div>
        </div>
      )}

      {hub.startHere.length > 0 && (
        <section className="py-14 sm:py-16">
          <div className="container-editorial">
            <SectionHeading eyebrow="Start here" heading={`Begin with ${topic.name}`} />
            <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3">
              {hub.startHere.map((a) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
          </div>
        </section>
      )}

      {hub.latest.length > 0 && (
        <section className="border-t border-taupe-200 py-14 sm:py-16">
          <div className="container-editorial">
            <SectionHeading eyebrow="Latest" heading={`New in ${topic.name}`} />
            <div className="mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-3">
              {hub.latest.map((a) => (
                <ArticleCard key={a.id} article={a} />
              ))}
            </div>
          </div>
        </section>
      )}

      {hub.editorsPicks.length > 0 && (
        <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
          <div className="container-editorial">
            <SectionHeading eyebrow="Editor's picks" heading="Most useful" />
            <div className="mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2">
              {hub.editorsPicks.map((a) => (
                <ArticleCard key={a.id} article={a} variant="horizontal" />
              ))}
            </div>
          </div>
        </section>
      )}

      {!hasArticles && (
        <div className="container-editorial py-14">
          <EmptyState title="No stories yet" description="We haven't published a story on this topic yet — check back soon." />
        </div>
      )}

      {hub.learning.length > 0 && (
        <section className="border-t border-taupe-200 py-14 sm:py-16">
          <div className="container-editorial">
            <SectionHeading eyebrow="From WSF Learning" heading={`Learn more about ${topic.name}`} viewAllHref="/learning" />
            <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-3">
              {hub.learning.map((p) => (
                <LearningProgramCard key={p.id} program={p} />
              ))}
            </div>
          </div>
        </section>
      )}

      {hub.resources.length > 0 && (
        <section className="border-t border-taupe-200 bg-cream py-14 sm:py-16">
          <div className="container-editorial">
            <SectionHeading eyebrow="Career tools" heading="Tools worth using" viewAllHref="/resources" />
            <div className="mt-8 grid grid-cols-1 gap-8 sm:grid-cols-3">
              {hub.resources.map((r) => (
                <ResourceCard key={r.id} resource={r} />
              ))}
            </div>
          </div>
        </section>
      )}

      {hub.opportunities.length > 0 && (
        <section className="border-t border-taupe-200 py-14 sm:py-16">
          <div className="container-editorial">
            <SectionHeading eyebrow="Opportunities" heading="Open now" viewAllHref="/opportunities" />
            <div className="mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3">
              {hub.opportunities.map((o) => (
                <OpportunityCard key={o.id} opportunity={o} />
              ))}
            </div>
          </div>
        </section>
      )}

      <div className="container-editorial">
        <ProfilePreviewList id="topic-contributors" heading="Contributors covering this topic" items={topic.contributors} basePath="/authors" metaKey="role" />
        {topic.sources?.length > 0 && (
          <div className="max-w-reading">
            <SourceReferences sources={topic.sources} id="topic-sources" />
          </div>
        )}
      </div>

      <section aria-labelledby="topic-newsletter" className="container-editorial py-16">
        <div className="mx-auto max-w-[1064px] rounded-card bg-plum-600 px-6 py-10 text-center sm:px-10">
          <h2 id="topic-newsletter" className="font-serif text-2xl font-semibold text-ivory sm:text-3xl">
            Get WSF Weekly
          </h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-ivory/85">Career guidance, stories and opportunities in one email.</p>
          <div className="mx-auto mt-6 flex max-w-md justify-center">
            <NewsletterForm variant="dark" source={`topic-${topic.slug}`} />
          </div>
        </div>
      </section>
    </div>
  )
}
