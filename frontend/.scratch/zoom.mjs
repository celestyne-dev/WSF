import { chromium } from 'playwright'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
await page.goto('http://localhost:5173/how-women-are-redefining-leadership', { waitUntil: 'networkidle' })
const el = await page.locator('text=Featured in this story').locator('xpath=ancestor::div[contains(@class,"border")][1]')
await el.screenshot({ path: '.scratch/featured-box.png' })
await browser.close()
console.log('done')
