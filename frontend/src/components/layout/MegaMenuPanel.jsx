import { ArrowRight } from 'lucide-react'
import NavDestination from './NavDestination'
import { NAV_ICONS } from './navIcons'

const WIDTH_BY_COLUMNS = { 1: 'max-w-[760px]', 2: 'max-w-[900px]', 3: 'max-w-[980px]' }
const GRID_BY_COLUMNS = { 1: 'grid-cols-1', 2: 'grid-cols-2', 3: 'grid-cols-3' }

// Up to three columns; any further groups stack in the last column.
function toColumns(groups) {
  if (groups.length <= 3) return groups.map((g) => [g])
  return [[groups[0]], [groups[1]], groups.slice(2)]
}

// The desktop mega-menu panel for one top-level entry. Positioned by the
// Header (absolute, directly beneath it, overlaying page content) so it
// never reflows the page. Closed panels stay in the DOM with `hidden`,
// out of the accessibility tree and tab order.
export default function MegaMenuPanel({ entry, id, open, onNavigate, onPointerEnter, onPointerLeave }) {
  const { menu } = entry
  const columns = toColumns(menu.groups)
  const count = Math.max(1, Math.min(columns.length, 3))
  const Icon = menu.icon ? NAV_ICONS[menu.icon] : null

  return (
    <div
      id={id}
      hidden={!open}
      className="pointer-events-none absolute inset-x-0 top-full z-50 px-4 pt-2"
      onPointerEnter={onPointerEnter}
      onPointerLeave={onPointerLeave}
    >
      <div
        className={`pointer-events-auto mx-auto grid ${WIDTH_BY_COLUMNS[count]} grid-cols-[minmax(0,32%)_minmax(0,1fr)] overflow-hidden rounded-surface border border-taupe-200 bg-white shadow-[0_24px_48px_-16px_rgba(36,31,33,0.22)]`}
      >
        <div className="flex flex-col bg-cream p-8">
          {Icon && (
            <span className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-full bg-ivory text-burgundy-600">
              <Icon size={18} aria-hidden="true" />
            </span>
          )}
          <p className="font-serif text-2xl font-semibold text-charcoal">{menu.title}</p>
          {menu.description && <p className="mt-2 text-sm leading-relaxed text-charcoal-600">{menu.description}</p>}
          {menu.cta && (
            <NavDestination
              link={menu.cta.link}
              onClick={onNavigate}
              className="mt-auto inline-flex items-center gap-1.5 pt-6 text-sm font-semibold text-burgundy-600 hover:text-burgundy-700 hover:underline"
            >
              {menu.cta.label} <ArrowRight size={15} aria-hidden="true" />
            </NavDestination>
          )}
        </div>
        <div className={`grid ${GRID_BY_COLUMNS[count]} gap-x-8 gap-y-6 p-8`}>
          {columns.map((groups) => (
            <div key={groups[0].key} className="space-y-6">
              {groups.map((group) => (
                <div key={group.key}>
                  {group.label && (
                    <p className="mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-burgundy-600/80">{group.label}</p>
                  )}
                  <ul className="space-y-1">
                    {group.links.map((item) => {
                      const LinkIcon = item.icon ? NAV_ICONS[item.icon] : null
                      return (
                        <li key={item.id}>
                          <NavDestination
                            link={item.link}
                            onClick={onNavigate}
                            className="group -mx-3 flex gap-3 rounded-control px-3 py-2.5 transition-colors hover:bg-cream focus-visible:bg-cream"
                          >
                            {LinkIcon && <LinkIcon size={17} aria-hidden="true" className="mt-0.5 shrink-0 text-burgundy-500" />}
                            <span className="min-w-0">
                              <span className="block text-[15px] font-semibold leading-snug text-charcoal group-hover:text-burgundy-600">{item.label}</span>
                              {item.description && <span className="mt-0.5 block text-[13px] leading-snug text-charcoal-600">{item.description}</span>}
                            </span>
                          </NavDestination>
                        </li>
                      )
                    })}
                  </ul>
                </div>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
