import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { X, ChevronDown } from 'lucide-react'
import { toggleMobileNav } from '../../features/navigation/uiSlice'

function isExternal(url) {
  return !!url && /^https?:\/\//i.test(url)
}

function NavItemLink({ item, onClick, className }) {
  if (!item.url) return null
  if (isExternal(item.url)) {
    return (
      <a
        href={item.url}
        onClick={onClick}
        target={item.openNewTab ? '_blank' : undefined}
        rel={item.openNewTab ? 'noopener noreferrer' : undefined}
        className={className}
      >
        {item.label}
      </a>
    )
  }
  return (
    <Link to={item.url} onClick={onClick} className={className}>
      {item.label}
    </Link>
  )
}

export default function MobileNav() {
  const open = useSelector((s) => s.ui.mobileNavOpen)
  const navigation = useSelector((s) => s.site.navigation)
  const dispatch = useDispatch()
  const [expanded, setExpanded] = useState(null)

  if (!open) return null
  const primary = navigation?.primary || []
  const secondaryNavigation = navigation?.secondary || []
  const socialLinks = navigation?.social || []

  function close() {
    dispatch(toggleMobileNav(false))
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-ivory lg:hidden" role="dialog" aria-modal="true">
      <div className="flex items-center justify-between border-b border-taupe-200 px-4 py-4">
        <span className="font-serif text-lg font-semibold text-charcoal">Menu</span>
        <button type="button" onClick={close} aria-label="Close menu" className="p-1 text-charcoal">
          <X size={24} />
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-4 py-4">
        <ul className="divide-y divide-taupe-200">
          {primary.map((item) => (
            <li key={item.id}>
              {item.children?.length ? (
                <div>
                  <button
                    type="button"
                    onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                    aria-expanded={expanded === item.id}
                    className="flex w-full items-center justify-between py-3 text-left font-serif text-lg text-charcoal"
                  >
                    {item.label}
                    <ChevronDown size={18} className={`transition-transform ${expanded === item.id ? 'rotate-180' : ''}`} />
                  </button>
                  {expanded === item.id && (
                    <ul className="pb-2 pl-3">
                      {item.children.map((child) => (
                        <li key={child.id}>
                          <NavItemLink
                            item={child}
                            onClick={close}
                            className="block py-2 text-sm text-charcoal-600 hover:text-burgundy-600"
                          />
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ) : (
                <NavItemLink item={item} onClick={close} className="block py-3 font-serif text-lg text-charcoal" />
              )}
            </li>
          ))}
        </ul>
        <ul className="mt-4 space-y-1 border-t border-taupe-200 pt-4">
          {secondaryNavigation.map((item) => (
            <li key={item.id}>
              <NavItemLink item={item} onClick={close} className="block py-2 text-sm font-medium text-charcoal-600 hover:text-burgundy-600" />
            </li>
          ))}
          <li>
            <Link to="/login" onClick={close} className="block py-2 text-sm font-medium text-charcoal-600 hover:text-burgundy-600">
              Login
            </Link>
          </li>
        </ul>
      </nav>
      <div className="flex gap-4 border-t border-taupe-200 px-4 py-4">
        {socialLinks.slice(0, 4).map((s) => (
          <a key={s.platform} href={s.url} target="_blank" rel="noreferrer" className="text-xs uppercase tracking-wide text-charcoal-600">
            {s.platform}
          </a>
        ))}
      </div>
    </div>
  )
}
