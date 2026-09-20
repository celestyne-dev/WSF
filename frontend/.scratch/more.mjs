import { chromium } from 'playwright'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()

const pages = [
  ['people/naliaka-wafula', 'person-profile'],
  ['series/founder-stories', 'series-detail'],
  ['opportunities', 'opportunities-list'],
  ['search?q=leadership', 'search'],
  ['partnerships', 'partnerships'],
]
for (const [path, name] of pages) {
  await page.goto(`http://localhost:5173/${path}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(300)
  await page.screenshot({ path: `.scratch/${name}.png`, fullPage: true })
}

// admin submissions (already logged in via storage state? need login again)
await page.goto('http://localhost:5173/login', { waitUntil: 'networkidle' })
await page.fill('#email', 'wanjiru@womenshapingfutures.org')
await page.fill('#password', 'demo1234')
await page.click('button[type=submit]')
await page.waitForTimeout(500)
await page.goto('http://localhost:5173/admin/submissions', { waitUntil: 'networkidle' })
await page.screenshot({ path: '.scratch/admin-submissions.png', fullPage: true })

await browser.close()
console.log('done')
