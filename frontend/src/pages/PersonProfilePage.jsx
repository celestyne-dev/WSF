import { useEffect, useMemo, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { Globe, Quote } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { fetchPersonBySlug, mapPerson } from '../api/people'
import { fetchArticles } from '../api/articles'
import { fetchSeriesBySlug } from '../api/taxonomies'
import { resolveImage, resolveAltText } from '../utils/media'
import useSeo from '../hooks/useSeo'
import { readBootstrap, consumeBootstrap } from '../utils/bootstrap'
import useBreadcrumbStructuredData from '../hooks/useBreadcrumbStructuredData'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleContent from '../components/article/ArticleContent'
import ArticleCard from '../components/cards/ArticleCard'
import SourceReferences from '../components/article/SourceReferences'
import { buildPersonStructuredData } from '../utils/profileStructuredData'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

// schema.org Person structured data — the data shape is the pure
// buildPersonStructuredData() (utils/profileStructuredData.js, mirroring
// spa_shell.py's _build_person_json_ld); this hook only owns the <script>.
function usePersonStructuredData(person, canonicalUrl) {
  useEffect(() => {
    if (!person) return
    const data = buildPersonStructuredData(person, canonicalUrl, {
      imageUrl: person.photo ? resolveImage(person.photo, { width: 600, height: 750 }) : undefined,
    })
    let el = document.head.querySelector('script[data-person-structured-data]')
    if (!el) {
      el = document.createElement('script')
      el.type = 'application/ld+json'
      el.setAttribute('data-person-structured-data', 'true')
      document.head.appendChild(el)
    }
    el.textContent = JSON.stringify(data)
    return () => el?.remove()
  }, [person, canonicalUrl])
}

// Conservative "same text" check so a profession identical to the title
// (e.g. both "Founder & CEO") is never shown twice in the header.
function normalizeLabel(value) {
  return (value || '').trim().replace(/\s+/g, ' ').toLowerCase()
}

export default function PersonProfilePage() {
  const { slug } = useParams()
  // AI Search / GEO Phase 1B — a hard load of /people/{slug} embeds this
  // exact public Person (spa_shell.py's _safe_public_person_payload) next
  // to its server-rendered profile, so the page can render immediately
  // instead of swapping that profile for a PageLoader while it refetches.
  // Memoized per slug: readBootstrap only reads the DOM (no side effect,
  // safe under StrictMode's double render), and a later SPA navigation —
  // to another slug, or back to this one after the tag was consumed —
  // gets null and fetches normally.
  const bootstrapPerson = useMemo(() => {
    const bootstrap = readBootstrap('person', slug)
    return bootstrap ? mapPerson(bootstrap.data) : null
  }, [slug])
  const [person, setPerson] = useState(() => bootstrapPerson ?? undefined)
  const [relatedArticles, setRelatedArticles] = useState([])
  // The bootstrap's series list is already published-only {slug, name}.
  const [seriesAppearances, setSeriesAppearances] = useState(() => bootstrapPerson?.series || [])
  const [error, setError] = useState(null)

  useEffect(() => {
    let active = true

    function loadRelatedArticles() {
      fetchArticles({ person: slug })
        .then((res) => active && setRelatedArticles(res.items))
        .catch(() => {})
    }

    if (bootstrapPerson) {
      // Person + series already initialized from the bootstrap above —
      // only drop the (now consumed) tag and load the related stories.
      consumeBootstrap('person')
      loadRelatedArticles()
      return () => {
        active = false
      }
    }

    setPerson(undefined)
    setError(null)

    fetchPersonBySlug(slug)
      .then((data) => {
        if (!active) return
        setPerson(data)
        if (!data) return

        loadRelatedArticles()

        // The real API already nests each Series ({slug, name}) in the
        // Person payload — used directly, no extra requests. Only mock-mode
        // data (slugs alone) still resolves names one by one.
        if (data.series) {
          setSeriesAppearances(data.series)
        } else {
          Promise.all((data.seriesSlugs || []).map((s) => fetchSeriesBySlug(s)))
            .then((results) => active && setSeriesAppearances(results.filter(Boolean)))
            .catch(() => {})
        }
      })
      .catch(() => {
        if (active) setError('Something went wrong loading this profile. Please try again.')
      })

    return () => {
      active = false
    }
  }, [slug, bootstrapPerson])

  const canonicalUrl = `https://womenshapingfutures.org/people/${slug}`
  // One effective canonical for useSeo, the Person JSON-LD and the
  // breadcrumb — the same resolved value spa_shell.py's _person_meta gives
  // all three server-side.
  const effectiveCanonicalUrl = person?.seo?.canonical || canonicalUrl

  // Social-share image priority, matching spa_shell.py's _person_meta: the
  // editor-picked SEO/OG image (person.seo.ogImage, resolved server-side
  // from seo.ogImageMediaId — see PersonSchema.get_seo) -> the portrait ->
  // useSeo's own global default. Alt text always comes from that SAME
  // image's Media record, never borrowed or derived from a filename.
  const hasExplicitOgImage = !!person?.seo?.ogImage
  const socialImagePath = hasExplicitOgImage ? person.seo.ogImage : person?.photo || null
  const socialImageAlt = hasExplicitOgImage ? person.seo.ogImageAlt || undefined : person?.photoMedia?.altText || undefined

  useSeo(
    person
      ? {
          title: person.seo?.title || `${person.name} | Women Shaping Futures`,
          description: person.seo?.description || person.shortBio,
          canonical: effectiveCanonicalUrl,
          image: socialImagePath ? resolveImage(socialImagePath, { width: 1200, height: 630 }) : undefined,
          imageAlt: socialImageAlt,
          robots: person.seo?.robots,
        }
      : {},
  )

  usePersonStructuredData(person, effectiveCanonicalUrl)
  useBreadcrumbStructuredData(person ? [{ label: 'People', to: '/people' }, { label: person.name }] : null, effectiveCanonicalUrl)

  if (error) return <div className="container-editorial py-20"><EmptyState title="Couldn't load this profile" description={error} /></div>
  if (person === undefined) return <PageLoader />
  if (person === null) return <NotFoundPage />

  const showProfession = !!person.profession && normalizeLabel(person.profession) !== normalizeLabel(person.title)

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'People', to: '/people' }, { label: person.name }]} />
          <div className="mt-6 grid grid-cols-1 gap-8 sm:grid-cols-[220px_1fr] sm:items-center">
            <MediaImage media={person.photoMedia} variant="medium" mediaPath={person.photo} alt={resolveAltText(person.photoMedia, person.name)} width={440} height={550} aspect={0.8} sizes="220px" className="aspect-[4/5] w-full max-w-[220px] object-cover" />
            <div>
              <h1 className="font-serif text-4xl font-semibold text-charcoal sm:text-5xl">
                {person.name} {person.pronouns && <span className="text-xl font-normal text-charcoal-600/60">({person.pronouns})</span>}
              </h1>
              {(person.title || person.organization) && (
                <p className="mt-2 text-lg text-charcoal-600">
                  {person.title}
                  {person.title && person.organization && ' at '}
                  {person.organizationSlug ? (
                    <Link to={`/organizations/${person.organizationSlug}`} className="font-medium text-burgundy-600 hover:underline">
                      {person.organization}
                    </Link>
                  ) : (
                    person.organization
                  )}
                </p>
              )}
              {showProfession && (
                <p className="mt-1 text-sm font-semibold uppercase tracking-wide text-charcoal-600/80">{person.profession}</p>
              )}
              {(person.location || person.industry) && (
                <p className="mt-1 text-sm text-charcoal-600">
                  {[person.location, person.industry].filter(Boolean).join(' · ')}
                </p>
              )}
              {person.shortBio && (
                <p className="mt-4 max-w-2xl font-serif text-lg leading-relaxed text-charcoal sm:text-xl">{person.shortBio}</p>
              )}
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

          {person.bio?.length > 0 && (
            <div>
              <h2 className="mt-10 font-serif text-2xl font-semibold text-charcoal">About</h2>
              <ArticleContent blocks={person.bio} variant="person" />
            </div>
          )}

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

          <SourceReferences sources={person.sources} id="person-sources" />
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
