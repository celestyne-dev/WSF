import { Link } from 'react-router-dom'

export default function Tag({ children, to, tone = 'default' }) {
  const tones = {
    default: 'bg-taupe-100 text-charcoal-600',
    burgundy: 'bg-burgundy-500/10 text-burgundy-600',
    plum: 'bg-plum-500/10 text-plum-600',
    sponsor: 'bg-taupe-200 text-charcoal-700',
  }
  const classes = `inline-flex items-center px-3 py-1 text-xs font-semibold uppercase tracking-wide ${tones[tone]}`
  if (to) {
    return (
      <Link to={to} className={`${classes} transition-colors hover:bg-burgundy-500/20 hover:text-burgundy-700`}>
        {children}
      </Link>
    )
  }
  return <span className={classes}>{children}</span>
}
