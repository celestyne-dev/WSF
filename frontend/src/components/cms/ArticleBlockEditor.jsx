import { useEffect, useRef } from 'react'
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
} from 'lucide-react'
import MediaPicker from './MediaPicker'

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

function BlockShell({ label, icon: Icon, onMoveUp, onMoveDown, onRemove, canMoveUp, canMoveDown, children }) {
  return (
    <div className="group relative border border-taupe-200 bg-white p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70">
          <Icon size={13} /> {label}
        </span>
        <div className="flex items-center gap-1 opacity-60 group-hover:opacity-100">
          <button type="button" onClick={onMoveUp} disabled={!canMoveUp} aria-label="Move up" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronUp size={15} />
          </button>
          <button type="button" onClick={onMoveDown} disabled={!canMoveDown} aria-label="Move down" className="p-1 text-charcoal-600 hover:text-charcoal disabled:opacity-30">
            <ChevronDown size={15} />
          </button>
          <button type="button" onClick={onRemove} aria-label="Delete block" className="p-1 text-charcoal-600 hover:text-rose-600">
            <Trash2 size={15} />
          </button>
        </div>
      </div>
      {children}
    </div>
  )
}

const inputClass = 'w-full border border-taupe-300 px-3 py-2 text-sm focus:border-burgundy-500 focus:outline-none'

function HeadingBlock({ block, onChange }) {
  return (
    <div className="flex gap-2">
      <select value={block.level || 2} onChange={(e) => onChange({ ...block, level: Number(e.target.value) })} className={`${inputClass} w-24 shrink-0`}>
        <option value={2}>H2</option>
        <option value={3}>H3</option>
        <option value={4}>H4</option>
      </select>
      <input value={block.text || ''} onChange={(e) => onChange({ ...block, text: e.target.value })} placeholder="Heading text" className={inputClass} />
    </div>
  )
}

function ParagraphBlock({ block, onChange }) {
  return <RichTextField value={block.text} onChange={(text) => onChange({ ...block, text })} placeholder="Write a paragraph…" />
}

