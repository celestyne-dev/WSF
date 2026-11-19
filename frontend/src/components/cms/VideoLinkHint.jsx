import { videoLinkHint } from '../../utils/videoEmbed'

const TONE = { ok: 'text-emerald-700', info: 'text-charcoal-600', error: 'text-rose-600' }

// Live editor guidance under a video/recording link field: which provider
// was detected and whether it will play on the page or open as a link.
export default function VideoLinkHint({ url }) {
  const hint = videoLinkHint(url)
  if (!hint) return null
  return (
    <p className={`text-xs ${TONE[hint.tone]}`} role={hint.tone === 'error' ? 'alert' : undefined}>
      {hint.text}
    </p>
  )
}
