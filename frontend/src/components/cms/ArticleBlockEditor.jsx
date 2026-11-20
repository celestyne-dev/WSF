import { useEffect, useRef, useState } from 'react'
import {
  Bold,
  Italic,
  Link as LinkIcon,
  Trash2,
  ChevronUp,
  ChevronDown,
  Heading2,
  Pilcrow,
  List as ListIcon,
  ListOrdered,
  Quote,
  MessageSquareQuote,
  ImagePlus,
  Minus,
  Megaphone,
  MousePointerClick,
  Newspaper,
  AlignLeft,
  Plus,
  X,
  PanelTop,
  Link2,
} from 'lucide-react'
import MediaPicker from './MediaPicker'
import { fetchArticles } from '../../api/articles'
import { CTA_PRESETS } from '../../constants/ctaPresets'
import { DEFAULT_CONTENT_BLOCK_TYPES } from '../../constants/contentBlockTypes'
import { NUMBERING_MODES, resolveListStarts } from '../../utils/listNumbering'
import { safeLinkUrl } from '../../utils/linkSafety'

// No rich-text library dependency (Tiptap/Slate/Lexical, etc.) was added —
// the only inline formatting this editor needs is bold/italic/links, which
// the browser's native contentEditable + execCommand already does
// reliably across evergreen browsers. Anything richer (marks, embeds,
// collaborative editing) would justify a real editor framework; this
// scope doesn't. Every field it produces is sanitized server-side
// (backend/app/services/content_blocks.py) before it's ever persisted or
// rendered back to a reader, so a11y/XSS risk from raw contentEditable
// HTML is not a concern here.
function RichTextField({ value, onChange, placeholder, className = '' }) {
  const ref = useRef(null)

  // Only sync the DOM from `value` when it actually changed out from under
  // us (block reorder, external reset) — never on every keystroke, or the
  // cursor jumps to the start on each character typed.
  useEffect(() => {
    if (ref.current && ref.current.innerHTML !== (value || '')) {
      ref.current.innerHTML = value || ''
    }
  }, [value])

  function exec(command, arg) {
    ref.current?.focus()
    document.execCommand(command, false, arg)
    onChange(ref.current?.innerHTML || '')
  }

  function handleLink() {
    const url = window.prompt('Link URL (https://…)')
    if (!url) return
    exec('createLink', url)
  }

  return (
    <div>
      <div className="flex gap-1 border border-b-0 border-taupe-300 bg-taupe-100 px-1.5 py-1">
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('bold')} aria-label="Bold" className="rounded p-1 text-charcoal-600 hover:bg-taupe-200 hover:text-charcoal">
          <Bold size={14} />
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('italic')} aria-label="Italic" className="rounded p-1 text-charcoal-600 hover:bg-taupe-200 hover:text-charcoal">
          <Italic size={14} />
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={handleLink} aria-label="Add link" className="rounded p-1 text-charcoal-600 hover:bg-taupe-200 hover:text-charcoal">
          <LinkIcon size={14} />
        </button>
      </div>
      <div
        ref={ref}
        contentEditable
        suppressContentEditableWarning
        data-placeholder={placeholder}
        onInput={(e) => onChange(e.currentTarget.innerHTML)}
        onBlur={(e) => onChange(e.currentTarget.innerHTML)}
        className={`rich-text-input ${className}`}
      />
    </div>
  )
}

// The header is `sticky` inside its own block: while a tall block is being
// scrolled through, its type label and Move/Delete controls stay pinned to
// the top of the CMS scroll area (AdminLayout's <main>), and they scroll
// away with the block once its end is reached — a sticky child can never
// leave its parent, so the next block's header simply takes over and two
// headers never stack. Opaque background + z-10 keep the field text
// underneath from showing through (MediaPicker's own modal sits above it).
function BlockShell({ label, icon: Icon, onMoveUp, onMoveDown, onRemove, canMoveUp, canMoveDown, children, position, total }) {
  // focus-within = "the block being edited": a burgundy edge + soft ring,
  // so it is obvious which block the keyboard/caret is in.
  return (
    <div className="group relative border border-taupe-200 bg-white px-4 pb-4 transition-shadow focus-within:border-burgundy-500 focus-within:shadow-[inset_3px_0_0_0_theme(colors.burgundy.500)] focus-within:ring-1 focus-within:ring-burgundy-500/30">
      <div className="sticky top-0 z-10 -mx-4 mb-3 flex items-center justify-between border-b border-taupe-100 bg-white px-4 py-2 group-focus-within:bg-blush-50">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600 group-focus-within:text-burgundy-600">
          <Icon size={13} aria-hidden="true" /> {label}
          {total > 1 && <span className="font-normal normal-case tracking-normal text-charcoal-600/60">· {position} of {total}</span>}
        </span>
        {/* Always fully visible (touch devices have no hover); disabled
            arrows stay subdued via disabled:opacity-30. */}
        <div className="flex items-center gap-1">
          <button type="button" onClick={onMoveUp} disabled={!canMoveUp} aria-label={`Move ${label} block up`} className="p-1.5 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronUp size={15} />
          </button>
          <button type="button" onClick={onMoveDown} disabled={!canMoveDown} aria-label={`Move ${label} block down`} className="p-1.5 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronDown size={15} />
          </button>
          <button type="button" onClick={onRemove} aria-label={`Delete ${label} block`} className="p-1.5 text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      {children}
    </div>
  )
}

