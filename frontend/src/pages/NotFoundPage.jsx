import { Link } from 'react-router-dom'
import useSeo from '../hooks/useSeo'

export default function NotFoundPage() {
  useSeo({ title: 'Page Not Found | Women Shaping Futures', description: 'The page you are looking for could not be found.', robots: 'noindex, follow' })
  return (
    <div className="container-editorial flex flex-col items-center justify-center py-28 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 font-serif text-4xl font-semibold text-charcoal sm:text-5xl">We couldn’t find that page</h1>
      <p className="mt-4 max-w-md text-charcoal-600">
        The page you’re looking for may have moved or no longer exists. Try searching, or head back to the homepage.
      </p>
      <div className="mt-8 flex gap-4">
        <Link to="/" className="btn-primary">
          Back to homepage
        </Link>
        <Link to="/search" className="btn-secondary">
          Search WSF
        </Link>
      </div>
    </div>
  )
}
