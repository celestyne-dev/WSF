import { chromium } from 'playwright'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.screenshot({ path: '.scratch/home-full.png', fullPage: true })
await browser.close()
console.log('done')
