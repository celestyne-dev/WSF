import NewsletterForm from '../ui/NewsletterForm'

// "Get new opportunities in your inbox": the normal WSF Weekly signup (same
// subscriber list), attributed to the listing it sits on via `placement`.
export default function ListingNewsletterCta({ placement }) {
  return (
    <section aria-labelledby={`${placement}-newsletter`} className="mt-14 rounded-card border border-taupe-200 bg-cream px-5 py-8 sm:px-8">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-xl">
          <h2 id={`${placement}-newsletter`} className="font-serif text-2xl font-semibold text-charcoal">Get new opportunities in your inbox.</h2>
          <p className="mt-2 text-sm text-charcoal-700">Receive new jobs, scholarships, grants and career opportunities from WSF.</p>
        </div>
        <div className="w-full max-w-md">
          <NewsletterForm source={placement} buttonLabel="Join WSF Weekly" />
        </div>
      </div>
    </section>
  )
}
