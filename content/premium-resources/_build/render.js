const { chromium } = require('playwright');
(async () => {
  const [,, inHtml, outPdf] = process.argv;
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('file://' + inHtml, { waitUntil: 'networkidle', timeout: 60000 });
  await page.evaluate(() => document.fonts.ready);
  await page.pdf({ path: outPdf, format: 'A4', preferCSSPageSize: true, printBackground: true, displayHeaderFooter: false });
  await browser.close();
})();
