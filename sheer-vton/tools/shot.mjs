// Full-page screenshots of dist/preview.html: node tools/shot.mjs <out.png> [width] [scheme light|dark]
import { createRequire } from 'node:module';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(join(here, '..', '..', 'iridescent-band', 'package.json'));
const { chromium } = require('playwright');
const root = join(here, '..', 'dist');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg', '.json': 'application/json' };
const server = createServer((req, res) => {
  const p = join(root, decodeURIComponent(req.url.split('?')[0]));
  if (!existsSync(p) || statSync(p).isDirectory()) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'Content-Type': types[extname(p)] || 'application/octet-stream' });
  res.end(readFileSync(p));
}).listen(0);
const [out = 'shot.png', w = '1280', scheme = 'light'] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome' });
const page = await browser.newPage({ viewport: { width: +w, height: 900 }, colorScheme: scheme });
const logs = [];
page.on('console', (m) => logs.push(`${m.type()}: ${m.text()}`));
page.on('pageerror', (e) => logs.push(`pageerror: ${e.message}`));
page.on('requestfailed', (r) => logs.push(`failed: ${r.url()}`));
await page.goto(`http://127.0.0.1:${server.address().port}/preview.html`, { waitUntil: 'networkidle' });
await page.waitForTimeout(1200);
const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
await page.screenshot({ path: out, fullPage: true });
console.log(JSON.stringify({ overflow, logs: logs.filter((l) => !l.includes('fonts.g')) }, null, 1));
await browser.close();
server.close();
