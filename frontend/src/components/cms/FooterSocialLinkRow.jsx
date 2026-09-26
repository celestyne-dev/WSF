import { ChevronUp, ChevronDown, Trash2 } from 'lucide-react'
import SocialIcon from '../ui/SocialIcon'
import { SOCIAL_PLATFORMS, SOCIAL_PLATFORM_LABELS } from '../../constants/footerItems'

export default function FooterSocialLinkRow({ item, index, siblingCount, onChange, onRemove, onMove }) {
  function patch(fields) {
    onChange({ ...item, ...fields })
  }

  return (
    <div className="flex items-start gap-2 border border-taupe-200 bg-white p-3">
      <div className="flex flex-col pt-1.5">
        <button type="button" disabled={index === 0} onClick={() => onMove(-1)} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-30">
          <ChevronUp size={14} />
        </button>
        <button type="button" disabled={index === siblingCount - 1} onClick={() => onMove(1)} className="text-charcoal-600 hover:text-burgundy-600 disabled:opacity-30">
          <ChevronDown size={14} />
        </button>
      </div>

      <div className="pt-1.5 text-charcoal-600">
        <SocialIcon name={item.platform} size={18} />
      </div>

      <div className="grid flex-1 grid-cols-1 gap-2 sm:grid-cols-4">
        <select
          value={item.platform}
          onChange={(e) => patch({ platform: e.target.value })}
          className="border border-taupe-300 bg-white px-2 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
        >
          {SOCIAL_PLATFORMS.map((p) => (
            <option key={p} value={p}>
              {SOCIAL_PLATFORM_LABELS[p]}
            </option>
          ))}
        </select>
        <input
          value={item.url}
          onChange={(e) => patch({ url: e.target.value })}
          placeholder="https://…"
          className="border border-taupe-300 px-2 py-2 text-sm focus:border-burgundy-500 focus:outline-none sm:col-span-2"
        />
        <input
          value={item.label || ''}
          onChange={(e) => patch({ label: e.target.value })}
          placeholder={`Accessible label (default: “Women Shaping Futures on ${SOCIAL_PLATFORM_LABELS[item.platform]}”)`}
          className="border border-taupe-300 px-2 py-2 text-sm focus:border-burgundy-500 focus:outline-none"
        />
      </div>

      <button
        type="button"
        onClick={() => patch({ visible: !item.visible })}
        className={`px-2 py-1.5 text-xs font-semibold uppercase tracking-wide ${item.visible ? 'text-charcoal-600' : 'bg-taupe-200 text-charcoal-600'}`}
      >
        {item.visible ? 'Visible' : 'Hidden'}
      </button>

      <button type="button" onClick={onRemove} className="pt-1.5 text-charcoal-600 hover:text-burgundy-600" aria-label="Remove social link">
        <Trash2 size={16} />
      </button>
    </div>
  )
}
