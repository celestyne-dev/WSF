import { ChevronDown, ChevronUp, Plus, Trash2 } from 'lucide-react'
import IdSelect from './IdSelect'
import MediaPicker from './MediaPicker'
import { searchPageIds, searchSeriesIds, searchTopicIds } from '../../api/destinationSearch'
import {
  PATHWAY_DESTINATION_LABELS,
  PATHWAY_DESTINATION_TYPES,
  PATHWAY_ICONS,
  PATHWAY_MAX_CARDS,
  changePathwayDestination,
  newPathwayCard,
  setPathwayIcon,
  setPathwayMedia,
} from '../../utils/homepageCollections'

const inputClass = 'w-full border border-taupe-300 bg-white px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

function Field({ label, children, wide }) {
  return (
    <div className={wide ? 'sm:col-span-2' : undefined}>
      <label className="text-xs font-semibold uppercase tracking-wide text-charcoal-600">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  )
}

function Text({ value, onChange, placeholder, maxLength }) {
  return (
    <input value={value || ''} maxLength={maxLength} placeholder={placeholder} onChange={(e) => onChange(e.target.value || null)} className={inputClass} />
  )
}

function PathwayCardEditor({ card, index, count, onChange, onMove, onRemove }) {
  const patch = (fields) => onChange({ ...card, ...fields })
  const pick = (field, id, label) => patch({ [field]: id, linkedLabel: label })
  const type = card.destinationType

  return (
    <div className="border border-taupe-200 bg-cream/40 p-3">
      <div className="mb-3 flex items-center justify-between">
        <p className="text-xs font-semibold uppercase tracking-wide text-burgundy-600">Card {index + 1}</p>
        <div className="flex items-center gap-1">
          <button type="button" aria-label="Move card up" onClick={() => onMove(-1)} disabled={index === 0} className="p-1 text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">
            <ChevronUp size={15} />
          </button>
          <button type="button" aria-label="Move card down" onClick={() => onMove(1)} disabled={index === count - 1} className="p-1 text-charcoal-600 hover:text-burgundy-600 disabled:opacity-20">
            <ChevronDown size={15} />
          </button>
          <button type="button" aria-label="Remove card" onClick={onRemove} className="p-1 text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <Field label="Title">
          <Text value={card.title} maxLength={80} onChange={(v) => patch({ title: v || '' })} placeholder="Card title" />
        </Field>
        <Field label="Small label (optional)">
          <Text value={card.eyebrow} maxLength={40} onChange={(v) => patch({ eyebrow: v })} placeholder="e.g. 5 min read" />
        </Field>
        <Field label="Short description" wide>
          <textarea value={card.description || ''} maxLength={240} rows={2} onChange={(e) => patch({ description: e.target.value || null })} className={inputClass} />
        </Field>

        <Field label="Destination type">
          <select value={type || ''} onChange={(e) => onChange(changePathwayDestination(card, e.target.value || null))} className={inputClass}>
            <option value="">Choose a destination…</option>
            {PATHWAY_DESTINATION_TYPES.map((t) => (
              <option key={t} value={t}>{PATHWAY_DESTINATION_LABELS[t]}</option>
            ))}
          </select>
        </Field>
        {type === 'route' && (
          <Field label="Internal path">
            <Text value={card.url} onChange={(v) => patch({ url: v })} placeholder="/resources" />
          </Field>
        )}
        {type === 'external' && (
          <Field label="External URL">
            <Text value={card.url} onChange={(v) => patch({ url: v })} placeholder="https://example.org" />
            <label className="mt-2 flex items-center gap-2 text-sm text-charcoal">
              <input type="checkbox" checked={!!card.openNewTab} onChange={(e) => patch({ openNewTab: e.target.checked })} /> Open in new tab
            </label>
          </Field>
        )}
        {type === 'page' && (
          <Field label="Page">
            <IdSelect value={card.pageId} savedLabel={card.linkedLabel} onChange={(id, label) => pick('pageId', id, label)} loadOptions={searchPageIds} placeholder="Search pages…" />
          </Field>
        )}
        {type === 'topic' && (
          <Field label="Topic">
            <IdSelect value={card.topicId} savedLabel={card.linkedLabel} onChange={(id, label) => pick('topicId', id, label)} loadOptions={searchTopicIds} placeholder="Search topics…" />
          </Field>
        )}
        {type === 'series' && (
          <Field label="Series">
            <IdSelect value={card.seriesId} savedLabel={card.linkedLabel} onChange={(id, label) => pick('seriesId', id, label)} loadOptions={searchSeriesIds} placeholder="Search series…" />
          </Field>
        )}

        <Field label="Icon (or use an image)">
          <select value={card.icon || ''} onChange={(e) => onChange(setPathwayIcon(card, e.target.value))} className={inputClass}>
            <option value="">No icon</option>
            {PATHWAY_ICONS.map((icon) => (
              <option key={icon} value={icon}>{icon.replace(/-/g, ' ')}</option>
            ))}
          </select>
        </Field>
        <Field label="Accessibility text (optional)">
          <Text value={card.ariaLabel} maxLength={160} onChange={(v) => patch({ ariaLabel: v })} placeholder="Read by screen readers instead of the title" />
        </Field>
        <div className="sm:col-span-2">
          <MediaPicker
            label="Image (replaces the icon)"
            value={card.media || (card.mediaId ? { id: card.mediaId } : null)}
            onChange={(media) => onChange(setPathwayMedia(card, media))}
          />
          {card.mediaId && !card.media?.mediaPath && <p className="mt-1 text-xs text-charcoal-600">Image #{card.mediaId} selected.</p>}
        </div>
      </div>
    </div>
  )
}

/** Career Pathways / Start Here — eyebrow plus 2–8 editor-written cards. */
export default function CareerPathwaysFields({ module, onChange }) {
  const config = module.config || {}
  const cards = config.cards || []
  const setCards = (next) => onChange({ ...module, config: { ...config, cards: next } })

  function move(index, direction) {
    const target = index + direction
    if (target < 0 || target >= cards.length) return
    const next = [...cards]
    ;[next[index], next[target]] = [next[target], next[index]]
    setCards(next)
  }

  return (
    <div className="sm:col-span-2 space-y-3">
      <Field label="Eyebrow (optional)">
        <Text value={config.eyebrow} maxLength={60} onChange={(v) => onChange({ ...module, config: { ...config, eyebrow: v } })} placeholder="e.g. New here?" />
      </Field>
      <p className="text-xs text-charcoal-600">
        {cards.length} of {PATHWAY_MAX_CARDS} cards. Use 2–8. A card whose destination is unpublished or missing is hidden on the live site, and the section hides when no card is valid.
      </p>
      {cards.map((card, index) => (
        <PathwayCardEditor
          key={index}
          card={card}
          index={index}
          count={cards.length}
          onChange={(next) => setCards(cards.map((c, i) => (i === index ? next : c)))}
          onMove={(direction) => move(index, direction)}
          onRemove={() => setCards(cards.filter((_, i) => i !== index))}
        />
      ))}
      <button type="button" onClick={() => setCards([...cards, newPathwayCard()])} disabled={cards.length >= PATHWAY_MAX_CARDS} className="btn-secondary !px-3 !py-1.5 text-xs disabled:opacity-50">
        <Plus size={13} /> Add card
      </button>
    </div>
  )
}
