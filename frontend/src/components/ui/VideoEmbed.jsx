import { ExternalLink } from 'lucide-react'
import { isAllowedEmbedUrl, videoProviderLabel } from '../../utils/videoEmbed'
import MediaImage from './MediaImage'

// One external video (WSF hosts none). Renders a sandboxed, lazy iframe
// only for a backend-derived embed URL on an allowlisted player host;
// otherwise a plain outbound "Watch" link. Transcript and captions links
// render only when provided.
export default function VideoEmbed({ title, url, embedUrl, provider, transcript, captionsUrl, thumbnail }) {
  const canEmbed = isAllowedEmbedUrl(embedUrl)
  const providerLabel = videoProviderLabel(provider)
  return (
    <div className="space-y-2">
      {canEmbed && (
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
