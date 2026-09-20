import { Link } from 'react-router-dom'

export default function Logo({ light = false }) {
  return (
    <Link to="/" className="flex flex-col items-start leading-none">
      <span className={`whitespace-nowrap font-serif text-xl font-semibold tracking-tight sm:text-[1.5rem] ${light ? 'text-ivory' : 'text-charcoal'}`}>
        Women Shaping <span className="text-burgundy-500">Futures</span>
      </span>
      <span className={`mt-0.5 hidden whitespace-nowrap text-[10px] font-semibold uppercase tracking-widest2 sm:block ${light ? 'text-ivory/70' : 'text-charcoal-600'}`}>
        Stories &middot; Opportunity &middot; Growth
      </span>
    </Link>
  )
}
