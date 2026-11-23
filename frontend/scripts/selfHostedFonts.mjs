// Vite plugin for the self-hosted fonts (src/fonts.css, src/assets/fonts).
//
// 1. Preloads ONLY the two above-the-fold files: the latin upright Inter and
//    Fraunces variable fonts (body text and headings). Italic and latin-ext
//    files load on demand through unicode-range, never preloaded.
// 2. Ships the SIL OFL 1.1 licence texts next to the built font files.
//
// The preload hrefs are the fingerprinted /assets/ names from the build, so
// they always match the files the CSS references.
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

export const PRELOADED_FONTS = ['inter-latin-normal', 'fraunces-latin-normal']
const LICENCES = ['OFL-Fraunces.txt', 'OFL-Inter.txt']
const fontsDir = fileURLToPath(new URL('../src/assets/fonts/', import.meta.url))

export function preloadTags(bundle) {
  const tags = []
  for (const base of PRELOADED_FONTS) {
    const asset = Object.values(bundle).find(
      (item) => item.type === 'asset' && item.fileName.endsWith('.woff2') && item.fileName.includes(`/${base}-`),
    )
    if (!asset) throw new Error(`Self-hosted font ${base}.woff2 is missing from the build output.`)
    tags.push(`<link rel="preload" href="/${asset.fileName}" as="font" type="font/woff2" crossorigin>`)
  }
  return tags
}

// Right after <meta charset> (which must stay first), ahead of the scripts
// and stylesheet, so the two font downloads start as early as possible.
export function injectPreloads(html, tags) {
  const anchor = /<meta charset="[^"]*"\s*\/?>/i
  if (!anchor.test(html)) throw new Error('index.html needs a <meta charset> tag for the font preloads.')
  return html.replace(anchor, (meta) => `${meta}\n    ${tags.join('\n    ')}`)
}

export default function selfHostedFonts() {
  return {
    name: 'wsf-self-hosted-fonts',
    apply: 'build',
    generateBundle() {
      for (const name of LICENCES) {
        this.emitFile({ type: 'asset', fileName: `assets/fonts/${name}`, source: readFileSync(fontsDir + name) })
      }
    },
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        return ctx.bundle ? injectPreloads(html, preloadTags(ctx.bundle)) : html
      },
    },
  }
}
