import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import Logo from './Logo'
import NewsletterForm from '../ui/NewsletterForm'
import SocialIcon from '../ui/SocialIcon'

export default function Footer() {
  const navigation = useSelector((s) => s.site.navigation)
  const footer = navigation?.footer || {}
  const social = navigation?.social || []

  return (
    <footer className="bg-charcoal-800 text-ivory">
      <div className="container-editorial border-b border-ivory/10 py-14">
        <div className="flex flex-col items-start justify-between gap-6 lg:flex-row lg:items-center">
          <div>
            <p className="eyebrow !text-blush-200">WSF Weekly</p>
            <h2 className="mt-2 font-serif text-2xl font-semibold sm:text-3xl">
              Stories, jobs, and opportunities — every Thursday.
            </h2>
          </div>
          <NewsletterForm variant="dark" source="footer" />
        </div>
      </div>

      <div className="container-editorial grid grid-cols-2 gap-10 py-14 sm:grid-cols-4">
        {Object.values(footer).map((group) => (
          <div key={group.heading}>
            <h3 className="text-xs font-semibold uppercase tracking-widest2 text-ivory/60">{group.heading}</h3>
            <ul className="mt-4 space-y-2.5">
              {group.links.map((link) => (
                <li key={link.label}>
                  <Link to={link.url} className="text-sm text-ivory/85 transition-colors hover:text-blush-200">
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="container-editorial flex flex-col items-center justify-between gap-6 border-t border-ivory/10 py-8 sm:flex-row">
        <Logo light />
        <div className="flex items-center gap-4">
          {social.map((s) => (
            <a key={s.platform} href={s.url} target="_blank" rel="noreferrer" aria-label={s.platform} className="text-ivory/70 transition-colors hover:text-ivory">
              <SocialIcon name={s.platform} size={18} />
            </a>
          ))}
        </div>
        <p className="text-xs text-ivory/50">&copy; {new Date().getFullYear()} Women Shaping Futures. All rights reserved.</p>
      </div>
    </footer>
  )
}
