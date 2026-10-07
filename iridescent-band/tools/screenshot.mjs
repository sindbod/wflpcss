// Headless screenshots for visual checks: node tools/screenshot.mjs out.png '<js to run before shot>' [width height wait_ms]
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join( dirname( fileURLToPath( import.meta.url ) ), '..', 'dist' );
const types = { '.html': 'text/html', '.js': 'text/javascript', '.hdr': 'application/octet-stream', '.png': 'image/png', '.jpg': 'image/jpeg', '.webp': 'image/webp', '.json': 'application/json', '.mp4': 'video/mp4', '.webm': 'video/webm' };
const server = createServer( ( req, res ) => {

	const p = join( root, decodeURIComponent( req.url.split( '?' )[ 0 ] ) );
	if ( ! existsSync( p ) || statSync( p ).isDirectory() ) {

		res.writeHead( 404 ); res.end(); return;

	}
	res.writeHead( 200, { 'Content-Type': types[ extname( p ) ] || 'application/octet-stream' } );
	res.end( readFileSync( p ) );

} ).listen( 0 );
const port = server.address().port;

const [ out = 'shot.png', script = '', w = '1280', h = '800', wait = '1500', pageName = 'preview.html' ] = process.argv.slice( 2 );
const browser = await chromium.launch( {
	executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
	args: [ '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-webgl' ],
} );
const page = await browser.newPage( { viewport: { width: + w, height: + h } } );
const logs = [];
page.on( 'console', ( m ) => logs.push( `[${m.type()}] ${m.text()}` ) );
page.on( 'pageerror', ( e ) => logs.push( `[pageerror] ${e.message}` ) );
await page.goto( `http://localhost:${port}/${pageName}` );
try {

	await page.waitForFunction( () => window.__lab && window.__lab.ready, null, { timeout: 120000 } );
	if ( script ) await page.evaluate( `(async () => { ${script} })()` );
	await page.waitForTimeout( + wait );

} catch ( e ) {

	logs.push( '[harness] ' + e.message );

}
await page.screenshot( { path: out } );
console.log( logs.filter( ( l ) => ! l.includes( 'GPU stall' ) ).slice( 0, 40 ).join( '\n' ) );
await browser.close();
server.close();
