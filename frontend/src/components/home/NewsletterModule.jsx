import { useEffect, useState } from 'react'
import { fetchNewsletterArchive } from '../../api/newsletter'
import NewsletterForm from '../ui/NewsletterForm'

export default function NewsletterModule({ module }) {
  const initialCount = module.initialData?.subscriberCount
  const [subscriberCount, setSubscriberCount] = useState(initialCount ?? null)

  useEffect(() => {
    if (initialCount != null) return undefined
    let active = true
    fetchNewsletterArchive()
      .then((data) => active && setSubscriberCount(data.stats?.subscriberCount ?? null))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [initialCount])

  return (
    <section className="border-t border-taupe-200 bg-charcoal py-16 text-ivory sm:py-20">
      <div className="container-editorial flex flex-col items-center text-center">
        <p className="eyebrow !text-blush-200">{module.heading}</p>
        <h2 className="mt-3 max-w-xl font-serif text-3xl font-semibold sm:text-4xl">{module.subheading}</h2>
        {subscriberCount != null && (
          <p className="mt-3 text-sm text-ivory/70">
            Join {new Intl.NumberFormat('en-US').format(subscriberCount)}+ readers who start their week with WSF.
          </p>
        )}
        {module.benefits?.length > 0 && (
          <ul className="mt-6 grid max-w-2xl grid-cols-1 gap-x-8 gap-y-2 text-left text-sm text-ivory/85 sm:grid-cols-2">
            {module.benefits.map((benefit) => (
              <li key={benefit} className="flex items-start gap-2">
                <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 shrink-0 bg-blush-200" />
                {benefit}
              </li>
            ))}
          </ul>
        )}
        <div className="mt-7">
          <NewsletterForm variant="dark" source="homepage" />
        </div>
      </div>
    </section>
  )
}
