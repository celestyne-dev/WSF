import { Link } from 'react-router-dom'
import { authors } from '../mock/authors'
import useSeo from '../hooks/useSeo'
import PageHeader from '../components/ui/PageHeader'
import CloudinaryImage from '../components/ui/CloudinaryImage'

export default function AuthorsIndexPage() {
  useSeo({
    title: 'Authors | Women Shaping Futures',
    description: 'Meet the editors and writers behind Women Shaping Futures.',
    canonical: 'https://womenshapingfutures.org/authors',
  })

  return (
    <div>
      <PageHeader eyebrow="Masthead" title="Our Authors & Editors" description="The reporters and editors researching, interviewing, and writing every Women Shaping Futures story." />
      <div className="container-editorial py-14">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {authors.map((author) => (
            <Link key={author.id} to={`/authors/${author.slug}`} className="group flex items-start gap-4 border border-taupe-200 bg-white p-5 transition-colors hover:border-burgundy-500/40">
              <CloudinaryImage publicId={author.photo} alt={author.name} width={160} height={160} aspect={1} className="h-16 w-16 shrink-0 rounded-full object-cover" />
              <div>
                <h2 className="font-serif text-lg font-semibold text-charcoal transition-colors group-hover:text-burgundy-600">{author.name}</h2>
                <p className="text-sm text-charcoal-600">{author.role}</p>
                <p className="mt-2 text-sm text-charcoal-600">{author.shortBio}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
