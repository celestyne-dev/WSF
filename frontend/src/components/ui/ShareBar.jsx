import { Link as LinkIcon } from 'lucide-react'
import { toast } from 'react-toastify'
import SocialIcon from './SocialIcon'
import { trackEvent } from '../../utils/analytics'

// LinkedIn leads the share bar — it's Women Shaping Futures' primary
// distribution channel, so sharing a page back to LinkedIn is one of the
// single most valuable actions a reader can take.
export default function ShareBar({ title, url, trackEventName = 'share_click', trackPayload = {} }) {
  const encodedUrl = encodeURIComponent(url)
  const encodedTitle = encodeURIComponent(title)
  const links = [
    { icon: 'linkedin', label: 'Share on LinkedIn', href: `https://www.linkedin.com/sharing/share-offsite/?url=${encodedUrl}`, emphasize: true },
    { icon: 'twitter', label: 'Share on X', href: `https://twitter.com/intent/tweet?url=${encodedUrl}&text=${encodedTitle}` },
    { icon: 'facebook', label: 'Share on Facebook', href: `https://www.facebook.com/sharer/sharer.php?u=${encodedUrl}` },
  ]
  return (
    <div className="flex items-center gap-3">
      {links.map(({ icon, label, href, emphasize }) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noreferrer"
          aria-label={label}
          onClick={() => trackEvent(trackEventName, { ...trackPayload, network: icon })}
          className={`flex h-9 w-9 items-center justify-center border transition-colors ${
            emphasize
              ? 'border-burgundy-500 bg-burgundy-500/10 text-burgundy-600 hover:bg-burgundy-500 hover:text-ivory'
              : 'border-taupe-300 text-charcoal hover:border-burgundy-500 hover:text-burgundy-600'
          }`}
        >
          <SocialIcon name={icon} size={16} />
        </a>
      ))}
      <button
        type="button"
        aria-label="Copy link"
        onClick={() => {
          navigator.clipboard?.writeText(url)
          trackEvent(trackEventName, { ...trackPayload, network: 'copy_link' })
          toast.success('Link copied to clipboard')
        }}
        className="flex h-9 w-9 items-center justify-center border border-taupe-300 text-charcoal transition-colors hover:border-burgundy-500 hover:text-burgundy-600"
      >
        <LinkIcon size={16} />
      </button>
    </div>
  )
}
