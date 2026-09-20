import { useParams } from 'react-router-dom'
import { Globe } from 'lucide-react'
import SocialIcon from '../components/ui/SocialIcon'
import { getAuthorBySlug } from '../mock/authors'
import { getArticlesByAuthor } from '../mock/articles'
import useSeo from '../hooks/useSeo'
import Breadcrumb from '../components/ui/Breadcrumb'
import MediaImage from '../components/ui/MediaImage'
import ArticleCard from '../components/cards/ArticleCard'
import EmptyState from '../components/ui/EmptyState'
import NotFoundPage from './NotFoundPage'

export default function AuthorProfilePage() {
  const { slug } = useParams()
  const author = getAuthorBySlug(slug)
  if (!author) return <NotFoundPage />

  const articles = getArticlesByAuthor(slug)

  useSeo({
    title: `${author.name} | Women Shaping Futures`,
    description: author.shortBio,
    canonical: `https://womenshapingfutures.org/authors/${author.slug}`,
  })

  return (
    <div>
      <div className="border-b border-taupe-200 bg-cream py-10">
        <div className="container-editorial">
          <Breadcrumb items={[{ label: 'Authors', to: '/authors' }, { label: author.name }]} />
          <div className="mt-6 flex flex-col items-start gap-6 sm:flex-row sm:items-center">
            <MediaImage mediaPath={author.photo} alt={author.name} width={200} height={200} aspect={1} className="h-28 w-28 rounded-full object-cover" />
            <div>
              <h1 className="font-serif text-3xl font-semibold text-charcoal sm:text-4xl">{author.name}</h1>
              <p className="mt-1 text-base text-charcoal-600">{author.role}</p>
              <p className="mt-1 text-sm text-charcoal-600">{author.location}</p>
              <div className="mt-3 flex gap-4">
                {author.website && (
                  <a href={author.website} target="_blank" rel="noreferrer" aria-label="Website" className="text-charcoal-600 hover:text-burgundy-600">
                    <Globe size={17} />
                  </a>
                )}
                {author.social.linkedin && (
                  <a href={`https://linkedin.com/in/${author.social.linkedin}`} target="_blank" rel="noreferrer" aria-label="LinkedIn" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="linkedin" size={17} />
                  </a>
                )}
                {author.social.twitter && (
                  <a href={`https://twitter.com/${author.social.twitter}`} target="_blank" rel="noreferrer" aria-label="Twitter" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="twitter" size={17} />
                  </a>
                )}
                {author.social.instagram && (
                  <a href={`https://instagram.com/${author.social.instagram}`} target="_blank" rel="noreferrer" aria-label="Instagram" className="text-charcoal-600 hover:text-burgundy-600">
                    <SocialIcon name="instagram" size={17} />
                  </a>
                )}
              </div>
            </div>
          </div>
          <p className="mt-6 max-w-2xl text-base leading-relaxed text-charcoal-600">{author.bio}</p>
        </div>
      </div>

      <div className="container-editorial py-14">
        <p className="eyebrow mb-6">{articles.length} articles by {author.name}</p>
        {articles.length ? (
          <div className="grid grid-cols-1 gap-x-8 gap-y-12 sm:grid-cols-2 lg:grid-cols-3">
            {articles.map((a) => (
              <ArticleCard key={a.id} article={a} />
            ))}
          </div>
        ) : (
          <EmptyState title="No published articles yet" />
        )}
      </div>
    </div>
  )
}
