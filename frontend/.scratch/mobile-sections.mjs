import { chromium } from 'playwright'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })
const context = await browser.newContext({ viewport: { width: 390, height: 844 } })
const page = await context.newPage()
await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await page.screenshot({ path: '.scratch/mobile-top.png' })

// open mobile nav
await page.click('button[aria-label="Open menu"]')
await page.waitForTimeout(300)
await page.screenshot({ path: '.scratch/mobile-nav.png' })
await page.click('button[aria-label="Close menu"]')

await page.goto('http://localhost:5173/how-women-are-redefining-leadership', { waitUntil: 'networkidle' })
await page.screenshot({ path: '.scratch/mobile-article-top.png' })
await page.mouse.wheel(0, 2000)
await page.waitForTimeout(200)
await page.screenshot({ path: '.scratch/mobile-article-mid.png' })

await page.goto('http://localhost:5173/jobs', { waitUntil: 'networkidle' })
await page.screenshot({ path: '.scratch/mobile-jobs.png' })

await browser.close()
console.log('done')
