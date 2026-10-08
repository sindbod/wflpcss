// Print the pattern page to PDF, once per unit system.
//   node tools/make_pdf.js            (run from the kogge-quilt folder)
// Needs Playwright with Chromium.
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

(async () => {
  const root = path.resolve(__dirname, '..');
  const browser = await chromium.launch();
  for (const units of ['cm', 'in']) {
    // A4 minus the side margins: anything wider makes Chrome shrink every page,
    // and the templates would no longer print at true size.
    const page = await browser.newPage({ colorScheme: 'light', viewport: { width: 688, height: 1000 } });
    await page.goto('file://' + path.join(root, 'index.html'), { waitUntil: 'load' });
    await page.evaluate((u) => {
      if (u === 'in') document.documentElement.setAttribute('data-units', 'in');
      else document.documentElement.removeAttribute('data-units');
      document.documentElement.removeAttribute('data-cw');
    }, units);
    await page.emulateMedia({ media: 'print' });
    await page.waitForTimeout(400);
    const wide = await page.evaluate(() => document.documentElement.scrollWidth);
    if (wide > 688) throw new Error(`${units}: the page is ${wide}px wide in print, wider than A4; templates would shrink`);
    const out = path.join(root, `kogge-pattern-${units}.pdf`);
    await page.pdf({
      path: out, format: 'A4', printBackground: true,
      margin: { top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' },
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="font:8px Helvetica,Arial,sans-serif;color:#777;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>Kogge · Hanseatic cog patchwork quilt</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    });
    console.log('wrote', out);
    await page.close();
  }
  await browser.close();
})();
