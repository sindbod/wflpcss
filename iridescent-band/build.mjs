// Build: bundles the map worker to a string, then the app; assembles dist/ (page + assets).
import * as esbuild from 'esbuild';
import { readFileSync, writeFileSync, mkdirSync, cpSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname( fileURLToPath( import.meta.url ) );
const dist = join( root, 'dist' );
mkdirSync( dist, { recursive: true } );

// The path tracer's diffuse lobe uses a scalar (1 - F). Replace it with the film transmittance
// T(theta_in) * T(theta_out) so light that passes the interference layer carries the complementary tint,
// and apply the stacked-platelet reflectance gain to the film's specular Fresnel.
const layeredDiffusePatch = {
	name: 'layered-diffuse-patch',
	setup( build ) {

		build.onLoad( { filter: /three-gpu-pathtracer[\\/]src[\\/]shader[\\/]bsdf[\\/]bsdf_functions\.glsl\.js$/ }, ( args ) => {

			let src = readFileSync( args.path, 'utf8' );
			const before = 'color = ( 1.0 - F ) * transFactor * metalFactor * wi.z * surf.color * ( retro + lambert ) / PI;';
			if ( ! src.includes( before ) ) throw new Error( 'path tracer diffuse patch: anchor not found' );
			const after = `vec3 filmT = vec3( 1.0 - F );
		if ( surf.iridescence > 0.0 ) {

			vec3 f0c = vec3( surf.f0 ) * surf.specularColor * surf.specularIntensity;
			vec3 Ti = clamp( vec3( 1.0 ) - evalIridescence( 1.0, surf.iridescenceIor, abs( wi.z ), surf.iridescenceThickness, f0c ), 0.0, 1.0 );
			vec3 To = clamp( vec3( 1.0 ) - evalIridescence( 1.0, surf.iridescenceIor, abs( wo.z ), surf.iridescenceThickness, f0c ), 0.0, 1.0 );
			filmT = mix( filmT, Ti * To, surf.iridescence );

		}
		color = filmT * transFactor * metalFactor * wi.z * surf.color * ( retro + lambert ) / PI;`;
			src = src.replace( before, after );
			// stacked-platelet gain on the film reflection (same calibration as approach 2 and the Cycles nodes)
			const specBefore = 'F = mix( F, iridescenceF,  surf.iridescence );';
			if ( ! src.includes( specBefore ) ) throw new Error( 'path tracer specular patch: anchor not found' );
			src = src.replace( specBefore, 'F = mix( F, min( iridescenceF * 1.6, vec3( 1.0 ) ), surf.iridescence );' );
			return { contents: src, loader: 'js' };

		} );

	},
};

const prod = ! process.argv.includes( '--dev' );

const worker = await esbuild.build( {
	entryPoints: [ join( root, 'src/core/maps-worker.js' ) ],
	bundle: true, format: 'iife', minify: prod, write: false, target: 'es2022',
} );
const workerSrc = worker.outputFiles[ 0 ].text;

const app = await esbuild.build( {
	entryPoints: [ join( root, 'src/main.js' ) ],
	bundle: true, format: 'esm', minify: prod, write: false, target: 'es2022',
	define: { __MAPS_WORKER_SRC__: JSON.stringify( workerSrc ) },
	plugins: [ layeredDiffusePatch ],
	legalComments: 'none',
	logLevel: 'warning',
} );
const appJs = app.outputFiles[ 0 ].text;
writeFileSync( join( dist, 'app.js' ), appJs );

// Page: template with the bundle inlined (artifact pages are single documents; assets load relatively).
const template = readFileSync( join( root, 'page/index.html' ), 'utf8' );
const page = template.replace( '<!--APP-->', () => `<script type="module">\n${appJs.replace( /<\/script/g, '<\\/script' )}\n</script>` );
writeFileSync( join( dist, 'index.html' ), page );

// Local preview wrapper (adds the skeleton the artifact host adds at publish time).
writeFileSync( join( dist, 'preview.html' ), `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><style>:root{color-scheme:light}body{margin:0;font:14px system-ui,sans-serif;background:#f6f6f4}img{max-width:100%}[hidden]{display:none!important}</style></head><body>${page}</body></html>` );

for ( const dir of [ 'hdr', 'cycles', 'ref' ] ) {

	const src = join( root, 'assets', dir );
	if ( existsSync( src ) ) cpSync( src, join( dist, dir ), { recursive: true } );

}
console.log( `built dist/index.html (${( page.length / 1024 ).toFixed( 0 )} KB page, ${( appJs.length / 1024 ).toFixed( 0 )} KB js)` );
