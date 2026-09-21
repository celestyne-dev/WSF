import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, Quote } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { fetchPersonBySlug } from '../api/people'
import { fetchArticles } from '../api/articles'
import { fetchSeriesBySlug } from '../api/taxonomies'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleCard from '../components/cards/ArticleCard'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

export default function PersonProfilePage() {
  const { slug } = useParams()
  const [person, setPerson] = useState(undefined)
  const [relatedArticles, setRelatedArticles] = useState([])
  const [seriesAppearances, setSeriesAppearances] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true
    setPerson(undefined)
    setError(null)

    fetchPersonBySlug(slug)
      .then((data) => {
        if (!active) return
        setPerson(data)
        if (!data) return

        fetchArticles({ person: slug })
          .then((res) => active && setRelatedArticles(res.items))
          .catch(() => {})

        Promise.all((data.seriesSlugs || []).map((s) => fetchSeriesBySlug(s)))
          .then((results) => active && setSeriesAppearances(results.filter(Boolean)))
          .catch(() => {})
      })
      .catch(() => {
        if (active) setError('Something went wrong loading this profile. Please try again.')
      })

    return () => {
      active = false
    }
  }, [slug])

  useSeo(
    person
      ? {
          title: `${person.name} | Women Shaping Futures`,
          description: person.shortBio,
          canonical: `https://womenshapingfutures.org/people/${person.slug}`,
          image: undefined,
        }
      : {},
  )

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this profile" description={error} /></div>
  if (person === undefined) return <PageLoader />
  if (person === null) return <NotFoundPage />

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'People', to: '/people' }, { label: person.name }]} />
          <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-[220px_1fr] sm:items-center">
            <MediaImage media={person.photoMedia} variant="medium" mediaPath={person.photo} alt={person.name} width={440} height={550} aspect={0.8} className="aspect-[4/5] w-full max-w-[220px] object-cover" />
            <div>
              <h1 className="font-serif text-4xl font-semibold text-charcoal sm:text-5xl">{person.name}</h1>
              <p className="mt-2 text-lg text-charcoal-600">
                {person.title}
                {person.organizationSlug ? (
                  <>
                    {' at '}
                    <Link to={`/organizations/${person.organizationSlug}`} className="font-medium text-burgundy-600 hover:underline">
                      {person.organization}
                    </Link>
                  </>
                ) : (
                  person.organization && ` at ${person.organization}`
                )}
              </p>
              <p className="mt-1 text-sm text-charcoal-600">
                {person.location} &middot; {person.industry}
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {person.expertise.map((e) => (
                  <span key={e} className="bg-taupe-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-charcoal-600">
                    {e}
                  </span>
                ))}
              </div>
              <div className="mt-5 flex items-center gap-4">
                {person.website && (
                  <a href={person.website} target="_blank" rel="noreferrer" aria-label="Website" className="text-charcoal-600 hover:text-burgundy-600">
                    <Globe size={18} />
                  </a>
                )}
                {person.social.linkedin && (
                  <a href={`https://linkedin.com/in/${person.social.linkedin}`} target="_blank" rel="noreferrer" aria-label="LinkedIn" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="linkedin" size={18} />
                  </a>
                )}
                {person.social.twitter && (
                  <a href={`https://twitter.com/${person.social.twitter}`} target="_blank" rel="noreferrer" aria-label="Twitter" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="twitter" size={18} />
                  </a>
                )}
                {person.social.instagram && (
                  <a href={`https://instagram.com/${person.social.instagram}`} target="_blank" rel="noreferrer" aria-label="Instagram" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="instagram" size={18} />
                  </a>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="container-editorial grid grid-cols-1 gap-14 py-14 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="max-w-reading">
          {person.featuredQuote && (
            <blockquote className="border-y border-taupe-200 py-8 text-center">
              <Quote className="mx-auto mb-3 text-burgundy-500/50" size={26} />
              <p className="font-serif text-2xl font-medium italic text-charcoal">{person.featuredQuote}</p>
            </blockquote>
          )}

          <h2 className="mt-10 font-serif text-2xl font-semibold text-charcoal">About</h2>
          <p className="mt-4 text-lg leading-[1.85] text-charcoal-600">{person.bio}</p>

          {person.careerTimeline?.length > 0 && (
            <div className="mt-10">
              <h2 className="font-serif text-2xl font-semibold text-charcoal">Career Timeline</h2>
              <ol className="mt-5 space-y-5 border-l border-taupe-300 pl-6">
                {person.careerTimeline.map((item) => (
                  <li key={item.year} className="relative">
                    <span className="absolute -left-[29px] top-1.5 h-2.5 w-2.5 rounded-full bg-burgundy-500" />
                    <p className="text-sm font-semibold uppercase tracking-wide text-burgundy-600">{item.year}</p>
                    <p className="mt-0.5 text-base text-charcoal">{item.title}</p>
                  </li>
                ))}
              </ol>
            </div>
          )}

          {person.achievements?.length > 0 && (
            <div className="mt-10">
              <h2 className="font-serif text-2xl font-semibold text-charcoal">Achievements</h2>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-base text-charcoal-600">
                {person.achievements.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}

          {person.awards?.length > 0 && (
            <div className="mt-10">
              <h2 className="font-serif text-2xl font-semibold text-charcoal">Awards</h2>
              <ul className="mt-4 list-disc space-y-2 pl-5 text-base text-charcoal-600">
                {person.awards.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        <aside className="space-y-8">
          {seriesAppearances.length > 0 && (
            <div>
              <p className="eyebrow mb-3">Featured in</p>
              <ul className="space-y-2">
                {seriesAppearances.map((s) => (
                  <li key={s.slug}>
                    <Link to={`/series/${s.slug}`} className="font-serif text-base font-medium text-charcoal hover:text-burgundy-600">
                      {s.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </aside>
      </div>

      {relatedArticles.length > 0 && (
        <div className="container-editorial border-t border-taupe-200 py-14">
          <p className="eyebrow mb-6">Stories featuring {person.name}</p>
          <div className="grid grid-cols-1 gap-x-8 gap-y-10 sm:grid-cols-3">
            {relatedArticles.map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
