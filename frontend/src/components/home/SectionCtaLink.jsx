import { Link } from 'react-router-dom'
import { ArrowRight } from 'lucide-react'
import { externalRel, publicNavLink } from '../../utils/navigation'

// The optional single section link of Career Pathways / Content
// Collection: internal paths use the router, external URLs a real <a>.
// Renders nothing when label or destination is missing — never "/".
export default function SectionCtaLink({ label, url }) {
  const link = label ? publicNavLink({ url }) : null
  if (!link || link.kind === 'group') return null
  const className = 'group inline-flex items-center gap-1.5 text-sm font-semibold text-burgundy-600 transition-colors hover:text-burgundy-700'
  const content = (
    <>
      {label}
      <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
    </>
  )
  return (
    <div className="mt-8">
      {link.kind === 'external' ? (
        <a href={link.href} rel={externalRel(false)} className={className}>{content}</a>
      ) : (
        <Link to={link.to} className={className}>{content}</Link>
      )}
    </div>
  )
}