// Grouped picker (Text / Editorial / Media / Engagement), each option with
// one short line saying what it is for. Groups with no allowed types for
// this caller (e.g. Newsletter, Resource) are simply not shown.
function BlockTypeChoices({ addMenu, onSelect }) {
  const groups = BLOCK_GROUPS.map((group) => ({ ...group, items: addMenu.filter((item) => item.group === group.key) })).filter((g) => g.items.length)
  return (
    <div className="space-y-3">
      {groups.map((group) => (
        <div key={group.key}>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-charcoal-600/70">{group.label}</p>
          <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
            {group.items.map(({ type, label, icon: Icon, description }) => (
              <button
                key={type}
                type="button"
                onClick={() => onSelect(type)}
                className="flex items-start gap-2 border border-taupe-200 bg-white px-2.5 py-2 text-left hover:border-burgundy-500 hover:bg-blush-50 focus-visible:border-burgundy-500"
              >
                <Icon size={15} className="mt-0.5 shrink-0 text-burgundy-600" aria-hidden="true" />
                <span className="min-w-0">
                  <span className="block text-xs font-semibold text-charcoal">{label}</span>
                  {description && <span className="block text-[11px] leading-snug text-charcoal-600">{description}</span>}
                </span>
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}

// One insertion point between blocks (or before the first / after the
// last). Collapsed it's a single subtle "+ Add block here" line; opened, it
// shows the caller's allowed block types right at this position. Only one
// is open at a time — ArticleBlockEditor owns that `insertAt` state.
function InsertPoint({ addMenu, isOpen, onOpen, onClose, onSelect, label, ariaLabel }) {
  if (isOpen) {
    return (
      <div
        className="border border-dashed border-burgundy-500/60 bg-taupe-50 p-3"
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose()
        }}
      >
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70">{label}</p>
          <button type="button" onClick={onClose} aria-label="Cancel adding a block" className="p-1 text-charcoal-600 hover:text-charcoal">
            <X size={14} />
          </button>
        </div>
        <BlockTypeChoices addMenu={addMenu} onSelect={onSelect} />
      </div>
    )
  }
  return (
    <div className="flex items-center gap-2">
      <span className="h-px flex-1 bg-taupe-200" aria-hidden="true" />
      <button
        type="button"
        onClick={onOpen}
        aria-label={ariaLabel}
        className="flex items-center gap-1 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70 hover:text-burgundy-600"
      >
        <Plus size={12} /> {label}
      </button>
      <span className="h-px flex-1 bg-taupe-200" aria-hidden="true" />
    </div>
  )
}

// Editor-only React keys for the block list, kept OUTSIDE the saved block
// JSON (nothing is ever written into a block). Index keys would let local
// UI state (an article-card search box, a MediaPicker's open state, a
// contentEditable's DOM) stay attached to a position instead of a block,
// so an insert/move could show one block's in-progress state on its
// neighbor. Keys follow this editor's own insert/move/delete; any change
// in length from outside (initial load, a parent resetting the content)
// just issues fresh keys.
let nextBlockKey = 0
function newBlockKey() {
  nextBlockKey += 1
  return `block-${nextBlockKey}`
}

// Width-free so callers can compose their own width utility instead of
// fighting the baked-in `w-full` below — see HeadingBlock, where the level
// `<select>` needs a fixed width instead of full width (pairing `w-full`
// and `w-24` on the same element is a no-op/bug: Tailwind's generated
// stylesheet always places `.w-full` after `.w-24`, so `.w-full` wins
// regardless of class order in the JSX, silently crushing the sibling
// field's share of the row).
const inputBaseClass = 'border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'
const inputClass = `w-full ${inputBaseClass}`

function HeadingBlock({ block, onChange }) {
  return (
    <div className="flex gap-2">
      <select value={block.level || 2} onChange={(e) => onChange({ ...block, level: Number(e.target.value) })} className={`${inputBaseClass} w-24 shrink-0`}>
        <option value={2}>H2</option>
        <option value={3}>H3</option>
        <option value={4}>H4</option>
      </select>
      <input value={block.text || ''} onChange={(e) => onChange({ ...block, text: e.target.value })} placeholder="Heading text" className={`${inputBaseClass} min-w-0 flex-1`} />
    </div>
  )
}

function ParagraphBlock({ block, onChange }) {
  return <RichTextField value={block.text} onChange={(text) => onChange({ ...block, text })} placeholder="Write a paragraph…" />
}

// Numbered lists: "Continue previous" (default for new numbered lists),
// "Restart at 1", or "Start at…". The resolved numbers shown beside each
// item come from the SAME helper the public page and server prerender use
// (utils/listNumbering.js), so what the editor shows is what readers get.
// A list saved before this existed (no numberingMode) shows as "Restart at
// 1" — exactly how it has always been published — and is never changed
// unless an editor picks a different option.
const NUMBERING_LABELS = { continue: 'Continue previous', restart: 'Restart at 1', custom: 'Start at…' }

function ListBlock({ block, onChange, listStart }) {
  const items = block.items?.length ? block.items : ['']
  const numbered = block.style === 'number'
  const mode = NUMBERING_MODES.includes(block.numberingMode) ? block.numberingMode : 'restart'
  // Numbers shown only for non-blank items (blank ones are not published).
  const itemNumbers = items.reduce(
    (acc, item) => {
      const blank = !item || !String(item).trim()
      acc.list.push(blank ? null : acc.next)
      if (!blank) acc.next += 1
      return acc
    },
    { list: [], next: listStart || 1 },
  ).list

  function updateItem(i, value) {
    const next = [...items]
    next[i] = value
    onChange({ ...block, items: next })
  }
  function addItem() {
    onChange({ ...block, items: [...items, ''] })
  }
  function removeItem(i) {
    onChange({ ...block, items: items.filter((_, idx) => idx !== i) })
  }
  function setStyle(style) {
    if (style === 'number') {
      // Switching a list to numbered = a new numbered list: continue by default.
      onChange({ ...block, style, numberingMode: block.numberingMode || 'continue' })
    } else {
      const { numberingMode: _mode, startNumber: _start, ...rest } = block
      onChange({ ...rest, style })
    }
  }
  function setMode(next) {
    const { startNumber: _start, ...rest } = block
    onChange(next === 'custom' ? { ...rest, numberingMode: next, startNumber: block.startNumber || listStart || 1 } : { ...rest, numberingMode: next })
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div className="flex gap-1" role="group" aria-label="List style">
          <button type="button" aria-pressed={!numbered} onClick={() => setStyle('bullet')} className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium ${!numbered ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
            <ListIcon size={13} aria-hidden="true" /> Bulleted
          </button>
          <button type="button" aria-pressed={numbered} onClick={() => setStyle('number')} className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium ${numbered ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
            <ListOrdered size={13} aria-hidden="true" /> Numbered
          </button>
        </div>
        {numbered && (
          <div className="flex flex-wrap items-center gap-2 text-xs text-charcoal-600">
            <label className="flex items-center gap-1.5">
              <span className="font-semibold">Numbering</span>
              <select value={mode} onChange={(e) => setMode(e.target.value)} className={`${inputBaseClass} py-1 text-xs`}>
                {NUMBERING_MODES.map((m) => (
                  <option key={m} value={m}>
                    {NUMBERING_LABELS[m]}
                  </option>
                ))}
              </select>
            </label>
            {mode === 'custom' && (
              <label className="flex items-center gap-1.5">
                <span className="sr-only">First number</span>
                <input
                  type="number"
                  min={1}
                  max={100000}
                  inputMode="numeric"
                  value={block.startNumber ?? ''}
                  onChange={(e) => {
                    const n = Number.parseInt(e.target.value, 10)
                    onChange({ ...block, startNumber: Number.isFinite(n) && n > 0 ? Math.min(n, 100000) : '' })
                  }}
                  className={`${inputBaseClass} w-24 py-1 text-xs`}
                  aria-label="First number"
                />
              </label>
            )}
            {listStart && <span className="text-charcoal-600/80">Starts at {listStart}</span>}
          </div>
        )}
      </div>
      <div className="space-y-2">
        {items.map((item, i) => {
          const number = itemNumbers[i]
          return (
            <div key={i} className="flex items-center gap-2">
              <span className="w-10 shrink-0 text-right text-xs font-semibold tabular-nums text-charcoal-600/70" aria-hidden="true">
                {numbered ? (number === null ? '–' : `${number}.`) : '•'}
              </span>
              <input value={item} onChange={(e) => updateItem(i, e.target.value)} className={inputClass} placeholder="List item" aria-label={`List item ${i + 1}`} />
              <button type="button" onClick={() => removeItem(i)} disabled={items.length <= 1} aria-label={`Remove list item ${i + 1}`} className="p-1 text-charcoal-600 hover:text-rose-600 disabled:opacity-30">
                <Trash2 size={14} />
              </button>
            </div>
          )
        })}
      </div>
      <button type="button" onClick={addItem} className="mt-2 text-xs font-semibold text-burgundy-600 hover:text-burgundy-700">
        + Add item
      </button>
    </div>
  )
}

function QuoteBlock({ block, onChange }) {
  return (
    <div className="space-y-2">
      <RichTextField value={block.text} onChange={(text) => onChange({ ...block, text })} placeholder="Quote text…" />
      <input value={block.attribution || ''} onChange={(e) => onChange({ ...block, attribution: e.target.value })} placeholder="Attribution (optional)" className={inputClass} />
    </div>
  )
}

const CALLOUT_LIST_OPTIONS = [
  { value: null, label: 'No list', icon: Minus },
  { value: 'bullet', label: 'Bulleted', icon: ListIcon },
  { value: 'number', label: 'Numbered', icon: ListOrdered },
]

// A Callout may end with an optional bulleted/numbered list (saved as
// block.listStyle + block.items — see content_blocks.py). Choosing
// "No list" only hides the list: items are kept on the block, so
// switching back to Bulleted/Numbered restores them.
function HighlightBlock({ block, onChange }) {
  const listStyle = block.listStyle === 'bullet' || block.listStyle === 'number' ? block.listStyle : null
  const items = block.items?.length ? block.items : ['']

  function setListStyle(next) {
    onChange({ ...block, listStyle: next, items: next && !block.items?.length ? [''] : block.items || [] })
  }
  function updateItem(i, value) {
    const next = [...items]
    next[i] = value
    onChange({ ...block, items: next })
  }
  function addItem() {
    onChange({ ...block, items: [...items, ''] })
  }
  function removeItem(i) {
    onChange({ ...block, items: items.filter((_, idx) => idx !== i) })
  }
  function moveItem(i, dir) {
    const target = i + dir
    if (target < 0 || target >= items.length) return
    const next = [...items]
    ;[next[i], next[target]] = [next[target], next[i]]
    onChange({ ...block, items: next })
  }

  return (
    <div className="space-y-2">
      <input value={block.title || ''} onChange={(e) => onChange({ ...block, title: e.target.value })} placeholder="Callout title (optional)" className={inputClass} />
      <RichTextField value={block.text} onChange={(text) => onChange({ ...block, text })} placeholder="Callout text…" />
      <div className="flex flex-wrap items-center gap-2 pt-1">
        <span className="text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70">List</span>
        {CALLOUT_LIST_OPTIONS.map(({ value, label, icon: Icon }) => (
          <button
            key={label}
            type="button"
            onClick={() => setListStyle(value)}
            aria-pressed={listStyle === value}
            className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium ${listStyle === value ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}
          >
            <Icon size={13} /> {label}
          </button>
        ))}
      </div>
      {listStyle && (
        <div>
          <div className="space-y-2">
            {items.map((item, i) => (
              <div key={i} className="flex items-center gap-2">
                <span className="w-4 shrink-0 text-xs text-charcoal-600/60">{listStyle === 'number' ? `${i + 1}.` : '•'}</span>
                <input value={item} onChange={(e) => updateItem(i, e.target.value)} className={inputClass} placeholder="List item" />
                <button type="button" onClick={() => moveItem(i, -1)} disabled={i === 0} aria-label="Move item up" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
                  <ChevronUp size={14} />
                </button>
                <button type="button" onClick={() => moveItem(i, 1)} disabled={i === items.length - 1} aria-label="Move item down" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
                  <ChevronDown size={14} />
                </button>
                <button type="button" onClick={() => removeItem(i)} disabled={items.length <= 1} aria-label="Remove item" className="p-1 text-charcoal-600 hover:text-rose-600 disabled:opacity-30">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
          <button type="button" onClick={addItem} className="mt-2 text-xs font-semibold text-burgundy-600 hover:text-burgundy-700">
            + Add item
          </button>
        </div>
      )}
    </div>
  )
}

function ImageBlockEditor({ block, onChange }) {
  const decorative = block.decorative === true

  function handleMediaChange(media) {
    onChange({
      ...block,
      media,
      // A decorative image's alt must stay "" even across a media swap —
      // never silently repopulated from the newly picked media's own
      // altText while the editor still has it marked decorative.
      alt: decorative ? '' : block.alt || media?.altText || '',
      caption: block.caption || media?.caption || '',
      credit: block.credit || media?.credit || '',
    })
  }

  function handleDecorativeChange(nextDecorative) {
    onChange({
      ...block,
      decorative: nextDecorative,
      // Marking an image decorative clears its stored alt (a decorative
      // image's rendered alt must be exactly ""). Un-marking it restores
      // the selected Media's own altText when it has one — never
      // fabricated from caption/credit/filename.
      alt: nextDecorative ? '' : block.alt || block.media?.altText || '',
    })
  }

  return (
    <div className="space-y-2">
      <MediaPicker label={null} aspect={3 / 2} value={block.media} onChange={handleMediaChange} />
      <input
        value={decorative ? '' : block.alt || ''}
        onChange={(e) => onChange({ ...block, alt: e.target.value })}
        placeholder="Alt text"
        disabled={decorative}
        className={`${inputClass} disabled:cursor-not-allowed disabled:bg-taupe-100 disabled:text-charcoal-600/50`}
      />
      <label className="flex items-start gap-2 text-sm text-charcoal-600">
        <input type="checkbox" checked={decorative} onChange={(e) => handleDecorativeChange(e.target.checked)} className="mt-0.5" />
        Decorative image
      </label>
      <p className="text-xs text-charcoal-600/70">
        Use this only when the image adds no information. Decorative images are ignored by screen readers.
      </p>
      <div className="grid grid-cols-2 gap-2">
        <input value={block.caption || ''} onChange={(e) => onChange({ ...block, caption: e.target.value })} placeholder="Caption" className={inputClass} />
        <input value={block.credit || ''} onChange={(e) => onChange({ ...block, credit: e.target.value })} placeholder="Credit" className={inputClass} />
      </div>
    </div>
  )
}

function DividerBlock() {
  return <hr className="border-t-2 border-dashed border-taupe-300" />
}

function UrlHint({ url }) {
  if (!url) return null
  if (safeLinkUrl(url, { allowMailto: true })) return null
  return (
    <p className="mt-1 text-xs text-rose-600" role="alert">
      Use a site path like /career-hub or a full https:// address. Other links are removed on save.
    </p>
  )
}

function ButtonBlock({ block, onChange }) {
  return (
    <div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <input value={block.label || ''} onChange={(e) => onChange({ ...block, label: e.target.value })} placeholder="Button label" aria-label="Button label" className={inputClass} />
        <input value={block.url || ''} onChange={(e) => onChange({ ...block, url: e.target.value })} placeholder="/career-hub or https://…" aria-label="Button link" className={inputClass} />
      </div>
      <UrlHint url={block.url} />
    </div>
  )
}

// Rich in-article CTA. Presets only pre-fill these editable fields — the
// saved block is always plain eyebrow/title/text/label/URL plus two
// controlled options (style, alignment). No custom CSS.
function CtaBlockEditor({ block, onChange }) {
  const set = (field) => (e) => onChange({ ...block, [field]: e.target.value })
  return (
    <div className="space-y-3">
      <div>
        <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/80">Start from a preset</p>
        <div className="flex flex-wrap gap-1.5">
          {CTA_PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              onClick={() => onChange({ ...block, ...preset.fields })}
              className="border border-taupe-300 bg-white px-2.5 py-1 text-xs font-medium text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600"
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-2 sm:grid-cols-2">
        <input value={block.eyebrow || ''} onChange={set('eyebrow')} maxLength={80} placeholder="Eyebrow (optional)" aria-label="Eyebrow" className={inputClass} />
        <input value={block.title || ''} onChange={set('title')} maxLength={160} placeholder="Title" aria-label="CTA title" className={inputClass} />
      </div>
      <textarea value={block.text || ''} onChange={set('text')} maxLength={600} rows={2} placeholder="Short supporting text" aria-label="CTA text" className={inputClass} />
      <div className="grid gap-2 sm:grid-cols-2">
        <input value={block.buttonLabel || ''} onChange={set('buttonLabel')} maxLength={60} placeholder="Button label" aria-label="CTA button label" className={inputClass} />
        <div>
          <input value={block.buttonUrl || ''} onChange={set('buttonUrl')} placeholder="/career-hub or https://…" aria-label="CTA button link" className={inputClass} />
          {block.buttonUrl && !safeLinkUrl(block.buttonUrl) && (
            <p className="mt-1 text-xs text-rose-600" role="alert">
              Use a site path like /career-hub or a full https:// address. Other links are removed on save.
            </p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-charcoal-600">
        <label className="flex items-center gap-1.5">
          <span className="font-semibold">Style</span>
          <select value={block.style || 'soft'} onChange={set('style')} className={`${inputBaseClass} py-1 text-xs`}>
            <option value="soft">Soft (cream panel)</option>
            <option value="outline">Outline</option>
            <option value="strong">Strong (dark panel)</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5">
          <span className="font-semibold">Align</span>
          <select value={block.align || 'left'} onChange={set('align')} className={`${inputBaseClass} py-1 text-xs`}>
            <option value="left">Left</option>
            <option value="center">Center</option>
          </select>
        </label>
      </div>
    </div>
  )
}

// "Related reading": up to three published Articles, resolved LIVE on the
// public page (an unpublished/deleted one simply drops out), unlike the
// Newsletter's articleCard snapshot.
function RelatedBlockEditor({ block, onChange }) {
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])
  const slugs = Array.isArray(block.articleSlugs) ? block.articleSlugs : []
  // Titles are only an editor convenience (never saved: the public page
  // resolves each slug live), so after a reload a pick shows as its URL.
  const [titles, setTitles] = useState({})

  useEffect(() => {
    if (!search) return undefined
    let active = true
    fetchArticles({ query: search, pageSize: 8 })
      .then((res) => active && setResults(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [search])
  const shownResults = search ? results : []

  function add(article) {
    if (slugs.includes(article.slug) || slugs.length >= 3) return
    setTitles((t) => ({ ...t, [article.slug]: article.title }))
    onChange({ ...block, articleSlugs: [...slugs, article.slug] })
    setSearch('')
    setResults([])
  }
  function remove(slug) {
    onChange({ ...block, articleSlugs: slugs.filter((s) => s !== slug) })
  }

  return (
    <div className="space-y-2">
      <input value={block.heading || ''} onChange={(e) => onChange({ ...block, heading: e.target.value })} maxLength={80} placeholder="Heading (default: Related reading)" aria-label="Related reading heading" className={inputClass} />
      {slugs.length > 0 && (
        <ul className="divide-y divide-taupe-200 border border-taupe-200 bg-taupe-50">
          {slugs.map((slug) => (
            <li key={slug} className="flex items-center justify-between gap-3 px-3 py-2">
              <span className="min-w-0 truncate text-sm text-charcoal">{titles[slug] || `/${slug}`}</span>
              <button type="button" onClick={() => remove(slug)} className="shrink-0 text-xs font-semibold text-charcoal-600/70 hover:text-rose-600" aria-label={`Remove ${titles[slug] || slug}`}>
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}
      {slugs.length < 3 ? (
        <>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search published articles to add…" aria-label="Search published articles" className={inputClass} />
          {shownResults.length > 0 && (
            <div className="max-h-40 divide-y divide-taupe-200 overflow-y-auto border border-taupe-200">
              {shownResults.map((a) => (
                <button key={a.slug} type="button" onClick={() => add(a)} disabled={slugs.includes(a.slug)} className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100 disabled:opacity-40">
                  {a.title}
                </button>
              ))}
            </div>
          )}
        </>
      ) : (
        <p className="text-xs text-charcoal-600">Up to three articles.</p>
      )}
    </div>
  )
}

function FooterNoteBlock({ block, onChange }) {
  return <RichTextField value={block.text} onChange={(text) => onChange({ ...block, text })} placeholder="Footer note — small print shown at the end…" />
}

// A snapshot of a published Article, not a live relationship — chosen so
// a newsletter's sent history stays meaningful even if the article is
// later edited, unpublished, or removed. Only ever offers published
// articles: the search hits the same public /articles endpoint the site
// itself uses, which already filters to status=published.
function ArticleCardBlock({ block, onChange }) {
  const [search, setSearch] = useState('')
  const [results, setResults] = useState([])

  useEffect(() => {
    if (!search) {
      setResults([])
      return
    }
    let active = true
    fetchArticles({ query: search, pageSize: 8 })
      .then((res) => active && setResults(res.items))
      .catch(() => {})
    return () => {
      active = false
    }
  }, [search])

  function selectArticle(article) {
    onChange({
      ...block,
      articleSlug: article.slug,
      title: article.title,
      excerpt: article.excerpt || '',
      imageUrl: article.heroImage || '',
    })
    setSearch('')
    setResults([])
  }

  if (block.articleSlug) {
    return (
      <div className="flex items-center justify-between gap-3 border border-taupe-200 bg-taupe-50 px-3 py-2">
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-charcoal">{block.title}</p>
          <p className="text-xs text-charcoal-600/70">/{block.articleSlug}</p>
        </div>
        <button
          type="button"
          onClick={() => onChange({ ...block, articleSlug: '', title: '', excerpt: '', imageUrl: '' })}
          className="shrink-0 text-xs font-semibold text-charcoal-600/70 hover:text-rose-600"
        >
          Change
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search published articles…" className={inputClass} />
      {results.length > 0 && (
        <div className="max-h-40 divide-y divide-taupe-200 overflow-y-auto border border-taupe-200">
          {results.map((a) => (
            <button key={a.slug} type="button" onClick={() => selectArticle(a)} className="block w-full px-3 py-2 text-left text-sm hover:bg-taupe-100">
              {a.title}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const BLOCK_KINDS = {
  heading: { label: 'Heading', icon: Heading2, Editor: HeadingBlock },
  paragraph: { label: 'Paragraph', icon: Pilcrow, Editor: ParagraphBlock },
  list: { label: 'List', icon: ListIcon, Editor: ListBlock },
  blockquote: { label: 'Blockquote', icon: Quote, Editor: QuoteBlock },
  pullquote: { label: 'Pull quote', icon: MessageSquareQuote, Editor: QuoteBlock },
  image: { label: 'Image', icon: ImagePlus, Editor: ImageBlockEditor },
  divider: { label: 'Divider', icon: Minus, Editor: DividerBlock },
  highlight: { label: 'Callout', icon: Megaphone, Editor: HighlightBlock },
  button: { label: 'Simple CTA', icon: MousePointerClick, Editor: ButtonBlock },
  cta: { label: 'CTA', icon: PanelTop, Editor: CtaBlockEditor },
  relatedBlock: { label: 'Related article', icon: Link2, Editor: RelatedBlockEditor },
  articleCard: { label: 'Article card', icon: Newspaper, Editor: ArticleCardBlock },
  footerNote: { label: 'Footer note', icon: AlignLeft, Editor: FooterNoteBlock },
}

function blankBlock(type) {
  switch (type) {
    case 'heading':
      return { type, level: 2, text: '' }
    case 'paragraph':
      return { type, text: '' }
    case 'list':
      return { type, style: 'bullet', items: [''] }
    case 'blockquote':
    case 'pullquote':
      return { type, text: '', attribution: '' }
    case 'image':
      return { type, media: null, alt: '', caption: '', credit: '', decorative: false }
    case 'highlight':
      return { type, title: '', text: '', listStyle: null, items: [] }
    case 'button':
      return { type, label: '', url: '' }
    case 'cta':
      return { type, eyebrow: '', title: '', text: '', buttonLabel: '', buttonUrl: '', style: 'soft', align: 'left' }
    case 'relatedBlock':
      return { type, heading: '', articleSlugs: [] }
    case 'articleCard':
      return { type, articleSlug: '', title: '', excerpt: '', imageUrl: '' }
    case 'footerNote':
      return { type, text: '' }
    default:
      return { type }
  }
}

const BLOCK_GROUPS = [
  { key: 'text', label: 'Text' },
  { key: 'editorial', label: 'Editorial' },
  { key: 'media', label: 'Media' },
  { key: 'engagement', label: 'Engagement' },
]

const ADD_MENU = [
  { type: 'paragraph', group: 'text', label: 'Paragraph', icon: Pilcrow, description: 'Body text with bold, italic and links.' },
  { type: 'heading', group: 'text', label: 'Heading', icon: Heading2, description: 'A section title (H2–H4); feeds the contents list.' },
  { type: 'list', group: 'text', label: 'List', icon: ListIcon, description: 'Bulleted or numbered; numbers can continue.' },
  { type: 'blockquote', group: 'editorial', label: 'Blockquote', icon: Quote, description: 'A quoted passage set off from the text.' },
  { type: 'pullquote', group: 'editorial', label: 'Pull quote', icon: MessageSquareQuote, description: 'A large highlighted line from the story.' },
  { type: 'highlight', group: 'editorial', label: 'Callout', icon: Megaphone, description: 'A boxed note, tip or key takeaways.' },
  { type: 'divider', group: 'editorial', label: 'Divider', icon: Minus, description: 'A quiet break between sections.' },
  { type: 'image', group: 'media', label: 'Image', icon: ImagePlus, description: 'A photo with alt text, caption and credit.' },
  { type: 'cta', group: 'engagement', label: 'CTA', icon: PanelTop, description: 'A panel with title, text and one button.' },
  { type: 'button', group: 'engagement', label: 'Simple CTA', icon: MousePointerClick, description: 'Just one button linking somewhere useful.' },
  { type: 'relatedBlock', group: 'engagement', label: 'Related article', icon: Link2, description: 'Link up to three published stories.' },
  { type: 'articleCard', group: 'engagement', label: 'Article card', icon: Newspaper, description: 'A saved snapshot of one story (email-safe).' },
  { type: 'footerNote', group: 'editorial', label: 'Footer note', icon: AlignLeft, description: 'Small print at the end.' },
]

// The set every caller sees when it doesn't pass `blockTypes` (Resource,
// Person, Page, Event… descriptions) — unchanged. The Article editor passes
// ARTICLE_BLOCK_TYPES (adds the in-article CTA blocks and Related article,
// which only ArticlePage resolves); Newsletter passes its own list.
const DEFAULT_BLOCK_TYPES = DEFAULT_CONTENT_BLOCK_TYPES

/**
 * The article body editor — a structured, ordered list of typed content
 * blocks (backend: Article.content, a JSON column; see
 * backend/app/services/content_blocks.py for the server-side sanitization
 * every text field here goes through before it's persisted). This is the
 * CMS's only place to write article body copy — there is no separate
 * unstructured textarea. Also reused by the Newsletter issue editor, which
 * passes a wider `blockTypes` list (adding button/articleCard/footerNote,
 * all still email-friendly — no columns, embeds, or raw HTML).
 */
export default function ArticleBlockEditor({ blocks = [], onChange, blockTypes = DEFAULT_BLOCK_TYPES }) {
  const addMenu = ADD_MENU.filter((item) => blockTypes.includes(item.type))
  const listStarts = resolveListStarts(blocks)
  // null = no insertion menu open; an integer = the position (0..length)
  // a newly chosen block will be inserted at.
  const [insertAt, setInsertAt] = useState(null)
  const [keys, setKeys] = useState(() => blocks.map(newBlockKey))
  let blockKeys = keys
  if (keys.length !== blocks.length) {
    // Derived-state reset during render (React's documented pattern for
    // "props changed underneath this state") — see newBlockKey's comment.
    blockKeys = blocks.map(newBlockKey)
    setKeys(blockKeys)
  }

  function updateBlock(i, next) {
    const copy = [...blocks]
    copy[i] = next
    onChange(copy)
  }
  function removeBlock(i) {
    setInsertAt(null)
    setKeys(blockKeys.filter((_, idx) => idx !== i))
    onChange(blocks.filter((_, idx) => idx !== i))
  }
  function moveBlock(i, dir) {
    const target = i + dir
    if (target < 0 || target >= blocks.length) return
    setInsertAt(null)
    const copy = [...blocks]
    ;[copy[i], copy[target]] = [copy[target], copy[i]]
    const keyCopy = [...blockKeys]
    ;[keyCopy[i], keyCopy[target]] = [keyCopy[target], keyCopy[i]]
    setKeys(keyCopy)
    onChange(copy)
  }
  // Inserts exactly one blankBlock(type) at `index` (0 = before the first
  // block, blocks.length = after the last) — never mutates `blocks`.
  function insertBlock(index, type) {
    const copy = [...blocks]
    copy.splice(index, 0, blankBlock(type))
    const keyCopy = [...blockKeys]
    keyCopy.splice(index, 0, newBlockKey())
    setKeys(keyCopy)
    setInsertAt(null)
    onChange(copy)
  }

  if (blocks.length === 0) {
    return (
      <div className="border border-dashed border-taupe-300 p-4">
        <p className="mb-3 text-sm text-charcoal-600/70">No content yet — choose your first block.</p>
        <BlockTypeChoices addMenu={addMenu} onSelect={(type) => insertBlock(0, type)} />
      </div>
    )
  }

  function renderInsertPoint(index) {
    const isEnd = index === blocks.length
    return (
      <InsertPoint
        key={`insert-${index}`}
        addMenu={addMenu}
        isOpen={insertAt === index}
        onOpen={() => setInsertAt(index)}
        onClose={() => setInsertAt(null)}
        onSelect={(type) => insertBlock(index, type)}
        label={isEnd ? 'Add block at end' : 'Add block here'}
        ariaLabel={
          index === 0
            ? 'Add block before the first content block'
            : isEnd
              ? 'Add block after the last content block'
              : `Add block between content blocks ${index} and ${index + 1}`
        }
      />
    )
  }

  return (
    <div className="space-y-3">
      {/* flatMap (not map returning pairs) so every insertion point and
          BlockShell is a direct, individually keyed child — a nested array
          would be keyed by position and remount blocks on reorder. */}
      {blocks.flatMap((block, i) => {
        const kind = BLOCK_KINDS[block.type]
        // An unknown block type is still kept in the saved content (never
        // dropped) — it just has no editor, as before.
        if (!kind) return [renderInsertPoint(i)]
        const { Editor } = kind
        return [
          renderInsertPoint(i),
          <BlockShell
            key={blockKeys[i]}
            label={kind.label}
            icon={kind.icon}
            onMoveUp={() => moveBlock(i, -1)}
            onMoveDown={() => moveBlock(i, 1)}
            onRemove={() => removeBlock(i)}
            canMoveUp={i > 0}
            canMoveDown={i < blocks.length - 1}
            position={i + 1}
            total={blocks.length}
          >
            <Editor block={block} onChange={(next) => updateBlock(i, next)} listStart={listStarts[i]} />
          </BlockShell>,
        ]
      })}
      {renderInsertPoint(blocks.length)}
    </div>
  )
}
