import { useEffect, useRef, useState } from 'react'
import { Bold, Italic, Link as LinkIcon, Unlink } from 'lucide-react'
import { normalizeEditorLink } from '../../utils/linkSafety'

// The ONE inline rich-text field of the CMS (paragraphs, list items,
// quotes, callouts, learning blocks…): bold, italic and links only — no
// headings, images or nested lists. No editor framework: native
// contentEditable + execCommand covers exactly this. Everything it
// produces is re-sanitized server-side (backend content_blocks
// _clean_inline_html: b/strong/i/em/u/a/br, http(s)/mailto/relative links).
//
// Links are validated HERE, at entry time, with the same rule the public
// site applies (utils/linkSafety): a site path ("/resources/…"), a full
// http(s) address, or an email. "www.example.org" becomes https://; an
// unsafe or malformed link is refused with a message instead of being
// silently stripped later.
const KEEP = { B: 'strong', STRONG: 'strong', I: 'em', EM: 'em', U: 'u', A: 'a', BR: 'br' }

// Pasted HTML (from a web page or a document) reduced to what this field
// allows: bold, italic, underline, links, line breaks. Every pasted link
// goes through the same normalizeEditorLink rule as the link button; one
// that can't be used is unwrapped to its text AND reported back, so the
// editor sees it at paste time instead of losing it silently.
function cleanPasted(node, doc, dropped) {
  const frag = doc.createDocumentFragment()
  node.childNodes.forEach((child) => {
    if (child.nodeType === 3) {
      frag.appendChild(doc.createTextNode(child.textContent.replace(/\s+/g, ' ')))
      return
    }
    if (child.nodeType !== 1 || /^(SCRIPT|STYLE|IFRAME|OBJECT|EMBED|TEMPLATE|HEAD|META|TITLE)$/.test(child.tagName)) return
    const tag = KEEP[child.tagName]
    const inner = cleanPasted(child, doc, dropped)
    if (tag === 'br') {
      frag.appendChild(doc.createElement('br'))
    } else if (tag === 'a') {
      const href = child.getAttribute('href') || ''
      const { url } = normalizeEditorLink(href)
      if (url) {
        const a = doc.createElement('a')
        a.setAttribute('href', url)
        a.appendChild(inner)
        frag.appendChild(a)
      } else {
        if (href) dropped.push(href)
        frag.appendChild(inner)
      }
    } else if (tag) {
      const el = doc.createElement(tag)
      el.appendChild(inner)
      frag.appendChild(el)
    } else {
      frag.appendChild(inner)
      if (/^(P|DIV|LI|H[1-6]|TR)$/.test(child.tagName)) frag.appendChild(doc.createTextNode(' '))
    }
  })
  return frag
}

export default function RichTextField({ value, onChange, placeholder, className = '', compact = false, ariaLabel, onEnter }) {
  const ref = useRef(null)
  const [linkError, setLinkError] = useState(null)

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
    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || !ref.current?.contains(selection.anchorNode)) {
      setLinkError('Select the words to link first, then press the link button.')
      return
    }
    const raw = window.prompt('Link address — a site path like /resources/salary-guide, or a full https:// address')
    if (raw === null) return
    const { url, error } = normalizeEditorLink(raw)
    if (error) {
      setLinkError(error)
      return
    }
    setLinkError(null)
    exec('createLink', url)
  }

  function handlePaste(e) {
    const htmlData = e.clipboardData?.getData('text/html')
    const text = e.clipboardData?.getData('text/plain') || ''
    e.preventDefault()
    const dropped = []
    let html
    if (htmlData) {
      const parsed = new DOMParser().parseFromString(htmlData, 'text/html')
      const holder = document.createElement('div')
      holder.appendChild(cleanPasted(parsed.body, document, dropped))
      html = holder.innerHTML.replace(/\s{2,}/g, ' ').trim()
    } else {
      const holder = document.createElement('div')
      holder.textContent = onEnter ? text.replace(/\s+/g, ' ') : text
      html = holder.innerHTML.replace(/\n/g, '<br>')
    }
    document.execCommand('insertHTML', false, html)
    onChange(ref.current?.innerHTML || '')
    setLinkError(
      dropped.length
        ? `Pasted text kept, but ${dropped.length === 1 ? 'one link was' : `${dropped.length} links were`} removed because the address can’t be used: ${dropped.slice(0, 3).join(', ')}. Select the words and add the link again with a full https:// address or a site path.`
        : null,
    )
  }

  const btn = 'rounded p-1 text-charcoal-600 hover:bg-taupe-200 hover:text-charcoal'
  return (
    <div className="min-w-0 flex-1">
      <div className={`flex gap-1 border border-b-0 border-taupe-300 bg-taupe-100 ${compact ? 'px-1 py-0.5' : 'px-1.5 py-1'}`}>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('bold')} aria-label="Bold" className={btn}>
          <Bold size={compact ? 12 : 14} />
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('italic')} aria-label="Italic" className={btn}>
          <Italic size={compact ? 12 : 14} />
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={handleLink} aria-label="Add link" className={btn}>
          <LinkIcon size={compact ? 12 : 14} />
        </button>
        <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => exec('unlink')} aria-label="Remove link" className={btn}>
          <Unlink size={compact ? 12 : 14} />
        </button>
      </div>
      <div
        ref={ref}
        role="textbox"
        aria-multiline={!onEnter}
        aria-label={ariaLabel || placeholder}
        contentEditable
        suppressContentEditableWarning
        data-placeholder={placeholder}
        onInput={(e) => onChange(e.currentTarget.innerHTML)}
        onBlur={(e) => onChange(e.currentTarget.innerHTML)}
        onPaste={handlePaste}
        onKeyDown={(e) => {
          // A list item is one line: Enter starts the next item instead.
          if (onEnter && e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            onEnter()
          }
        }}
        className={`rich-text-input ${compact ? '!min-h-[2.25rem] !py-1.5' : ''} ${className}`}
      />
      {linkError && (
        <p className="mt-1 text-xs text-rose-600" role="alert">
          {linkError}
        </p>
      )}
    </div>
  )
}
