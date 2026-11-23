import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { PRELOADED_FONTS, injectPreloads, preloadTags } from './selfHostedFonts.mjs'

const root = new URL('..', import.meta.url).pathname

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) walk(full, out)
    else if (/\.(jsx?|mjs|css|html)$/.test(entry.name)) out.push(full)
  }
  return out
}

test('no source file references Google Fonts', () => {
  const files = [join(root, 'index.html'), ...walk(join(root, 'src'))]
  for (const file of files) {
    const text = readFileSync(file, 'utf8')
    assert.ok(!/fonts\.(googleapis|gstatic)\.com/.test(text), `${file} still references Google Fonts`)
  }
})

test('every @font-face is a local woff2 with font-display: swap, and the OFL licences ship with it', () => {
  const css = readFileSync(join(root, 'src/fonts.css'), 'utf8')
  const faces = css.match(/@font-face \{[^}]+\}/g)
  assert.equal(faces.length, 6)
  for (const face of faces) {
    assert.match(face, /font-display: swap;/)
    assert.match(face, /src: url\('\.\/assets\/fonts\/[a-z-]+\.woff2'\) format\('woff2'\);/)
    assert.match(face, /unicode-range: /)
  }
  const dir = readdirSync(join(root, 'src/assets/fonts'))
  for (const licence of ['OFL-Fraunces.txt', 'OFL-Inter.txt']) {
    assert.ok(dir.includes(licence))
    assert.match(readFileSync(join(root, 'src/assets/fonts', licence), 'utf8'), /SIL OPEN FONT LICENSE Version 1\.1/)
  }
})

test('only the two main upright latin files are preloaded, right after <meta charset>', () => {
  const bundle = {
    a: { type: 'asset', fileName: 'assets/inter-latin-normal-AAA.woff2' },
    b: { type: 'asset', fileName: 'assets/fraunces-latin-normal-BBB.woff2' },
    c: { type: 'asset', fileName: 'assets/fraunces-latin-italic-CCC.woff2' },
    d: { type: 'asset', fileName: 'assets/inter-latin-ext-normal-DDD.woff2' },
  }
  const tags = preloadTags(bundle)
  assert.deepEqual(PRELOADED_FONTS, ['inter-latin-normal', 'fraunces-latin-normal'])
  assert.equal(tags.length, 2)
  assert.ok(tags[0].includes('/assets/inter-latin-normal-AAA.woff2'))
  assert.ok(tags.every((t) => t.includes('as="font"') && t.includes('crossorigin')))
  const html = injectPreloads('<head>\n    <meta charset="UTF-8" />\n    <title>x</title>', tags)
  assert.ok(html.indexOf('<meta charset') < html.indexOf('rel="preload"'))
  assert.ok(html.indexOf('rel="preload"') < html.indexOf('<title>'))
  assert.throws(() => preloadTags({ c: bundle.c }), /missing from the build output/)
})
