// The server's first paint of a hard-loaded page (its prerender inside
// #root, see backend services/spa_shell.py), captured once before React's
// first render replaces it. While that same URL is still loading its route
// chunk or its data, PageLoader shows this markup instead of a spinner, so
// a visitor never sees "page -> spinner -> page". Any other URL (a client
// navigation, a filter change) gets the normal spinner.
let snapshot = null

export function captureFirstPaintSnapshot(doc = typeof document === 'undefined' ? null : document) {
  const main = doc?.querySelector('#root > [data-wsf-prerender]')
  if (!main) return null
  const { pathname, search } = doc.defaultView?.location || {}
  snapshot = {
    url: `${pathname}${search}`,
    kind: main.getAttribute('data-wsf-prerender'),
    className: main.getAttribute('class') || '',
    html: main.innerHTML,
  }
  return snapshot
}

export function firstPaintSnapshotFor(url) {
  return snapshot && snapshot.url === url ? snapshot : null
}

export function releaseFirstPaintSnapshot() {
  snapshot = null
}
