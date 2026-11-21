import { useEffect, useState } from 'react'
import { ExternalLink, Play } from 'lucide-react'
import { hasConsent, onConsentChange, openConsentManager } from '../../utils/consent'
import { isAllowedEmbedUrl, videoProviderLabel } from '../../utils/videoEmbed'
import MediaImage from './MediaImage'

// One external video (WSF hosts none). Renders a sandboxed, lazy iframe
// only for a backend-derived embed URL on an allowlisted player host;
// otherwise a plain outbound "Watch" link. Transcript and captions links
// render only when provided.
//
// The provider's player can set its own cookies/storage, so the iframe
// loads only with Marketing consent (utils/consent) or when the visitor
// presses play for this one video. Withdrawing consent unloads a player
// that was loaded by consent (one the visitor started stays).
export default function VideoEmbed({ title, url, embedUrl, provider, transcript, captionsUrl, thumbnail }) {
  const canEmbed = isAllowedEmbedUrl(embedUrl)
  const providerLabel = videoProviderLabel(provider)
  const [allowed, setAllowed] = useState(() => hasConsent('marketing'))
  const [clicked, setClicked] = useState(false)
  useEffect(() => onConsentChange((snap) => setAllowed(snap.marketing)), [])
  const showPlayer = canEmbed && (allowed || clicked)
  return (
    <div className="space-y-2">
      {canEmbed && !showPlayer && (
        <div className="relative flex aspect-video w-full flex-col items-center justify-center gap-3 overflow-hidden border border-taupe-200 bg-charcoal px-6 text-center text-ivory">
          <button type="button" onClick={() => setClicked(true)} className="btn-light">
            <Play size={16} aria-hidden="true" /> Play video
          </button>
          <p className="max-w-md text-xs text-ivory/80">
            Loads the player from {providerLabel || 'the video provider'}, which may set its own cookies.{' '}
            <button type="button" onClick={openConsentManager} className="font-semibold underline underline-offset-2">Cookie settings</button>
          </p>
        </div>
      )}
      {showPlayer && (
        <div className="relative aspect-video w-full overflow-hidden border border-taupe-200 bg-charcoal">
          <iframe
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
            {canEmbed ? `Open on ${providerLabel || 'the provider'}` : `Watch${providerLabel && provider !== 'other' ? ` on ${providerLabel}` : ''}`}
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
