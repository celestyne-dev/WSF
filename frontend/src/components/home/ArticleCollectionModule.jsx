import { useEffect, useState } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import { mapArticle } from '../../api/articles'
import { fetchPersonalizedHandpicked } from '../../api/site'
import ArticleCard from '../cards/ArticleCard'
import SectionHeading from '../ui/SectionHeading'
import SectionCtaLink from './SectionCtaLink'

// Article collections chosen by the server's page-level selection (backend
// services/homepage_editorial.py): `module.initialData.articles` is already
// de-duplicated against every module above (first placement wins). This
// component never selects Articles itself, so the server first paint
// (services/first_paint.py) and React always show the same stories.
const COLLECTION_LAYOUT = {
  career_moves: { section: 'border-t border-taupe-200 bg-cream py-14 sm:py-16', grid: 'mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4', card: 'grid' },
  right_now: { section: 'border-t border-taupe-200 py-14 sm:py-16', grid: 'mt-8 grid grid-cols-1 gap-8 lg:grid-cols-2', card: 'horizontal' },
  community_stories: { section: 'border-t border-taupe-200 bg-blush-50 py-14 sm:py-16', grid: 'mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3', card: 'grid' },
  expert_guidance: { section: 'border-t border-taupe-200 py-14 sm:py-16', grid: 'mt-8 grid grid-cols-1 gap-6 sm:grid-cols-3', card: 'expert' },
  handpicked: { section: 'border-t border-taupe-200 py-14 sm:py-16', grid: 'mt-8 grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-2 lg:grid-cols-4', card: 'grid' },
}

const DEFAULT_EYEBROWS = {
  career_moves: 'Career moves',
  right_now: 'Right now',
  community_stories: 'Community stories',
  expert_guidance: 'Expert-backed guidance',
  handpicked: 'Handpicked by WSF',
}

function ExpertArticleCard({ article, experts }) {
  const href = `/${article.slug}`
  const expert = experts?.[0]
  return (
    <article className="flex h-full flex-col rounded-card border border-taupe-200 bg-white p-6">
      {article.topic && (
        <Link to={`/topics/${article.topic.slug}`} className="eyebrow">
          {article.topic.name}
        </Link>
      )}
      <h3 className="mt-2 font-serif text-xl font-semibold leading-snug text-charcoal">
        <Link to={href} className="transition-colors hover:text-burgundy-600">
          {article.title}
        </Link>
      </h3>
      {article.excerpt && <p className="mt-2 line-clamp-3 text-sm text-charcoal-600">{article.excerpt}</p>}
      {expert && (
        <p className="mt-auto border-t border-taupe-200 pt-4 text-xs text-charcoal-600">
          <span className="font-semibold uppercase tracking-wide text-burgundy-600">{expert.label}</span>{' '}
          <Link to={expert.href} className="font-semibold text-charcoal hover:text-burgundy-600">
            {expert.name}
          </Link>
          {expert.line && <span className="block pt-0.5">{expert.line}</span>}
        </p>
      )}
    </article>
  )
}

export default function ArticleCollectionModule({ module }) {
  const layout = COLLECTION_LAYOUT[module.type] || COLLECTION_LAYOUT.career_moves
  const raw = module.initialData?.articles || []
  const [personal, setPersonal] = useState(null)
  const signedIn = useSelector((s) => Boolean(s.auth.user))

  // Handpicked only: a signed-in reader with Career Goals gets a goal-based
  // set (still excluding every Article placed elsewhere on the page).
  useEffect(() => {
    if (module.type !== 'handpicked' || !signedIn) return undefined
    let active = true
    fetchPersonalizedHandpicked()
      .then((data) => active && data?.personalized && data.articles?.length && setPersonal(data.articles))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [module.type, signedIn])

  const items = (personal || raw).map((a) => ({ article: mapArticle(a), experts: a.experts || [] }))
  if (!items.length) return null
  const eyebrow = personal ? 'Recommended for you' : module.eyebrow || DEFAULT_EYEBROWS[module.type]
  const heading = personal && module.personalizedHeading ? module.personalizedHeading : module.heading

  return (
    <section className={layout.section}>
      <div className="container-editorial">
        <SectionHeading eyebrow={eyebrow} heading={heading} subheading={module.subheading} />
        <div className={layout.grid}>
          {items.map(({ article, experts }) =>
            layout.card === 'expert' ? (
              <ExpertArticleCard key={article.id} article={article} experts={experts} />
            ) : (
              <ArticleCard key={article.id} article={article} variant={layout.card} />
            ),
          )}
        </div>
        <SectionCtaLink label={module.ctaLabel} url={module.ctaUrl} />
      </div>
    </section>
  )
}
