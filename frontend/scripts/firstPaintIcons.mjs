// The lucide-react icons the server first paint mirrors (backend
// app/services/first_paint.py), with the exact props each component passes.
// Shared by gen-first-paint-icons.mjs and the contract test.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import * as L from 'lucide-react'

export const specs = {
  search: ['Search', { size: 20, 'aria-hidden': 'true' }],
  user: ['User', { size: 20, 'aria-hidden': 'true' }],
  chevronDown: ['ChevronDown', { size: 14, 'aria-hidden': 'true', className: 'transition-transform' }],
  menu: ['Menu', { size: 26, 'aria-hidden': 'true' }],
  arrowRight16: ['ArrowRight', { size: 16, className: 'transition-transform group-hover:translate-x-0.5' }],
  arrowRight16Plain: ['ArrowRight', { size: 16 }],
  arrowUpRight18: ['ArrowUpRight', { size: 18, className: 'transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5' }],
  quote32: ['Quote', { size: 32, className: 'mt-4 text-blush-200/70' }],
  clock12: ['Clock', { size: 12, 'aria-hidden': 'true' }],
  clock13: ['Clock', { size: 13 }],
  mapPin13: ['MapPin', { size: 13, 'aria-hidden': 'true' }],
  mapPin13Plain: ['MapPin', { size: 13 }],
  globe13: ['Globe2', { size: 13 }],
  calendarClock12: ['CalendarClock', { size: 12, 'aria-hidden': 'true' }],
  chevronRight12: ['ChevronRight', { size: 12 }],
  chevronDown18Toc: ['ChevronDown', { size: 18, 'aria-hidden': 'true', className: 'text-charcoal-600 transition-transform group-open:rotate-180' }],
  sparkles14: ['Sparkles', { size: 14, className: 'mt-0.5 shrink-0 text-charcoal-600/60' }],
  mail11: ['Mail', { size: 11 }],
  lock11: ['Lock', { size: 11 }],
  sparkles11: ['Sparkles', { size: 11 }],
  externalLink11: ['ExternalLink', { size: 11 }],
  'pathway:briefcase': ['Briefcase', { size: 20, 'aria-hidden': 'true' }],
  'pathway:graduation-cap': ['GraduationCap', { size: 20, 'aria-hidden': 'true' }],
  'pathway:users': ['Users', { size: 20, 'aria-hidden': 'true' }],
  'pathway:book-open': ['BookOpen', { size: 20, 'aria-hidden': 'true' }],
  'pathway:lightbulb': ['Lightbulb', { size: 20, 'aria-hidden': 'true' }],
  'pathway:compass': ['Compass', { size: 20, 'aria-hidden': 'true' }],
  'pathway:calendar': ['Calendar', { size: 20, 'aria-hidden': 'true' }],
  'pathway:sparkles': ['Sparkles', { size: 20, 'aria-hidden': 'true' }],
  'pathway:heart-handshake': ['HeartHandshake', { size: 20, 'aria-hidden': 'true' }],
  'pathway:rocket': ['Rocket', { size: 20, 'aria-hidden': 'true' }],
  'pathway:target': ['Target', { size: 20, 'aria-hidden': 'true' }],
  'pathway:megaphone': ['Megaphone', { size: 20, 'aria-hidden': 'true' }],
  'pathway:globe': ['Globe', { size: 20, 'aria-hidden': 'true' }],
  'pathway:award': ['Award', { size: 20, 'aria-hidden': 'true' }],
}

export function renderFirstPaintIcons() {
  const out = {}
  for (const [key, [name, props]] of Object.entries(specs)) out[key] = renderToStaticMarkup(createElement(L[name], props))
  return out
}
