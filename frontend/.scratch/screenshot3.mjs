import { chromium } from 'playwright'
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' })

const desktop = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const dp = await desktop.newPage()
await dp.goto('http://localhost:5173/how-women-are-redefining-leadership', { waitUntil: 'networkidle' })
await dp.screenshot({ path: '.scratch/article-full.png', fullPage: true })

await dp.goto('http://localhost:5173/login', { waitUntil: 'networkidle' })
await dp.fill('#email', 'wanjiru@womenshapingfutures.org')
await dp.fill('#password', 'demo1234')
await dp.click('button[type=submit]')
await dp.waitForTimeout(700)
await dp.screenshot({ path: '.scratch/admin-dashboard.png', fullPage: true })

await dp.goto('http://localhost:5173/admin/articles/new', { waitUntil: 'networkidle' })
await dp.screenshot({ path: '.scratch/admin-editor.png', fullPage: true })

await dp.goto('http://localhost:5173/admin/homepage', { waitUntil: 'networkidle' })
await dp.screenshot({ path: '.scratch/admin-homepage.png', fullPage: true })

const mobile = await browser.newContext({ viewport: { width: 390, height: 844 } })
const mp = await mobile.newPage()
await mp.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
await mp.screenshot({ path: '.scratch/home-mobile-full.png', fullPage: true })

await mp.goto('http://localhost:5173/how-women-are-redefining-leadership', { waitUntil: 'networkidle' })
await mp.screenshot({ path: '.scratch/article-mobile.png', fullPage: true })

await browser.close()
console.log('done')
