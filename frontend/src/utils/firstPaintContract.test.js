// Run with: node --test src/utils/firstPaintContract.test.js
// The server first paint (backend app/services/first_paint.py) mirrors the
// React components. This test fails when the shared pieces drift:
//  - backend/app/data/header_menu.json vs constants/megaMenu.js
//  - backend/app/data/first_paint_icons.json vs lucide-react markup
//  - backend/tests/fixtures/first_paint_media.json vs utils/media.js
//    (the backend test checks its own port against the same fixture)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { MENU_PRESENTATION, SECONDARY_PLACEMENT, SECONDARY_FALLBACK_MENU, MIN_TOP_LEVEL } from '../constants/megaMenu.js'
import { renderFirstPaintIcons } from '../../scripts/firstPaintIcons.mjs'

const backend = (path) => JSON.parse(readFileSync(new URL(`../../../backend/${path}`, import.meta.url), 'utf8'))

// utils/media.js reads import.meta.env (Vite); load the real file with that
// one expression stubbed so the test runs under plain Node.
async function loadMedia() {
  const source = readFileSync(new URL('./media.js', import.meta.url), 'utf8').replace(/import\.meta\.env/g, '({})')
  return import(`data:text/javascript,${encodeURIComponent(source)}`)
}

test('header_menu.json mirrors constants/megaMenu.js', () => {
  const menu = backend('app/data/header_menu.json')
  assert.equal(menu.minTopLevel, MIN_TOP_LEVEL)
  assert.equal(menu.secondaryFallbackMenu, SECONDARY_FALLBACK_MENU)
  assert.deepEqual(menu.secondaryPlacement, SECONDARY_PLACEMENT)
  const hosts = Object.fromEntries(Object.entries(MENU_PRESENTATION).map(([path, c]) => [path, { key: c.key, absorbs: c.absorbs || [] }]))
  assert.deepEqual(menu.hosts, hosts)
})

test('first_paint_icons.json is the current lucide-react markup', () => {
  assert.deepEqual(backend('app/data/first_paint_icons.json'), renderFirstPaintIcons())
})

test('first_paint_media.json is what utils/media.js produces', async () => {
  const { resolveImage, resolveMediaImage } = await loadMedia()
  const fixture = backend('tests/fixtures/first_paint_media.json')
  for (const c of fixture.placeholders) {
    assert.equal(resolveImage(null, { width: c.width, height: c.height, tone: c.tone }), c.src, JSON.stringify([c.width, c.height, c.tone]))
  }
  for (const c of fixture.media) {
    const out = resolveMediaImage(c.media, { variant: c.variant, width: c.width, height: c.height })
    // API_ORIGIN is the page origin in the browser ('' here): same URLs.
    assert.deepEqual({ src: out.src, srcSet: out.srcSet ?? null }, { src: c.src, srcSet: c.srcSet })
  }
})
