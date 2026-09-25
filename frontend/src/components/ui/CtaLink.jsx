import { Link } from 'react-router-dom'

/**
 * A CMS-configured CTA URL is either an internal route ("/jobs") or a full
 * external https:// link (validated server-side in PageInput/Homepage
 * module schemas) — never both handled the same way: React Router's
 * <Link> can't navigate off-site, and a plain <a> would full-reload an
 * internal route. This picks the right element for whichever it got.
 */
export default function CtaLink({ to, className, children, ...rest }) {
  if (!to) return null
  if (to.startsWith('/')) {
    return (
      <Link to={to} className={className} {...rest}>
        {children}
      </Link>
    )
  }
  return (
    <a href={to} target="_blank" rel="noopener noreferrer" className={className} {...rest}>
      {children}
    </a>
  )
}
