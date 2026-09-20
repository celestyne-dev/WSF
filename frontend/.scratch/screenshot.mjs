import { chromium } from 'playwright'

const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })

const pages = [
  { path: '/', name: 'home' },
  { path: '/how-women-are-redefining-leadership', name: 'article' },
  { path: '/people', name: 'people' },
  { path: '/people/naliaka-wafula', name: 'person' },
  { path: '/jobs', name: 'jobs' },
  { path: '/admin', name: 'admin-login-redirect' },
]

for (const viewport of [{ w: 1440, h: 900, tag: 'desktop' }, { w: 390, h: 844, tag: 'mobile' }]) {
  const context = await browser.newContext({ viewport: { width: viewport.w, height: viewport.h } })
  const page = await context.newPage()
  for (const p of pages) {
    await page.goto(`http://localhost:5173${p.path}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(400)
    await page.screenshot({ path: `/tmp/claude-0/-home-user-WSF/926eb765-4783-56ef-9f7b-cee4d042ac89/scratchpad/${p.name}-${viewport.tag}.png`, fullPage: viewport.tag === 'mobile' ? false : false })
  }
  await context.close()
}

await browser.close()
console.log('done')
