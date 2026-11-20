// Studio -> Settings -> Appearance. The server already writes
// data-wsf-corners on <html> for every page (backend spa_shell), so the
// first paint uses the saved preset; this only keeps the attribute in sync
// with the public settings the app loads anyway (no extra request), e.g.
// after a Studio save or when index.html was served without the server.
// Only the four controlled presets ever reach the DOM.
export const CORNER_STYLES = [
  { value: 'square', label: 'Square', radius: '0px', description: 'Crisp, editorial edges. How the site has always looked.' },
  { value: 'subtle', label: 'Subtle', radius: '~6px', description: 'A barely-there softening of cards and buttons.' },
  { value: 'soft', label: 'Soft', radius: '~12px', description: 'Friendly, modern rounding on cards and panels.' },
  { value: 'rounded', label: 'Rounded', radius: '~18px', description: 'Generous rounding for a warmer, app-like feel.' },
]
export const DEFAULT_CORNER_STYLE = 'square'
const VALUES = new Set(CORNER_STYLES.map((c) => c.value))

export function resolveCornerStyle(value) {
  return VALUES.has(value) ? value : DEFAULT_CORNER_STYLE
}

export function applyCornerStyle(value, root = typeof document !== 'undefined' ? document.documentElement : null) {
  if (!root) return
  const style = resolveCornerStyle(value)
  if (root.dataset.wsfCorners !== style) root.dataset.wsfCorners = style
}
