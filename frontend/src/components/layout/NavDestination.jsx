import { Link } from 'react-router-dom'
import { externalRel } from '../../utils/navigation'

// One header/mobile-nav destination from utils/megaMenu.js: an internal
// route is a router <Link>, an external URL a plain <a> (new tab only when
// the CMS item says so). Never a fallback to "/".
export default function NavDestination({ link, className, onClick, children, ...rest }) {
  if (link?.kind === 'external') {
    return (
      <a href={link.href} target={link.newTab ? '_blank' : undefined} rel={externalRel(link.newTab)} className={className} onClick={onClick} {...rest}>
        {children}
      </a>
    )
  }
  if (link?.kind === 'internal') {
    return (
      <Link to={link.to} className={className} onClick={onClick} {...rest}>
        {children}
      </Link>
    )
  }
  return null
}
