import { newsletterStats } from '../../mock/newsletter'
import NewsletterForm from '../ui/NewsletterForm'

export default function NewsletterModule({ module }) {
  return (
    <section className="border-t border-taupe-200 bg-charcoal py-16 text-ivory sm:py-20">
      <div className="container-editorial flex flex-col items-center text-center">
        <p className="eyebrow !text-blush-200">{module.heading}</p>
        <h2 className="mt-3 max-w-xl font-serif text-3xl font-semibold sm:text-4xl">{module.subheading}</h2>
        <p className="mt-3 text-sm text-ivory/70">
          Join {new Intl.NumberFormat('en-US').format(newsletterStats.subscriberCount)}+ readers who start their week with WSF.
        </p>
        <div className="mt-7">
          <NewsletterForm variant="dark" source="homepage" />
        </div>
      </div>
    </section>
  )
}
