// Print the pattern page to PDF: metric on A4, imperial on US Letter.
//   node tools/make_pdf.js            (run from the kogge-quilt folder)
// Needs Playwright with Chromium.
const path = require('path');
let chromium;
try { ({ chromium } = require('playwright')); } catch (e) { ({ chromium } = require('/opt/node22/lib/node_modules/playwright')); }

const MARGIN = { top: '14mm', bottom: '16mm', left: '14mm', right: '14mm' };
const PX_PER_MM = 96 / 25.4;
// paper width minus the side margins, in CSS pixels
const PAPERS = {
  cm: { format: 'A4', printable: Math.floor((210 - 28) * PX_PER_MM) },
  in: { format: 'Letter', printable: Math.floor((215.9 - 28) * PX_PER_MM) },
};

(async () => {
  const root = path.resolve(__dirname, '..');
  const browser = await chromium.launch();
  for (const units of ['cm', 'in']) {
    const paper = PAPERS[units];
    // Anything wider than the printable width makes Chrome shrink every page,
    // and the templates would no longer print at true size.
    const page = await browser.newPage({ colorScheme: 'light', viewport: { width: paper.printable, height: 1000 } });
    await page.goto('file://' + path.join(root, 'index.html'), { waitUntil: 'load' });
    await page.evaluate((u) => {
      if (u === 'in') document.documentElement.setAttribute('data-units', 'in');
      else document.documentElement.removeAttribute('data-units');
      document.documentElement.removeAttribute('data-cw');
    }, units);
    await page.emulateMedia({ media: 'print' });
    await page.waitForTimeout(400);
    const wide = await page.evaluate(() => document.documentElement.scrollWidth);
    if (wide > paper.printable) {
      throw new Error(`${units}: the page is ${wide}px wide in print, wider than ${paper.format}; templates would shrink`);
    }
    const ver = await page.evaluate(() => {
      const m = (document.querySelector('footer .version') || { textContent: '' }).textContent.match(/version ([\d.]+), ([A-Za-z]+ \d{4})/);
      return m ? `version ${m[1]}, ${m[2]}` : '';
    });
    const out = path.join(root, `kogge-pattern-${units}.pdf`);
    await page.pdf({
      path: out, format: paper.format, printBackground: true, margin: MARGIN,
      outline: true, tagged: true,
      displayHeaderFooter: true,
      headerTemplate: '<span></span>',
      footerTemplate: `<div style="font:8px Helvetica,Arial,sans-serif;color:#777;width:100%;padding:0 14mm;display:flex;justify-content:space-between"><span>Kogge · Hanseatic cog patchwork quilt${ver ? ' · ' + ver : ''}</span><span><span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`,
    });
    console.log('wrote', out, paper.format);
    await page.close();
  }
  await browser.close();
})();