function ListBlock({ block, onChange }) {
  const items = block.items?.length ? block.items : ['']

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

  return (
    <div>
      <div className="mb-2 flex gap-2">
        <button type="button" onClick={() => onChange({ ...block, style: 'bullet' })} className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium ${block.style !== 'number' ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
          <ListIcon size={13} /> Bulleted
        </button>
        <button type="button" onClick={() => onChange({ ...block, style: 'number' })} className={`flex items-center gap-1 px-2.5 py-1 text-xs font-medium ${block.style === 'number' ? 'bg-plum-600 text-ivory' : 'bg-taupe-100 text-charcoal-600'}`}>
          <ListOrdered size={13} /> Numbered
        </button>
      </div>
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-4 shrink-0 text-xs text-charcoal-600/60">{block.style === 'number' ? `${i + 1}.` : '•'}</span>
            <input value={item} onChange={(e) => updateItem(i, e.target.value)} className={inputClass} placeholder="List item" />
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

function HighlightBlock({ block, onChange }) {
  return (
    <div className="space-y-2">
      <input value={block.title || ''} onChange={(e) => onChange({ ...block, title: e.target.value })} placeholder="Callout title (optional)" className={inputClass} />
      <RichTextField value={block.text} onChange={(text) => onChange({ ...block, text })} placeholder="Callout text…" />
    </div>
  )
}

function ImageBlockEditor({ block, onChange }) {
  return (
    <div className="space-y-2">
      <MediaPicker
        label={null}
        aspect={3 / 2}
        value={block.media}
        onChange={(media) =>
          onChange({
            ...block,
            media,
            alt: block.alt || media?.altText || '',
            caption: block.caption || media?.caption || '',
            credit: block.credit || media?.credit || '',
          })
        }
      />
      <input value={block.alt || ''} onChange={(e) => onChange({ ...block, alt: e.target.value })} placeholder="Alt text" className={inputClass} />
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

const BLOCK_KINDS = {
  heading: { label: 'Heading', icon: Heading2, Editor: HeadingBlock },
  paragraph: { label: 'Paragraph', icon: Pilcrow, Editor: ParagraphBlock },
  list: { label: 'List', icon: ListIcon, Editor: ListBlock },
  blockquote: { label: 'Blockquote', icon: Quote, Editor: QuoteBlock },
  pullquote: { label: 'Pull quote', icon: MessageSquareQuote, Editor: QuoteBlock },
  image: { label: 'Image', icon: ImagePlus, Editor: ImageBlockEditor },
  divider: { label: 'Divider', icon: Minus, Editor: DividerBlock },
  highlight: { label: 'Callout', icon: Megaphone, Editor: HighlightBlock },
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
      return { type, media: null, alt: '', caption: '', credit: '' }
    case 'highlight':
      return { type, title: '', text: '' }
    default:
      return { type }
  }
}

const ADD_MENU = [
  { type: 'paragraph', label: 'Paragraph', icon: Pilcrow },
  { type: 'heading', label: 'Heading', icon: Heading2 },
  { type: 'list', label: 'List', icon: ListIcon },
  { type: 'blockquote', label: 'Blockquote', icon: Quote },
  { type: 'pullquote', label: 'Pull quote', icon: MessageSquareQuote },
  { type: 'image', label: 'Image', icon: ImagePlus },
  { type: 'highlight', label: 'Callout', icon: Megaphone },
  { type: 'divider', label: 'Divider', icon: Minus },
]

/**
 * The article body editor — a structured, ordered list of typed content
 * blocks (backend: Article.content, a JSON column; see
 * backend/app/services/content_blocks.py for the server-side sanitization
 * every text field here goes through before it's persisted). This is the
 * CMS's only place to write article body copy — there is no separate
 * unstructured textarea.
 */
export default function ArticleBlockEditor({ blocks = [], onChange }) {
  function updateBlock(i, next) {
    const copy = [...blocks]
    copy[i] = next
    onChange(copy)
  }
  function removeBlock(i) {
    onChange(blocks.filter((_, idx) => idx !== i))
  }
  function moveBlock(i, dir) {
    const target = i + dir
    if (target < 0 || target >= blocks.length) return
    const copy = [...blocks]
    ;[copy[i], copy[target]] = [copy[target], copy[i]]
    onChange(copy)
  }
  function addBlock(type) {
    onChange([...blocks, blankBlock(type)])
  }

  return (
    <div className="space-y-3">
      {blocks.length === 0 && (
        <p className="border border-dashed border-taupe-300 px-4 py-8 text-center text-sm text-charcoal-600/60">
          No content yet — add your first block below.
        </p>
      )}
      {blocks.map((block, i) => {
        const kind = BLOCK_KINDS[block.type]
        if (!kind) return null
        const { Editor } = kind
        return (
          <BlockShell
            key={i}
            label={kind.label}
            icon={kind.icon}
            onMoveUp={() => moveBlock(i, -1)}
            onMoveDown={() => moveBlock(i, 1)}
            onRemove={() => removeBlock(i)}
            canMoveUp={i > 0}
            canMoveDown={i < blocks.length - 1}
          >
            <Editor block={block} onChange={(next) => updateBlock(i, next)} />
          </BlockShell>
        )
      })}

      <div className="border border-dashed border-taupe-300 p-3">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-charcoal-600/70">Add a block</p>
        <div className="flex flex-wrap gap-2">
          {ADD_MENU.map(({ type, label, icon: Icon }) => (
            <button
              key={type}
              type="button"
              onClick={() => addBlock(type)}
              className="flex items-center gap-1.5 border border-taupe-300 px-2.5 py-1.5 text-xs font-medium text-charcoal-600 hover:border-burgundy-500 hover:text-burgundy-600"
            >
              <Icon size={13} /> {label}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
