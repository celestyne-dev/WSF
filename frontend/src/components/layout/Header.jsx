import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { Search, Menu, User } from 'lucide-react'
import Logo from './Logo'
import { toggleMobileNav, toggleSearch } from '../../features/navigation/uiSlice'

export default function Header() {
  const navigation = useSelector((s) => s.site.navigation)
  const dispatch = useDispatch()
  const [openDropdown, setOpenDropdown] = useState(null)

  const primary = navigation?.primary || []

  return (
    <header className="sticky top-0 z-40 bg-ivory/95 backdrop-blur">
      <div className="hidden border-b border-taupe-200 bg-charcoal text-ivory lg:block">
        <div className="container-editorial flex h-9 items-center justify-between text-xs">
          <p className="tracking-wide text-ivory/80">
            The editorial platform for women shaping the future of business, leadership &amp; opportunity.
          </p>
          <div className="flex items-center gap-5">
            <Link to="/newsletter" className="tracking-wide hover:text-blush-200">
              WSF Weekly Newsletter
            </Link>
            <Link to="/partnerships" className="tracking-wide hover:text-blush-200">
              Partner With Us
            </Link>
          </div>
        </div>
      </div>

      <div className="border-b border-taupe-200">
        <div className="container-editorial flex items-center justify-between gap-4 py-3">
          <button
            type="button"
            onClick={() => dispatch(toggleMobileNav(true))}
            aria-label="Open menu"
            className="p-1 text-charcoal lg:hidden"
          >
            <Menu size={26} />
          </button>

          <Logo />

          <nav aria-label="Primary" className="hidden lg:block">
            <ul className="flex items-center gap-5 xl:gap-6">
              {primary.map((item) => (
                <li
                  key={item.id}
                  className="relative"
                  onMouseEnter={() => setOpenDropdown(item.id)}
                  onMouseLeave={() => setOpenDropdown(null)}
                >
                  <NavLink
                    to={item.url}
                    className={({ isActive }) =>
                      `flex items-center py-7 text-sm font-semibold uppercase tracking-wide text-charcoal transition-colors hover:text-burgundy-600 ${
                        isActive ? 'text-burgundy-600' : ''
                      }`
                    }
                  >
                    {item.label}
                  </NavLink>
                  {item.children?.length > 0 && openDropdown === item.id && (
                    <div className="absolute left-1/2 top-full w-56 -translate-x-1/2 border border-taupe-200 bg-ivory py-2 shadow-card">
                      {item.children.map((child) => (
                        <Link
                          key={child.label}
                          to={child.url}
                          className="block px-4 py-2 text-sm text-charcoal-600 hover:bg-blush-50 hover:text-burgundy-600"
                        >
                          {child.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          </nav>

          <div className="flex items-center gap-1 sm:gap-2">
            <button
              type="button"
              onClick={() => dispatch(toggleSearch(true))}
              aria-label="Search"
              className="p-2 text-charcoal transition-colors hover:text-burgundy-600"
            >
              <Search size={20} />
            </button>
            <Link to="/login" aria-label="Account" className="hidden p-2 text-charcoal transition-colors hover:text-burgundy-600 sm:block">
              <User size={20} />
            </Link>
            <Link to="/newsletter" className="ml-1 hidden bg-plum-600 px-4 py-2 text-xs font-semibold uppercase tracking-wide text-ivory transition-colors hover:bg-plum-700 md:inline-flex">
              Subscribe
            </Link>
          </div>
        </div>
      </div>
    </header>
  )
}
