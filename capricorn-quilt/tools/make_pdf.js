// Print the pattern page to PDF, once per unit system.
//   node tools/make_pdf.js            (run from the capricorn-quilt folder)
// Needs Playwright with Chromium.
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

(async () => {
  const root = path.resolve(__dirname, '..');
  const browser = await chromium.launch();
  for (const units of ['cm', 'in']) {
    const page = await browser.newPage({ colorScheme: 'light' });
    await page.goto('file://' + path.join(root, 'index.html'), { waitUntil: 'load' });
    await page.evaluate((u) => {
      if (u === 'in') document.documentElement.setAttribute('data-units', 'in');
      else document.documentElement.removeAttribute('data-units');
      document.documentElement.removeAttribute('data-cw');
    }, units);
    await page.emulateMedia({ media: 'print' });
    await page.waitForTimeout(400);
    const out = path.join(root, `steinbock-pattern-${units}.pdf`);
    await page.pdf({
      path: out, format: 'A4', printBackground: true,
      margin: { top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' },
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: '<div style="font:8px Helvetica,Arial,sans-serif;color:#777;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>Steinbock · Capricorn patchwork wall quilt</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>',
    });
    console.log('wrote', out);
    await page.close();
  }
  await browser.close();
})();
