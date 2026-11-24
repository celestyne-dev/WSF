import { Link } from 'react-router-dom'
import { collectionNotice } from '../../utils/collectionNotices'

// Short notice shown where a form collects personal data (Step 19).
export default function CollectionNotice({ kind, className = '' }) {
  const { text, terms } = collectionNotice(kind)
  const link = 'font-semibold text-burgundy-600 hover:underline'
  return (
    <p className={`text-xs text-charcoal-600 ${className}`} data-collection-notice={kind}>
      {text} See our <Link to="/privacy" className={link}>Privacy Policy</Link>
      {terms && (<>{' '}and <Link to="/terms" className={link}>Terms</Link></>)}.
    </p>
  )
}
