// Generates backend/app/data/first_paint_icons.json: the exact SVG markup
// lucide-react renders for the icons the server first paint mirrors.
// Usage: node scripts/gen-first-paint-icons.mjs ../backend/app/data/first_paint_icons.json
import { writeFileSync } from 'node:fs'
import { renderFirstPaintIcons } from './firstPaintIcons.mjs'

const out = renderFirstPaintIcons()
writeFileSync(process.argv[2], JSON.stringify(out, null, 1) + '\n')
console.log(Object.keys(out).length, 'icons')
