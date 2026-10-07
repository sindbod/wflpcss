// Minimal PNG + Radiance HDR writers for Node-side asset export.
import { deflateSync } from 'node:zlib';
import { writeFileSync } from 'node:fs';

const CRC_TABLE = new Uint32Array( 256 ).map( ( _, n ) => {

	let c = n;
	for ( let k = 0; k < 8; k ++ ) c = c & 1 ? 0xedb88320 ^ ( c >>> 1 ) : c >>> 1;
	return c >>> 0;

} );

function crc32( buf ) {

	let c = 0xffffffff;
	for ( let i = 0; i < buf.length; i ++ ) c = CRC_TABLE[ ( c ^ buf[ i ] ) & 0xff ] ^ ( c >>> 8 );
	return ( c ^ 0xffffffff ) >>> 0;

}

function chunk( type, data ) {

	const len = Buffer.alloc( 4 );
	len.writeUInt32BE( data.length );
	const td = Buffer.concat( [ Buffer.from( type, 'ascii' ), data ] );
	const crc = Buffer.alloc( 4 );
	crc.writeUInt32BE( crc32( td ) );
	return Buffer.concat( [ len, td, crc ] );

}

// rgba: Uint8Array (row 0 = bottom when flipY = true, matching GL texture rows)
export function writePNG( path, width, height, rgba, { flipY = true, channels = 4 } = {} ) {

	const stride = width * channels;
	const raw = Buffer.alloc( ( stride + 1 ) * height );
	for ( let y = 0; y < height; y ++ ) {

		const srcRow = flipY ? height - 1 - y : y;
		raw[ y * ( stride + 1 ) ] = 0;
		for ( let x = 0; x < width; x ++ ) {

			for ( let c = 0; c < channels; c ++ ) raw[ y * ( stride + 1 ) + 1 + x * channels + c ] = rgba[ ( srcRow * width + x ) * 4 + c ];

		}

	}
	const ihdr = Buffer.alloc( 13 );
	ihdr.writeUInt32BE( width, 0 );
	ihdr.writeUInt32BE( height, 4 );
	ihdr[ 8 ] = 8; ihdr[ 9 ] = channels === 4 ? 6 : 2; ihdr[ 10 ] = 0; ihdr[ 11 ] = 0; ihdr[ 12 ] = 0;
	const png = Buffer.concat( [
		Buffer.from( [ 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a ] ),
		chunk( 'IHDR', ihdr ),
		chunk( 'IDAT', deflateSync( raw, { level: 9 } ) ),
		chunk( 'IEND', Buffer.alloc( 0 ) ),
	] );
	writeFileSync( path, png );

}

// Radiance RGBE (.hdr), uncompressed scanlines. data: Float32Array RGB(A), row 0 = top.
export function writeHDR( path, width, height, data, stride = 4 ) {

	const header = Buffer.from( `#?RADIANCE\nFORMAT=32-bit_rle_rgbe\nEXPOSURE=1.0\n\n-Y ${height} +X ${width}\n`, 'ascii' );
	const body = Buffer.alloc( width * height * 4 );
	for ( let i = 0; i < width * height; i ++ ) {

		const r = data[ i * stride ], g = data[ i * stride + 1 ], b = data[ i * stride + 2 ];
		const m = Math.max( r, g, b );
		if ( m < 1e-32 ) {

			body[ i * 4 ] = body[ i * 4 + 1 ] = body[ i * 4 + 2 ] = body[ i * 4 + 3 ] = 0;
			continue;

		}
		const e = Math.ceil( Math.log2( m ) + 1e-9 );
		const scale = Math.pow( 2, - e ) * 256;
		body[ i * 4 ] = Math.min( 255, Math.floor( r * scale ) );
		body[ i * 4 + 1 ] = Math.min( 255, Math.floor( g * scale ) );
		body[ i * 4 + 2 ] = Math.min( 255, Math.floor( b * scale ) );
		body[ i * 4 + 3 ] = e + 128;

	}
	writeFileSync( path, Buffer.concat( [ header, body ] ) );

}
