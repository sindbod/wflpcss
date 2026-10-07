// End-to-end check of the dataset export through the UI: node tools/test-export.mjs <approach-number> <out.zip>
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { join, extname } from 'node:path';
const root = new URL( '../dist', import.meta.url ).pathname;
const server = createServer( ( req, res ) => {

	const p = join( root, decodeURIComponent( req.url.split( '?' )[ 0 ] ) );
	if ( ! existsSync( p ) || statSync( p ).isDirectory() ) {

		res.writeHead( 404 ); res.end(); return;

	}
	res.writeHead( 200, { 'Content-Type': { '.html': 'text/html', '.js': 'text/javascript' }[ extname( p ) ] || 'application/octet-stream' } );
	res.end( readFileSync( p ) );

} ).listen( 0 );
const [ num = '2', out = 'export.zip' ] = process.argv.slice( 2 );
const browser = await chromium.launch( { executablePath: '/opt/pw-browsers/chromium-1194/chrome-linux/chrome', args: [ '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist' ] } );
const page = await browser.newPage( { viewport: { width: 1280, height: 900 }, acceptDownloads: true } );
page.on( 'pageerror', ( e ) => console.log( 'PAGEERROR', e.message ) );
await page.goto( `http://localhost:${server.address().port}/preview.html#a${num}` );
await page.waitForFunction( () => window.__lab && window.__lab.ready, null, { timeout: 120000 } );
await page.click( '#g-capture > summary' );
await page.click( 'label[for="cap-count-12"], #cap-count-12', { force: true } );
await page.click( '#cap-size-512', { force: true } );
const t0 = Date.now();
const [ dl ] = await Promise.all( [
	page.waitForEvent( 'download', { timeout: 600000 } ),
	page.click( 'text=Export dataset (.zip)' ),
] );
await dl.saveAs( out );
console.log( 'download', dl.suggestedFilename(), 'in', ( ( Date.now() - t0 ) / 1000 ).toFixed( 1 ), 's' );
console.log( 'status:', await page.textContent( '.progress' ) );
await browser.close();
server.close();
