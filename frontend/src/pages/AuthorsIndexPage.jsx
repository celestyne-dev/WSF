import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Search } from 'lucide-react'
import { fetchAuthors } from '../api/taxonomies'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import MediaImage from '../components/ui/MediaImage'
import PageLoader from '../components/ui/PageLoader'
import EmptyState from '../components/ui/EmptyState'

export default function AuthorsIndexPage() {
  const [query, setQuery] = useState('')
  const [authors, setAuthors] = useState(null)
  const [error, setError] = useState(null)

  useSeo({
    title: 'Authors | Women Shaping Futures',
    description: 'Meet the editors and writers behind Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/authors',
  })

  useEffect(() => {
    let active = true
    setAuthors(null)
    setError(null)
    fetchAuthors({ query, pageSize: 100 })
      .then((res) => active && setAuthors(res.items))
      .catch(() => active && setError('Something went wrong loading our authors. Please try again.'))
    return () => {
      active = false
    }
  }, [query])

  return (
    <div>
      <PageHeader eyebrow="Masthead" title="Our Authors & Editors" description="The reporters and editors researching, interviewing, and writing every Women Shaping Futures story." />
      <div className="container-editorial py-14">
        <div className="mb-8 flex max-w-sm items-center gap-2 border border-taupe-300 bg-white px-3 py-2">
          <Search size={15} className="shrink-0 text-charcoal-600" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search authors by name…" className="w-full text-sm focus:outline-none" />
        </div>

        {error && <EmptyState title="Couldn't load authors" description={error} />}
        {!error && authors === null && <PageLoader />}
        {!error && authors !== null && (
          authors.length ? (
            <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {authors.map((author) => (
                <Link key={author.id} to={`/authors/${author.slug}`} className="group flex items-start gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40">
                  <MediaImage media={author.photoMedia} variant="thumbnail" mediaPath={author.photo} alt={author.name} width={160} height={160} aspect={1} className="h-16 w-16 shrink-0 rounded-full object-cover" />
                  <div>
                    <h2 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{author.name}</h2>
                    {author.role && <p className="text-sm text-charcoal-600">{author.role}</p>}
                    {author.shortBio && <p className="mt-2 text-sm text-charcoal-600">{author.shortBio}</p>}
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="No authors match that search" description="Try a different name." />
          )
        )}
      </div>
    </div>
  )
}
