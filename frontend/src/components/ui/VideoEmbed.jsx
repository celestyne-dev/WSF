import { useEffect, useId, useRef, useState } from 'react'
import { ExternalLink, Play } from 'lucide-react'
import { grantConsentCategory, hasConsent, onConsentChange } from '../../utils/consent'
import { embedProviderLabel, isAllowedEmbedUrl, shouldShowPlayer, videoProviderLabel } from '../../utils/videoEmbed'
import MediaImage from './MediaImage'

// One external video (WSF hosts none). Renders a sandboxed, lazy iframe
// only for a backend-derived embed URL on an allowlisted player host;
// otherwise a plain outbound "Watch" link. Transcript and captions links
// render only when provided.
//
// Functional media the visitor came for, not advertising: the provider's
// player can still set its own storage, so the iframe loads automatically
// only with Preferences consent (utils/consent), or for this one video when
// the visitor presses Play. Withdrawing Preferences unloads a player that
// was loaded by stored consent (one the visitor started stays).
//
// Without Preferences the placeholder names the provider (from the player
// URL's own allowlisted host) and offers two choices:
//   Play video           loads THIS video only; consent is not changed
//   Always allow videos  grants Preferences (other choices unchanged), so
//                        every video player may load from then on
// Nothing autoplays: the embed URLs carry no autoplay parameter, and the
// player only receives focus after the visitor asked for it.
export default function VideoEmbed({ title, url, embedUrl, provider, transcript, captionsUrl, thumbnail }) {
  const canEmbed = isAllowedEmbedUrl(embedUrl)
  const providerLabel = videoProviderLabel(provider)
  const hostLabel = embedProviderLabel(embedUrl) || 'an external provider'
  const [allowed, setAllowed] = useState(() => hasConsent('preferences'))
  const [clicked, setClicked] = useState(false)
  const frameRef = useRef(null)
  const noticeId = useId()
  useEffect(() => onConsentChange((snap) => setAllowed(snap.preferences)), [])
  const showPlayer = shouldShowPlayer(embedUrl, { preferencesConsent: allowed, playRequested: clicked })

  function play() {
    setClicked(true)
  }
  function alwaysAllow() {
    // Load this video now even if the consent version hasn't loaded yet.
    setClicked(true)
    grantConsentCategory('preferences')
  }
  // Keyboard users who chose to play land on the player, not back at the top.
  useEffect(() => {
    if (clicked && showPlayer) frameRef.current?.focus()
  }, [clicked, showPlayer])

  return (
    <div className="space-y-2">
      {canEmbed && !showPlayer && (
        <div
          role="group"
          aria-label={title ? `Video: ${title}` : 'Video'}
          className="relative flex aspect-video w-full flex-col items-center justify-center gap-3 overflow-hidden border border-taupe-200 bg-charcoal px-6 text-center text-ivory"
        >
          <p id={noticeId} className="max-w-md text-sm text-ivory">
            This video is hosted by {hostLabel}. Playing it may set cookies.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            <button
              type="button"
              onClick={play}
              aria-describedby={noticeId}
              className="btn-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ivory"
            >
              <Play size={16} aria-hidden="true" /> Play video
            </button>
            <button
              type="button"
              onClick={alwaysAllow}
              aria-describedby={noticeId}
              className="btn-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ivory"
            >
              Always allow videos
            </button>
          </div>
        </div>
      )}
      {showPlayer && (
        <div className="relative aspect-video w-full overflow-hidden border border-taupe-200 bg-charcoal">
          <iframe
            ref={frameRef}
            src={embedUrl}
            title={title || 'Video'}
            loading="lazy"
            allow="encrypted-media; fullscreen; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
            sandbox="allow-scripts allow-same-origin allow-presentation allow-popups"
            className="absolute inset-0 h-full w-full"
          />
        </div>
      )}
      {!canEmbed && thumbnail && url && (
        <a href={url} target="_blank" rel="noopener noreferrer" className="block aspect-video w-full overflow-hidden border border-taupe-200">
          <MediaImage media={thumbnail} alt={title || 'Video thumbnail'} className="h-full w-full object-cover" />
        </a>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
        {url && (
          <a href={url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-semibold text-burgundy-600 hover:underline">
            {canEmbed ? `Open on ${embedProviderLabel(embedUrl) || providerLabel || 'the provider'}` : `Watch${providerLabel && provider !== 'other' ? ` on ${providerLabel}` : ''}`}
            <ExternalLink size={12} aria-hidden="true" />
          </a>
        )}
        {captionsUrl && (
          <a href={captionsUrl} target="_blank" rel="noopener noreferrer" className="font-semibold text-burgundy-600 hover:underline">
            Captions
          </a>
        )}
      </div>
      {transcript && (
        <details className="border border-taupe-200 bg-cream px-3 py-2 text-sm text-charcoal-700">
          <summary className="cursor-pointer text-xs font-semibold text-charcoal">Transcript</summary>
          <p className="mt-2 whitespace-pre-line">{transcript}</p>
        </details>
      )}
    </div>
  )
}
