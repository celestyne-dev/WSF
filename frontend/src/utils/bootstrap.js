// WSF SEO Phase 2D — reads the small, non-executable
// <script type="application/json" data-wsf-bootstrap="{type}"> tag the
// server (backend/app/services/spa_shell.py's _set_bootstrap_data)
// embeds in the initial HTML for a hard load of "/" or an Article's flat
// /{slug} route, so that route's own first client-side fetch (GET
// /public/homepage, or GET /articles/{slug}) can be skipped entirely —
// see frontend/src/store/index.js (homepage) and pages/ArticlePage.jsx
// (article) for the two call sites.
//
// `readBootstrap` is deliberately side-effect-free (it only reads
// `textContent` and JSON.parses it — it never removes the script tag)
// so it's safe to call from a useState/useMemo lazy initializer even
// under React 18 StrictMode's dev-only double-render: both invocations
// see the same still-present tag and compute the same result, so
// whichever one React keeps is correct either way. The actual one-time
// "consumption" — removing the tag so a later SPA navigation never
// finds (or re-reads) it — is a separate call, `consumeBootstrap`,
// because removing a DOM node IS a real side effect and would NOT be
// safe to couple to a lazy initializer the same way; callers invoke it
// once from an effect (ArticlePage.jsx) or inline at module-evaluation
// time (store/index.js, which only ever runs once per real page load,
// never double-invoked by StrictMode). Consuming late (from an effect)
// rather than eagerly is fine either way: the real one-shot guarantee
// callers need — a later SPA navigation never reusing this slug/type's
// bootstrap — already comes from the fact that nothing calls
// `readBootstrap` again after a component's first mount for that route,
// not from the DOM removal itself; the removal is cleanup, not the
// correctness mechanism.

function bootstrapScriptSelector(type) {
  return `script[type="application/json"][data-wsf-bootstrap="${type}"]`
}

/**
 * Returns the parsed `{key, data}` bootstrap payload for `type`
 * ("article" | "homepage"), or `null` when there's nothing to use —
 * every one of these is a normal, expected "fall back to the API"
 * case, never thrown: no `document` (a non-browser environment, e.g. a
 * future test runner), no matching script tag (most routes never get
 * one), malformed JSON, or (when `expectedKey` is passed) a `key` that
 * doesn't match the route the caller is actually rendering — e.g. an
 * Article bootstrap embedded for slug "a" must never be consumed by a
 * render of slug "b".
 */
export function readBootstrap(type, expectedKey) {
  if (typeof document === 'undefined') return null
  const el = document.querySelector(bootstrapScriptSelector(type))
  if (!el) return null
  let payload
  try {
    payload = JSON.parse(el.textContent)
  } catch {
    return null
  }
  if (!payload || typeof payload !== 'object') return null
  if (expectedKey !== undefined && payload.key !== expectedKey) return null
  return payload
}

/**
 * Removes the now-consumed bootstrap script tag for `type`, if still
 * present. Safe to call more than once, or when there was never a tag
 * to begin with (e.g. `readBootstrap` returned null) — removing an
 * already-absent element is a no-op, not an error.
 */
export function consumeBootstrap(type) {
  if (typeof document === 'undefined') return
  document.querySelector(bootstrapScriptSelector(type))?.remove()
}
