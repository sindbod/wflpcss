// Exports the shared band assets for the offline (Blender/Cycles) approach:
//   meshes (OBJ, three.js Y-up), surface maps (PNG), height map (16-bit PNG, mm), procedural HDRIs, scene.json
// Usage: node tools/export-assets.mjs <outDir>
import { mkdirSync, writeFileSync, copyFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { deflateSync } from 'node:zlib';
import { buildRingBand, buildForm, FlexSwatch, TORSO } from '../src/core/geometry.js';
import { generateBandMaps, BAND, COLORS } from '../src/core/band.js';
import { generateEnvironment } from '../src/core/envgen.js';
import { filmSpectrum, spectrumToRgb } from '../src/core/spectral.js';
import { writePNG, writeHDR } from './png.mjs';

const root = join( dirname( fileURLToPath( import.meta.url ) ), '..' );
const out = process.argv[ 2 ] || join( root, '.cache', 'blender-assets' );
mkdirSync( out, { recursive: true } );

function writeOBJ( path, geo, name ) {

	const p = geo.attributes.position.array, n = geo.attributes.normal.array, uv = geo.attributes.uv.array;
	const idx = geo.index.array;
	const lines = [ `o ${name}` ];
	for ( let i = 0; i < p.length; i += 3 ) lines.push( `v ${p[ i ].toFixed( 6 )} ${p[ i + 1 ].toFixed( 6 )} ${p[ i + 2 ].toFixed( 6 )}` );
	for ( let i = 0; i < uv.length; i += 2 ) lines.push( `vt ${uv[ i ].toFixed( 6 )} ${uv[ i + 1 ].toFixed( 6 )}` );
	for ( let i = 0; i < n.length; i += 3 ) lines.push( `vn ${n[ i ].toFixed( 5 )} ${n[ i + 1 ].toFixed( 5 )} ${n[ i + 2 ].toFixed( 5 )}` );
	lines.push( 's 1' );
	for ( let i = 0; i < idx.length; i += 3 ) {

		const a = idx[ i ] + 1, b = idx[ i + 1 ] + 1, c = idx[ i + 2 ] + 1;
		lines.push( `f ${a}/${a}/${a} ${b}/${b}/${b} ${c}/${c}/${c}` );

	}
	writeFileSync( path, lines.join( '\n' ) + '\n' );

}

// 16-bit grayscale PNG (row 0 = bottom, flipped on write)
function writePNG16( path, width, height, values, scale ) {

	const raw = Buffer.alloc( ( width * 2 + 1 ) * height );
	for ( let y = 0; y < height; y ++ ) {

		const src = height - 1 - y;
		raw[ y * ( width * 2 + 1 ) ] = 0;
		for ( let x = 0; x < width; x ++ ) {

			const v = Math.max( 0, Math.min( 65535, Math.round( values[ src * width + x ] * scale ) ) );
			raw.writeUInt16BE( v, y * ( width * 2 + 1 ) + 1 + x * 2 );

		}

	}
	const crcTable = new Uint32Array( 256 ).map( ( _, n ) => {

		let c = n;
		for ( let k = 0; k < 8; k ++ ) c = c & 1 ? 0xedb88320 ^ ( c >>> 1 ) : c >>> 1;
		return c >>> 0;

	} );
	const crc = ( buf ) => {

		let c = 0xffffffff;
		for ( let i = 0; i < buf.length; i ++ ) c = crcTable[ ( c ^ buf[ i ] ) & 0xff ] ^ ( c >>> 8 );
		return ( c ^ 0xffffffff ) >>> 0;

	};
	const chunk = ( type, data ) => {

		const len = Buffer.alloc( 4 ); len.writeUInt32BE( data.length );
		const td = Buffer.concat( [ Buffer.from( type ), data ] );
		const c = Buffer.alloc( 4 ); c.writeUInt32BE( crc( td ) );
		return Buffer.concat( [ len, td, c ] );

	};
	const ihdr = Buffer.alloc( 13 );
	ihdr.writeUInt32BE( width, 0 ); ihdr.writeUInt32BE( height, 4 );
	ihdr[ 8 ] = 16; ihdr[ 9 ] = 0;
	writeFileSync( path, Buffer.concat( [ Buffer.from( [ 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a ] ), chunk( 'IHDR', ihdr ), chunk( 'IDAT', deflateSync( raw, { level: 9 } ) ), chunk( 'IEND', Buffer.alloc( 0 ) ) ] ) );

}

const ring = buildRingBand();
const form = buildForm( { yTop: 0.085, bevel: 0.04 } );
const swatch = new FlexSwatch( { brickPitch: ring.userData.brickPitch } );
swatch.update( 4.0, { bend: 10, twist: 1.1, wave: 7 } );
writeOBJ( join( out, 'band_ring.obj' ), ring, 'band_ring' );
writeOBJ( join( out, 'form.obj' ), form, 'form' );
writeOBJ( join( out, 'swatch.obj' ), swatch.front, 'swatch' );
console.log( 'meshes written' );

const maps = generateBandMaps( { width: 4096, height: 2048, brickPitch: ring.userData.brickPitch } );
for ( const k of [ 'albedo', 'normal', 'orm', 'irid' ] ) writePNG( join( out, `band_${k}.png` ), maps.width, maps.height, maps[ k ], { channels: 4 } );
// height in mm -> 16 bit with 1 unit = 1/100000 mm offset by 0.1 mm
const hmm = maps.heightMM;
let hmin = Infinity, hmax = - Infinity;
for ( const v of hmm ) {

	hmin = Math.min( hmin, v ); hmax = Math.max( hmax, v );

}
const hn = new Float32Array( hmm.length );
for ( let i = 0; i < hmm.length; i ++ ) hn[ i ] = ( hmm[ i ] - hmin ) / ( hmax - hmin );
writePNG16( join( out, 'band_height16.png' ), maps.width, maps.height, hn, 65535 );
console.log( 'maps written', maps.width, maps.height, 'height range mm', hmin.toFixed( 3 ), hmax.toFixed( 3 ) );

for ( const name of [ 'studio', 'darkroom', 'neon' ] ) {

	const env = generateEnvironment( name, 2048, 1024 );
	// RGBE rows are top-first
	const flipped = new Float32Array( env.data.length );
	for ( let y = 0; y < env.height; y ++ ) flipped.set( env.data.subarray( ( env.height - 1 - y ) * env.width * 4, ( env.height - y ) * env.width * 4 ), y * env.width * 4 );
	writeHDR( join( out, `${name}.hdr` ), env.width, env.height, flipped );

}
for ( const f of [ 'venice_sunset_1k.hdr', 'pedestrian_overpass_1k.hdr', 'quarry_01_1k.hdr' ] ) copyFileSync( join( root, 'assets', 'hdr', f ), join( out, f ) );
console.log( 'environments written' );

// film transmission tint for the diffuse path: T(cos θ_out) · T(θ_in ≈ 52°), as a colour ramp over cos θ
const film = { n2: 2.45, n3: 1.58, d: 106 };
const T = ( c ) => spectrumToRgb( filmSpectrum( c, film.d, film ).map( ( r ) => 1 - r ) );
const Tin = T( 0.62 );
const flopRamp = [];
for ( let i = 0; i <= 16; i ++ ) {

	const c = Math.max( 0.02, i / 16 );
	const t = T( c );
	flopRamp.push( { pos: i / 16, color: t.map( ( v, k ) => v * Tin[ k ] ) } );

}

writeFileSync( join( out, 'scene.json' ), JSON.stringify( {
	band: { ...BAND, brickPitch: ring.userData.brickPitch, tileW: ring.userData.tileW, nTiles: ring.userData.nTiles },
	torso: TORSO,
	colors: COLORS,
	heightRangeMM: [ hmin, hmax ],
	bandCenter: [ 0, BAND.height / 2000, 0 ],
	camera: { fovY: 28, azimuth: 24, elevation: 5, distance: 0.46 },
	key: { azimuth: - 16, elevation: 14, distance: 1.4, lux: 0.35, radius: 0.1 },
	film: { n2: 2.45, n3: 1.58, d: 106, spread: 0.12, brickOffset: 0.03, specGain: 1.6, brickGloss: 1.4, flopRamp },
}, null, 2 ) );
console.log( 'done ->', out );
