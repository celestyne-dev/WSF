import { Link } from 'react-router-dom'
import { useSelector } from 'react-redux'
import Logo from './Logo'
import NewsletterForm from '../ui/NewsletterForm'
import SocialIcon from '../ui/SocialIcon'

function isExternal(url) {
  return !!url && /^https?:\/\//i.test(url)
}

function FooterLink({ link }) {
  if (!link.url) return null
  if (isExternal(link.url)) {
    return (
      <a
        href={link.url}
        target={link.openNewTab ? '_blank' : undefined}
        rel={link.openNewTab ? 'noopener noreferrer' : undefined}
        className="text-sm text-ivory/85 transition-colors hover:text-blush-200"
      >
        {link.label}
      </a>
    )
  }
  return (
    <Link to={link.url} className="text-sm text-ivory/85 transition-colors hover:text-blush-200">
      {link.label}
    </Link>
  )
}

export default function Footer() {
  // Loads via loadFooter() in PublicLayout — falls back to an empty/minimal
  // shape before that resolves (or if it fails) so the footer never crashes
  // the page, matching Header.jsx's existing `navigation?.primary || []`
  // fallback pattern for the same reason.
  const footer = useSelector((s) => s.site.footer) || {}
  const groups = footer.groups || []
  const social = footer.social || []

  return (
    <footer className="bg-charcoal-800 text-ivory">
      {footer.newsletterVisible !== false && (footer.newsletterHeading || footer.newsletterDescription) && (
        <div className="container-editorial border-b border-ivory/10 py-14">
          <div className="flex flex-col items-start justify-between gap-6 lg:flex-row lg:items-center">
            <div>
              <p className="eyebrow !text-blush-200">{footer.newsletterHeading}</p>
              <h2 className="mt-2 font-serif text-2xl font-semibold sm:text-3xl">{footer.newsletterDescription}</h2>
            </div>
            <NewsletterForm variant="dark" source="footer" />
          </div>
        </div>
      )}

      {(footer.brandDescription || groups.length > 0) && (
        <div className="container-editorial grid grid-cols-1 gap-10 py-14 sm:grid-cols-2 lg:grid-cols-5">
          {footer.brandDescription && (
            <div className="sm:col-span-2 lg:col-span-1">
              <Logo light />
              <p className="mt-4 max-w-xs text-sm text-ivory/70">{footer.brandDescription}</p>
            </div>
          )}
          {groups.map((group) => (
            <div key={group.key}>
              <h3 className="text-xs font-semibold uppercase tracking-widest2 text-ivory/60">{group.heading}</h3>
              <ul className="mt-4 space-y-2.5">
                {group.links.map((link) => (
                  <li key={link.id}>
                    <FooterLink link={link} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      <div className="container-editorial flex flex-col items-center justify-between gap-6 border-t border-ivory/10 py-8 sm:flex-row">
        {!footer.brandDescription && <Logo light />}
        <div className="flex items-center gap-4">
          {social.map((s) => (
            <a key={s.platform} href={s.url} target="_blank" rel="noreferrer" aria-label={s.label} className="text-ivory/70 transition-colors hover:text-ivory">
              <SocialIcon name={s.platform} size={18} />
            </a>
          ))}
        </div>
        <div className="flex flex-col items-center gap-1 text-center sm:items-end sm:text-right">
          <p className="text-xs text-ivory/50">
            &copy; {new Date().getFullYear()} {footer.copyrightText || 'Women Shaping Futures. All rights reserved.'}
          </p>
          {footer.contactEmail && (
            <a href={`mailto:${footer.contactEmail}`} className="text-xs text-ivory/50 hover:text-ivory">
              {footer.contactEmail}
            </a>
          )}
        </div>
      </div>
    </footer>
  )
}
